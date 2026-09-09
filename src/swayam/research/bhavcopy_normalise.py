"""NSE's daily derivatives file, in the two shapes it has had, as one shape.

NSE changed the format in July 2024. Everything since is UDiFF, with column
names like `TckrSymb` and `ClsPric`. Everything before is the legacy file, with
`SYMBOL` and `CLOSE`. His profitable run, October 2022 to April 2023, is entirely
in the legacy format, so both have to be read or that run cannot be tested.

They are not the same data wearing different names. Three real differences, and
none of them may be papered over:

1. **Volume.** The legacy file counts CONTRACTS. UDiFF counts UNITS. A contract
   is a lot, and the NIFTY lot has been 75, then 50, then 65, so the two numbers
   are not comparable and are kept in separate columns. Whichever is unknown is
   NULL.
2. **The underlying.** UDiFF carries `UndrlygPric`, the NIFTY level that day.
   The legacy file does not. It is filled afterwards from our own NIFTY daily
   history, and `underlying_spot_source` says which it was.
3. **The lot size.** UDiFF carries `NewBrdLotQty` for that day, which matters
   because the lot changed. The legacy file does not carry it at all, and it is
   left NULL rather than guessed. A backtest of 2022 that assumes today's lot of
   65 is wrong by a fifth.

And one trap that is in both. **A closing price on a contract that did not trade
is not a price anyone could have got.** Untraded strikes still carry a close,
derived by the exchange. `volume_contracts` and `volume_units` are what tells
them apart, which is why they are kept even when zero.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

COLUMNS = [
    "trade_date", "symbol", "underlying", "expiry_date", "strike", "option_type",
    "open", "high", "low", "close", "prev_close", "settle_price",
    "volume_contracts", "volume_units", "turnover_inr",
    "open_interest", "change_in_oi", "underlying_spot", "underlying_spot_source",
    "lot_size", "source_format",
]

_MONTHS = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}
# The single character FYERS uses for the month in a weekly symbol.
_WEEKLY_MONTH_CHAR = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D",
}


def is_udiff(frame: pd.DataFrame) -> bool:
    """UDiFF from July 2024, legacy before it."""
    return "TckrSymb" in frame.columns


def fyers_style_symbol(expiry: date, strike: float, option_type: str, monthly: bool) -> str:
    """The contract's name in the same shape FYERS uses, so the sources join.

    A monthly contract is `NIFTY24MAR22300CE`; a weekly is `NIFTY2432122300CE`,
    where the month is one character because the day follows it immediately.
    Whether an expiry is the monthly one cannot be read off a single row, so the
    caller works it out per expiry and passes it in.
    """
    year = expiry.year % 100
    strike_text = f"{int(round(strike))}"
    if monthly:
        return f"NIFTY{year:02d}{_MONTHS[expiry.month]}{strike_text}{option_type}"
    return (
        f"NIFTY{year:02d}{_WEEKLY_MONTH_CHAR[expiry.month]}"
        f"{expiry.day:02d}{strike_text}{option_type}"
    )


def _monthly_expiries(expiries: set[date]) -> set[date]:
    """The last expiry in each month is the monthly one."""
    latest: dict[tuple[int, int], date] = {}
    for expiry in expiries:
        key = (expiry.year, expiry.month)
        if key not in latest or expiry > latest[key]:
            latest[key] = expiry
    return set(latest.values())


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("float64")


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def normalise(frame: pd.DataFrame, underlying: str = "NIFTY") -> pd.DataFrame:
    """One day's file, filtered to `underlying` options, in the shared shape."""
    if frame.empty:
        return pd.DataFrame(columns=COLUMNS)

    if is_udiff(frame):
        rows = frame[
            (frame["TckrSymb"] == underlying) & (frame["FinInstrmTp"].isin(["IDO", "OPTIDX"]))
        ].copy()
        if rows.empty:
            return pd.DataFrame(columns=COLUMNS)
        out = pd.DataFrame({
            "trade_date": pd.to_datetime(rows["TradDt"]).dt.date,
            "expiry_date": pd.to_datetime(rows["XpryDt"]).dt.date,
            "strike": _to_float(rows["StrkPric"]),
            "option_type": rows["OptnTp"].astype(str).str.upper(),
            "open": _to_float(rows["OpnPric"]),
            "high": _to_float(rows["HghPric"]),
            "low": _to_float(rows["LwPric"]),
            "close": _to_float(rows["ClsPric"]),
            "prev_close": _to_float(rows["PrvsClsgPric"]),
            "settle_price": _to_float(rows["SttlmPric"]),
            "volume_contracts": pd.Series([pd.NA] * len(rows), dtype="Int64"),
            "volume_units": _to_int(rows["TtlTradgVol"]),
            "turnover_inr": _to_float(rows["TtlTrfVal"]),
            "open_interest": _to_int(rows["OpnIntrst"]),
            "change_in_oi": _to_int(rows["ChngInOpnIntrst"]),
            "underlying_spot": _to_float(rows["UndrlygPric"]),
            "underlying_spot_source": "nse_bhavcopy",
            "lot_size": _to_int(rows["NewBrdLotQty"]),
            "source_format": "udiff",
        })
    else:
        rows = frame[
            (frame["SYMBOL"] == underlying) & (frame["INSTRUMENT"] == "OPTIDX")
        ].copy()
        if rows.empty:
            return pd.DataFrame(columns=COLUMNS)
        out = pd.DataFrame({
            "trade_date": pd.to_datetime(rows["TIMESTAMP"], format="%d-%b-%Y").dt.date,
            "expiry_date": pd.to_datetime(rows["EXPIRY_DT"], format="%d-%b-%Y").dt.date,
            "strike": _to_float(rows["STRIKE_PR"]),
            "option_type": rows["OPTION_TYP"].astype(str).str.upper(),
            "open": _to_float(rows["OPEN"]),
            "high": _to_float(rows["HIGH"]),
            "low": _to_float(rows["LOW"]),
            "close": _to_float(rows["CLOSE"]),
            "prev_close": pd.Series([float("nan")] * len(rows), dtype="float64"),
            # On an expiry day NSE puts the INDEX settlement in this column for
            # the expiring series, not the option's own. It is kept as sent and
            # must not be read as an option price without checking the expiry.
            "settle_price": _to_float(rows["SETTLE_PR"]),
            "volume_contracts": _to_int(rows["CONTRACTS"]),
            "volume_units": pd.Series([pd.NA] * len(rows), dtype="Int64"),
            # VAL_INLAKH is lakhs of rupees; one lakh is 100,000.
            "turnover_inr": _to_float(rows["VAL_INLAKH"]) * 100_000.0,
            "open_interest": _to_int(rows["OPEN_INT"]),
            "change_in_oi": _to_int(rows["CHG_IN_OI"]),
            "underlying_spot": pd.Series([float("nan")] * len(rows), dtype="float64"),
            "underlying_spot_source": None,
            "lot_size": pd.Series([pd.NA] * len(rows), dtype="Int64"),
            "source_format": "legacy",
        })

    out = out[out["option_type"].isin(["CE", "PE"])]
    out = out[out["strike"] > 0]
    if out.empty:
        return pd.DataFrame(columns=COLUMNS)

    monthly = _monthly_expiries(set(out["expiry_date"]))
    out["symbol"] = [
        fyers_style_symbol(expiry, strike, option_type, expiry in monthly)
        for expiry, strike, option_type in zip(
            out["expiry_date"], out["strike"], out["option_type"]
        )
    ]
    out["underlying"] = underlying
    return out[COLUMNS].reset_index(drop=True)


def fill_underlying_from_index(
    frame: pd.DataFrame, index_daily: pd.DataFrame
) -> pd.DataFrame:
    """Fills a missing NIFTY level from our own downloaded index history.

    The legacy file does not carry the underlying. Rather than leave two and a
    half years of his best trading with no spot, it is joined from the daily
    NIFTY bars we already hold, and `underlying_spot_source` records that it came
    from the index history rather than from NSE's own file. A backtest can then
    tell the two apart, which it could not do if they were silently merged.
    """
    if frame.empty or index_daily.empty:
        return frame

    closes = index_daily[["day", "close"]].rename(columns={"close": "_index_close"})
    merged = frame.merge(closes, left_on="trade_date", right_on="day", how="left")
    missing = merged["underlying_spot"].isna() & merged["_index_close"].notna()
    merged.loc[missing, "underlying_spot"] = merged.loc[missing, "_index_close"]
    merged.loc[missing, "underlying_spot_source"] = "fyers_index_daily_close"
    return merged.drop(columns=["day", "_index_close"])
