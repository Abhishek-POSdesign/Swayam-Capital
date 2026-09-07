"""
Real broker margin, from FYERS.

What this replaces
------------------
Two invented constants in `execution.py`: ₹32,000 per lot for a hedged short
and ₹1,15,000 per lot for a naked short. Neither came from anywhere. Measured
against the live account on 2026-09-07, for one lot of NIFTY:

    naked short 23750 PE          shown ₹1,15,000    actual ₹2,00,441
    bear put spread 23700/23750   shown    ₹32,000   actual   ₹66,836

Both understated the real requirement by roughly half, which is the dangerous
direction: it made trades look affordable that the broker would refuse.

Two things learned while proving this endpoint, both easy to lose again
--------------------------------------------------------------------
1. **Leg order changes the answer.** With the SELL leg listed first, FYERS
   returns the naked margin and no hedge benefit. With the BUY leg first it
   returns ₹66,836 instead of ₹2,00,441 for the same spread. Buy legs are
   therefore always sent first.
2. **A default Python user agent is blocked by Cloudflare** with an HTTP 403
   and error code 1010, which looks exactly like an authentication failure and
   is not. A browser user agent is required.

Failure policy: if the broker cannot be reached, or answers with anything this
module does not recognise, the result is **unavailable**. There is no estimate,
no cached-forever value and no fallback constant. A trade that cannot be priced
does not get a made-up price.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal, Optional, Sequence

import requests

from swayam.config import settings
from swayam.services.contract_master import (
    ContractMasterUnavailable,
    get_lot_size,
    get_symbol,
)

logger = logging.getLogger(__name__)

MARGIN_URL = "https://api-t1.fyers.in/api/v3/multiorder/margin"
TIMEOUT_SECONDS = 20
CACHE_SECONDS = 60
MIN_SECONDS_BETWEEN_CALLS = 1.0

# Cloudflare rejects the default urllib/requests user agent with a 403 and
# error code 1010, which reads like an auth failure. Do not remove this.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

_lock = threading.Lock()
_cache: dict[tuple, tuple[float, "MarginQuote"]] = {}
_last_call_at = 0.0


class MarginUnavailable(RuntimeError):
    """The broker margin could not be established. Show 'unavailable', never a number."""


@dataclass(frozen=True)
class MarginLeg:
    """One leg of a basket, in the terms the margin endpoint understands."""

    strike: float
    option_type: Literal["CE", "PE"]
    direction: Literal["buy", "sell"]
    quantity_lots: int
    expiry: date
    underlying: str = "NIFTY"


@dataclass(frozen=True)
class MarginQuote:
    """A margin figure that can say where it came from."""

    total_inr: float
    new_order_inr: float
    available_inr: float
    source: str = "FYERS multiorder/margin"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "margin_total_inr": round(self.total_inr, 2),
            "margin_new_order_inr": round(self.new_order_inr, 2),
            "margin_available_inr": round(self.available_inr, 2),
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(),
        }


def _cache_key(legs: Sequence[MarginLeg], product_type: str) -> tuple:
    return (
        product_type,
        tuple(
            sorted(
                (l.underlying, l.expiry.isoformat(), l.strike, l.option_type,
                 l.direction, l.quantity_lots)
                for l in legs
            )
        ),
    )


def _build_payload(legs: Sequence[MarginLeg], product_type: str) -> dict:
    """Builds the request body, buy legs first.

    Ordering is not cosmetic. FYERS returns the un-hedged margin when a short
    leg is listed before the long leg that covers it.
    """
    ordered = [l for l in legs if l.direction.lower() == "buy"]
    ordered += [l for l in legs if l.direction.lower() != "buy"]

    data = []
    for leg in ordered:
        lot = get_lot_size(leg.underlying, leg.expiry)
        data.append(
            {
                "symbol": get_symbol(leg.underlying, leg.expiry, leg.strike, leg.option_type),
                "qty": leg.quantity_lots * lot,
                "side": 1 if leg.direction.lower() == "buy" else -1,
                "type": 2,  # market, for a margin estimate
                "productType": product_type,
                "limitPrice": 0.0,
                "stopLoss": 0.0,
                "stopPrice": 0.0,
                "takeProfit": 0.0,
            }
        )
    return {"data": data}


def get_margin(
    legs: Sequence[MarginLeg],
    *,
    product_type: str = "MARGIN",
    force: bool = False,
) -> MarginQuote:
    """Returns the broker's margin requirement for a basket of legs.

    Cached for a minute on the full leg set and throttled, so a slider drag
    cannot hammer the broker. Never called speculatively.

    Raises:
        MarginUnavailable: on any failure at all. Callers must surface
            'unavailable' rather than substitute a number.
    """
    global _last_call_at

    if not legs:
        raise MarginUnavailable("No legs supplied.")
    if not settings.fyers_access_token or not settings.fyers_app_id:
        raise MarginUnavailable("FYERS is not configured.")

    key = _cache_key(legs, product_type)
    now = time.monotonic()

    with _lock:
        hit = _cache.get(key)
        if hit and not force and now - hit[0] < CACHE_SECONDS:
            return hit[1]

    try:
        payload = _build_payload(legs, product_type)
    except ContractMasterUnavailable as exc:
        raise MarginUnavailable(f"Contract details unavailable: {exc}") from exc

    with _lock:
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()

    try:
        response = requests.post(
            MARGIN_URL,
            headers={
                "Authorization": f"{settings.fyers_app_id}:{settings.fyers_access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": _BROWSER_UA,
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # No retry loop. A broker that is down stays down for this request.
        raise MarginUnavailable(f"Could not reach the FYERS margin service: {exc}") from exc

    if response.status_code != 200:
        raise MarginUnavailable(
            f"FYERS margin service returned HTTP {response.status_code}."
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise MarginUnavailable("FYERS margin service returned a non-JSON body.") from exc

    if body.get("s") != "ok":
        raise MarginUnavailable(
            f"FYERS margin service refused the request: {body.get('message') or body.get('code')}"
        )

    data = body.get("data") or {}
    try:
        quote = MarginQuote(
            total_inr=float(data["margin_total"]),
            new_order_inr=float(data["margin_new_order"]),
            available_inr=float(data["margin_avail"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        # Schema validation. A changed response shape must not be read as zero.
        raise MarginUnavailable(
            "FYERS margin response did not carry the expected fields."
        ) from exc

    if quote.total_inr <= 0:
        raise MarginUnavailable("FYERS returned a margin of zero, which cannot be right.")

    with _lock:
        _cache[key] = (time.monotonic(), quote)
    return quote


def try_get_margin(legs: Sequence[MarginLeg], **kwargs) -> tuple[Optional[MarginQuote], Optional[str]]:
    """get_margin, but returning the reason instead of raising.

    For display paths that must render 'unavailable' with a reason rather than
    fail the whole page.
    """
    try:
        return get_margin(legs, **kwargs), None
    except MarginUnavailable as exc:
        logger.warning("Margin unavailable: %s", exc)
        return None, str(exc)
