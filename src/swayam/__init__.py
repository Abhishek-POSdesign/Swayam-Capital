"""
Swayam Capital: Rule-enforced options trading platform for Abhishek Sikka.

This package provides:
- Dynamic Method Rules parsing from Obsidian Second Brain (`vault_reader`)
- Tolerant rule evaluation engine (`rules_engine`)
- Market data and execution through FYERS API v3 (`fyers_client`)
- Historical options backtesting and Bhavcopy ingestion (`bhavcopy`, `local_db`)
- Operational state persistence via Supabase (`db`)
- TradingView chart integration for dual-screen analysis (`tradingview_helper`)
- AI adapter architecture for collaborative strategy synthesis (`ai`)
"""

__version__ = "0.1.0"
