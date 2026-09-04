"""
NSE Derivatives Bhavcopy Ingestion Pipeline for Swayam Capital.

Downloads official End-of-Day (EOD) Bhavcopy archives directly from the National
Stock Exchange (NSE) in standardized UDiFF / legacy formats, filters derivative
records to NIFTY options, and ingests them into the local DuckDB database.
"""

from datetime import date, datetime
import io
from pathlib import Path
from typing import Optional
import zipfile
import duckdb
import pandas as pd
import requests
from swayam.config import settings
from swayam.local_db import local_db


class BhavcopyError(Exception):
    """Raised when Bhavcopy download or parsing fails."""
    pass


class BhavcopyDownloader:
    """Manages downloading, parsing, and ingesting official NSE Bhavcopies."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = Path(output_dir or settings.bhavcopy_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def get_bhavcopy_url(self, target_date: date) -> list[str]:
        """Generates candidate URLs for downloading Bhavcopy for a given date."""
        date_str = target_date.strftime("%Y%m%d")
        year_str = target_date.strftime("%Y")
        month_str = target_date.strftime("%b").upper()
        day_str = target_date.strftime("%d")

        # Candidate 1: Standardized UDiFF format (post July 8, 2024)
        udiff_url = (
            f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"
        )
        # Candidate 2: Alternative UDiFF path
        udiff_alt = (
            f"https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"
        )
        # Candidate 3: Traditional legacy format (pre July 2024)
        legacy_url = (
            f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
            f"{year_str}/{month_str}/fo{day_str}{month_str}{year_str}bhav.csv.zip"
        )
        return [udiff_url, udiff_alt, legacy_url]

    def download_bhavcopy(self, target_date: date) -> Path:
        """Downloads the Bhavcopy zip from NSE, extracts it, and saves as a clean CSV.

        Args:
            target_date: Trading session date.

        Returns:
            Path: Path to the extracted CSV file.
        """
        output_csv = self.output_dir / f"{target_date.strftime('%Y-%m-%d')}.csv"
        if output_csv.exists() and output_csv.stat().st_size > 0:
            return output_csv

        urls = self.get_bhavcopy_url(target_date)
        content_bytes: Optional[bytes] = None

        for url in urls:
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    content_bytes = resp.content
                    break
            except requests.RequestException:
                continue

        if not content_bytes:
            raise BhavcopyError(
                f"Bhavcopy unavailable for {target_date} (likely weekend, holiday, or before archive creation)."
            )

        # Unpack zip
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                if not csv_names:
                    raise BhavcopyError(f"No CSV file found inside downloaded zip for {target_date}")
                raw_csv = z.read(csv_names[0])
                output_csv.write_bytes(raw_csv)
                return output_csv
        except zipfile.BadZipFile as e:
            raise BhavcopyError(f"Downloaded payload for {target_date} was not a valid zip file: {e}") from e

    def parse_bhavcopy(self, csv_path: Path) -> pd.DataFrame:
        """Parses a downloaded Bhavcopy CSV and filters down to NIFTY index options.

        Args:
            csv_path: Path to the raw extracted Bhavcopy CSV.

        Returns:
            pd.DataFrame: Cleaned DataFrame conforming to `options_history` schema.
        """
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().upper() for c in df.columns]

        # Handle UDiFF format vs Legacy format
        if "TCKRSYMB" in df.columns or "TRADDT" in df.columns:
            # UDiFF Format (post July 2024)
            # Filter for NIFTY options (TCKRSYMB == 'NIFTY' and OPTNTP in CE/PE)
            optn_col = "OPTNTP" if "OPTNTP" in df.columns else None
            tckr_col = "TCKRSYMB" if "TCKRSYMB" in df.columns else None
            if not optn_col or not tckr_col:
                return pd.DataFrame()

            mask = (df[tckr_col].astype(str).str.strip() == "NIFTY") & (
                df[optn_col].astype(str).str.strip().str.upper().isin(["CE", "PE"])
            )
            sub = df[mask].copy()
            if sub.empty:
                return pd.DataFrame()

            symbol_series = (
                sub["FININSTRMNM"].astype(str).str.strip()
                if "FININSTRMNM" in sub.columns
                else sub[tckr_col].astype(str).str.strip()
            )

            parsed = pd.DataFrame({
                "trade_date": pd.to_datetime(sub["TRADDT"]).dt.date,
                "symbol": symbol_series,
                "underlying": "NIFTY",
                "expiry_date": pd.to_datetime(sub["XPRYDT"]).dt.date if "XPRYDT" in sub.columns else pd.to_datetime(sub["TRADDT"]).dt.date,
                "strike": pd.to_numeric(sub["STRKPRIC"], errors="coerce") if "STRKPRIC" in sub.columns else None,
                "option_type": sub[optn_col].astype(str).str.strip().str.upper(),
                "open": pd.to_numeric(sub.get("OPNPRIC", 0), errors="coerce"),
                "high": pd.to_numeric(sub.get("HGHPRIC", 0), errors="coerce"),
                "low": pd.to_numeric(sub.get("LWPRIC", 0), errors="coerce"),
                "close": pd.to_numeric(sub.get("CLSPRIC", 0), errors="coerce"),
                "settle_price": pd.to_numeric(sub.get("STTLMPRIC", sub.get("CLSPRIC", 0)), errors="coerce"),
                "volume": pd.to_numeric(sub.get("TTLTRADGVOL", 0), errors="coerce").fillna(0).astype("int64"),
                "turnover_inr": pd.to_numeric(sub.get("TTLTRFVAL", 0), errors="coerce").fillna(0.0),
                "open_interest": pd.to_numeric(sub.get("OPNINTRST", 0), errors="coerce").fillna(0).astype("int64"),
                "change_in_oi": pd.to_numeric(sub.get("CHNGINOPNINTRST", 0), errors="coerce").fillna(0).astype("int64"),
                "underlying_spot": pd.to_numeric(sub.get("UNDRLYGPRIC", None), errors="coerce"),
            })
            return parsed

        elif "INSTRUMENT" in df.columns:
            # Legacy Format
            mask = (df["INSTRUMENT"].isin(["OPTIDX"])) & (df["SYMBOL"].str.strip() == "NIFTY")
            sub = df[mask].copy()
            if sub.empty:
                return pd.DataFrame()

            parsed = pd.DataFrame({
                "trade_date": pd.to_datetime(sub["TIMESTAMP"]).dt.date,
                "symbol": sub["SYMBOL"].str.strip() + "_" + sub["EXPIRY_DT"].str.strip() + "_" + sub["STRIKE_PR"].astype(str) + sub["OPTION_TYP"].str.strip(),
                "underlying": "NIFTY",
                "expiry_date": pd.to_datetime(sub["EXPIRY_DT"]).dt.date,
                "strike": pd.to_numeric(sub["STRIKE_PR"], errors="coerce"),
                "option_type": sub["OPTION_TYP"].str.strip().str.upper(),
                "open": pd.to_numeric(sub["OPEN"], errors="coerce"),
                "high": pd.to_numeric(sub["HIGH"], errors="coerce"),
                "low": pd.to_numeric(sub["LOW"], errors="coerce"),
                "close": pd.to_numeric(sub["CLOSE"], errors="coerce"),
                "settle_price": pd.to_numeric(sub.get("SETTLE_PR", sub["CLOSE"]), errors="coerce"),
                "volume": pd.to_numeric(sub.get("CONTRACTS", 0), errors="coerce").fillna(0).astype("int64"),
                "turnover_inr": pd.to_numeric(sub.get("VAL_INLAKH", 0) * 100000.0, errors="coerce").fillna(0.0),
                "open_interest": pd.to_numeric(sub.get("OPEN_INT", 0), errors="coerce").fillna(0).astype("int64"),
                "change_in_oi": pd.to_numeric(sub.get("CHG_IN_OI", 0), errors="coerce").fillna(0).astype("int64"),
                "underlying_spot": None,
            })
            return parsed

        return pd.DataFrame()

    def ingest_to_duckdb(self, csv_path: Path) -> int:
        """Parses a Bhavcopy CSV and ingests NIFTY options into DuckDB."""
        df = self.parse_bhavcopy(csv_path)
        if df.empty:
            return 0
        return local_db.insert_options_df(df)


# Global downloader instance
bhavcopy_downloader = BhavcopyDownloader()
