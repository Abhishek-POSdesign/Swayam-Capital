# Swayam Capital: Historical Expired NIFTY Options Data

## Executive Summary

For a 2–3 year NIFTY options backtest, the key requirement is not ordinary NIFTY index candles. It is **expired contract-level options history**: strike, expiry, timestamp, OHLC, volume, open interest, and ideally implied volatility and spot. FYERS and Zerodha/Kite are excellent low-cost sources for current market data, but their official documentation and support responses historically state that expired option-contract candles are unavailable through their standard APIs.[^1][^2][^3]

A newer FYERS community result indicates a beta expired-F&O endpoint with up to four years of data, but this conflicts with other FYERS support/community material that says expired options data was unavailable or still being added. Therefore, the first action should be a direct capability test against Abhishek’s FYERS API app—not a purchase of another broker or vendor.[^4][^2]

If FYERS beta access works, it is the lowest-cost route because FYERS APIs are advertised as free for clients. If it does not, DhanHQ is the most clearly documented low-cost API alternative found: its rolling-options endpoint provides up to five years of expired options data, including OHLC, IV, volume, OI and spot, with data APIs reported at ₹499/month plus taxes by Dhan-related documentation and product material.[^5][^6][^7][^8][^9]

For a minimum-cost research path, use a staged approach: free NSE end-of-day data for broad regime validation; test FYERS beta expired data; use DhanHQ for minute-level expired options only if FYERS fails; and postpone TrueData or Global Datafeeds until the strategy requires higher-fidelity intraday or tick data.

## What the Backtester Actually Needs

A backtest of defined-risk NIFTY options strategies needs the following minimum data model:

| Field | Why it matters | Minimum acceptable quality |
|---|---|---|
| Underlying NIFTY spot | Entry logic, strike selection, payoff and moneyness | Intraday synchronized with option timestamp |
| Expiry date | Determines remaining life and settlement | Exact exchange expiry |
| Strike and option type | Identifies CE/PE contract | Exact strike and type |
| OHLC | Entry, exit and stop/target simulation | 1-minute or 5-minute for intraday tests |
| Volume | Liquidity and fill-quality filter | Contract-level |
| Open interest | OI filters and option-chain studies | Historical, timestamped if strategy uses it |
| IV/Greeks | Required only if the strategy explicitly uses them or for advanced valuation | Historical preferred; otherwise calculate cautiously |
| Bid/ask or spread | More realistic fills | Strongly preferred, not always available |
| Lot size and charges | Correct P&L and cost drag | Contract-specific and date-aware |
| Trading calendar | Avoids false trades on holidays and expiry changes | Exchange calendar |

The existing Swayam Capital terminal already treats data integrity, realistic fills, charges, risk gates and journaling as core design requirements. Its current paper-trading architecture should therefore use a separate research-data layer rather than placing raw historical files directly into the live trading tables.[^10]

## FYERS Options

### Standard FYERS History API

FYERS documents its History API as a historical-candle service and says it can be used for analysis and backtesting. FYERS also advertises historical data, quotes and real-time data as available to clients at zero data-feed fees, subject to creating an API app with the required permissions.[^11][^12][^6]

However, the standard API has an important historical-options limitation. FYERS support states that expired option contracts are not available in the normal Options Chain interface, and that expired strike-level OI, IV, bid, ask and LTP are not shown there. A FYERS community response also states that the regular history and quotes routes resolve symbols only against the current instrument master, so an option becomes unresolvable after expiry.[^13][^2][^1]

### Possible FYERS expired-F&O beta endpoint

A June 2026 FYERS community response says expired F&O contract data was released in beta, with up to four years of historical data and multiple timeframes, and points to an API documentation section named **Expired FnO Contracts Data**. This is promising for Swayam Capital, but it should be treated as unverified until the endpoint is tested with the live FYERS app because other FYERS material still says historical expired-options data was unavailable or being developed.[^2][^14][^4]

The test should verify all of the following:

- A known expired NIFTY weekly option from 2024 or 2025 can be requested.
- The response includes OHLC and timestamps.
- The response includes volume and OI.
- The response includes enough spot information to synchronize the option with NIFTY.
- Weekly and monthly contracts are both supported.
- The earliest available date reaches at least three years back.
- The API returns the exact expired contract rather than an ATM-relative rolling series.
- The response can be downloaded repeatedly without undocumented restrictions.

If all tests pass, FYERS should be the first choice. It avoids the cost and operational burden of adding another broker while keeping the research and live terminal in the same ecosystem.

## Zerodha/Kite Connect

Kite Connect’s historical API provides candles containing timestamp, OHLC, volume and optionally OI for supported instruments. Its documented historical endpoint is `/instruments/historical/:instrument_token/:interval`, and the official instrument list is generated daily.[^15][^16]

The critical limitation is that Zerodha does not provide historical data for expired option contracts. Zerodha’s own support article says expired futures can be accessed through continuous charts, but expired options cannot. A recent Zerodha forum answer repeats that expired option instruments are not provided, while active options history is supported.[^17][^3]

Kite Connect therefore does not solve the central Swayam Capital requirement unless Abhishek had continuously downloaded and stored the option instrument tokens and live data before every contract expired. It can still be useful for current live data or expired futures, but buying Kite Connect solely for a three-year expired-options backtest would not be justified.

Kite’s official API rate limits include 1 request/second for quote, 3 requests/second for historical candles and 10 requests/second for other endpoints. These limits are workable, but they do not compensate for the expired-option data gap.[^18]

## DhanHQ

DhanHQ is the strongest documented alternative for this specific requirement. Its expired-options endpoint is `POST /charts/rollingoption` and provides rolling historical options data for up to five years, including OHLC, implied volatility, volume, open interest and spot information.[^8]

The important limitation is the data representation. DhanHQ describes the endpoint as rolling data based on strike relative to spot, such as ATM, ATM+1 and ATM-1, rather than necessarily a complete permanent archive of every absolute strike for every expiry. The data is stored at minute level and a single request can cover up to 30 days. This may be enough for an ATM-driven strategy, but it needs testing before being used for strategies that select fixed strikes far from ATM or require a complete historical chain.[^8]

DhanHQ’s own documentation says the normal option-chain API is limited to one unique request every three seconds because OI updates more slowly than LTP. Its release documentation says historical intraday data can extend to five years and that data APIs carry a 100,000-request daily allowance with no minute/hourly limits for the historical-data category.[^7][^19]

Dhan-related product documentation and an independent API integration guide report the Data API price as ₹499/month plus taxes, or approximately ₹399/month on annual billing, while trading APIs are free. Confirm the current price in the Dhan developer portal before subscribing.[^9][^20]

## NSE and Free Sources

NSE is useful for end-of-day research. NSE archives and derivative reports can provide contract-level daily information, and public resources identify NSE bhavcopy files as a free route for end-of-day OHLC data covering many years.[^21][^22]

NSE EOD data can answer questions such as:

- What happened on each expiry?
- Which strikes were traded?
- What were the daily high, low and close values?
- How did volume and open interest change?
- Did the strategy survive bull, bear and sideways periods at daily resolution?

NSE EOD data is not enough for an intraday strategy using a tight stop-loss, intraday target, breakout timing or 1-minute/5-minute execution. It can be used for an initial regime/backtest screen, but not as the final proof of an intraday edge.

An open-source historical option-chain project was identified in community discussion as covering 2025 and 2026, with downloadable archives and an API, but it does not yet cover the full three-year requirement and should be independently validated before use.[^21]

## Paid Vendors

TrueData advertises authorised NSE/BSE/MCX real-time and historical APIs, including options-chain APIs, Greeks and historical data, with pricing supplied through its sales process rather than a public fixed tariff. FYERS community material has previously pointed users seeking expired F&O data toward TrueData, but this means a subscription is required.[^23][^24][^25]

Global Datafeeds advertises real-time, historical, snapshot, EOD, option-chain and Greek APIs for NSE F&O. Its published availability table shows strong historical coverage for cash and market data, but contract-wise options coverage is more limited in the publicly described table; pricing is customized by requirement.[^26][^27][^28]

These vendors are more appropriate when Swayam Capital needs reliable intraday/tick history, larger-scale downloads, formal support or data licensing. They are not the minimum-cost first step for one personal terminal.

## Comparison of Routes

| Route | Expired NIFTY options | Intraday | Historical OI | Cost position | Fit for Swayam Capital |
|---|---|---:|---:|---|---|
| FYERS beta expired-F&O endpoint | Possibly, up to four years according to a 2026 community response | Reported multiple timeframes | Must verify | Potentially ₹0 as existing client | **Test first** |
| FYERS standard History/Options Chain | No reliable expired-option access in older/current support material | Active contracts only for this use case | No historical expired OI | ₹0 | Not sufficient alone |
| Zerodha Kite Connect | No expired option history | Active options only | Not for expired options | API subscription cost if added | Do not buy for this purpose |
| NSE archives/bhavcopy | Yes, mainly EOD contract data | No/minimal intraday | EOD OI may be available; timestamped intraday OI no | Free | First free benchmark |
| DhanHQ rolling options | Yes, up to five years | Minute level | Yes | About ₹499/month plus taxes, subject to confirmation | **Best paid low-cost API** |
| TrueData | Yes, depending on package | Intraday/tick-oriented | Vendor package dependent | Quote required | Later, if fidelity matters |
| Global Datafeeds | Advertises historical F&O and option APIs | Intraday/tick options available by package | Vendor package dependent | Quote required | Later, for professional-grade feed |

## Recommended Minimum-Cost Plan

### Stage 1: Free, no new broker

Use FYERS daily NIFTY spot/futures data and NSE EOD option files to create the backtester’s data schema. This proves the strategy engine, payoff calculations, expiry handling, lot-size handling, brokerage/charges model and report generation without buying new data.

At this stage, test broad historical behaviour across:

- A rising market period.
- A sharp falling or high-volatility period.
- A sideways or range-bound period.
- Multiple weekly and monthly expiries.
- Expiry-day and non-expiry-day entries.

Do not call a strategy “validated” from this stage if its actual rule is intraday and the data is EOD.

### Stage 2: Test FYERS expired-F&O access

Build a small downloader for the suspected expired-F&O endpoint. Test five known contracts: a weekly call, weekly put, monthly call, monthly put and a far-from-ATM strike. Test dates at approximately one month, one year, two years and three years in the past.

The acceptance test is not “the endpoint returned JSON.” It must return correct, timestamped data that can be reconciled against an independent source or known chart. Store the raw response, request parameters, API version, retrieval time and a checksum.

### Stage 3: Add DhanHQ only if necessary

If FYERS does not provide complete expired contracts, subscribe to DhanHQ Data API for one month and download only the exact research window and fields needed. DhanHQ’s five-year rolling-options feature is specifically designed for expired options research, but confirm whether ATM-relative strikes cover Abhishek’s actual strategy before relying on it.[^8]

A one-month paid acquisition is preferable to a permanent monthly subscription while the backtester is still being designed. Freeze the downloaded data in `gs://swayam-capital-options-data` and keep the raw source files separate from normalized tables.

### Stage 4: Upgrade only after the strategy is specified

If the strategy needs every strike, bid/ask, tick data, or accurate intraday execution simulation, obtain vendor quotes from TrueData and Global Datafeeds. Do not pay for those feeds before writing a precise data specification; otherwise, the project can spend money on fields the strategy never uses.

## Data Architecture for Swayam Capital

Create three layers:

### Raw layer

Store the vendor response unchanged:

- Provider.
- Endpoint.
- Request payload.
- Retrieval timestamp.
- Response checksum.
- Original file or compressed JSON.

### Normalized market layer

Normalize into a schema such as:

```text
options_candles
- provider
- underlying
- expiry_date
- strike
- option_type
- timestamp_ist
- open
- high
- low
- close
- volume
- open_interest
- implied_volatility
- spot
- source_quality
```

### Backtest layer

Store the assumptions separately from the market data:

- Entry time.
- Signal time.
- Fill model.
- Slippage.
- Brokerage and taxes.
- Lot size.
- Stop-loss rule.
- Target rule.
- Position-sizing rule.
- Daily, weekly and monthly loss caps.

The backtester must never silently fill a missing price. If bid/ask is absent, use a declared approximation and label the result as less reliable. The existing Swayam terminal has already identified realistic fills and per-leg charges as important, so the historical engine should follow the same discipline.[^10]

## Minimum Data Quality Tests

Before trusting any backtest result:

1. Confirm every option candle belongs to a valid expiry and strike.
2. Confirm no option trades before its listing date or after expiry.
3. Confirm timestamps are in IST and aligned with the NIFTY spot series.
4. Check for duplicate candles.
5. Check for gaps during market hours.
6. Compare a sample of candles against NSE or a second provider.
7. Check that OI never gets treated as price.
8. Verify lot size by date rather than hard-coding today’s lot size.
9. Include transaction costs, STT, exchange charges, GST, SEBI charges and slippage.
10. Run an out-of-sample period that was not used to design the rules.

## Final Assessment

The minimum-cost route is **not** to purchase Kite Connect. Zerodha does not provide expired option history, so its subscription would add cost without solving the core requirement.[^3][^17]

The preferred sequence is:

1. Build the engine and EOD benchmark with free NSE data.
2. Test the FYERS beta expired-F&O endpoint because Abhishek already owns the account and FYERS APIs are advertised as free.
3. If FYERS is incomplete or inaccessible, buy one month of DhanHQ Data API and download the required historical window.
4. Move to TrueData or Global Datafeeds only if the strategy needs complete strike coverage, tick data, bid/ask history or stronger vendor support.

A three-year period is a reasonable **initial research window** for covering different regimes, but it is not proof that a strategy will remain profitable. The backtest should be followed by walk-forward testing, a held-out period and paper/front testing through the existing Swayam Capital terminal before any increase in position size.

---

## References

1. [Can I view expired contracts in FYERS? - FYERS - Support Portal](https://support.fyers.in/portal/en/kb/articles/can-i-view-expired-contracts-in-fyers) - FYERS does not support viewing expired option contracts in the chain. Learn how to access historical...

2. [Nifty Historical Option Chain Data - Support Desk - FYERS Community](https://fyers.in/community/t/nifty-historical-option-chain-data/22327) - Hello Team, I am using the Fyers API v3 to fetch historical data. The monthly symbol “NSE:NIFTY26JAN...

3. [How to access historical data for expired F&O contracts on Kite?](https://support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/historical-data-for-expired-f-o-contract) - You can access historical data for expired futures contracts using the continuous chart feature. You...

4. [Is historical options OI data via API - FYERS](https://fyers.in/community/t/is-historical-options-oi-data-via-api/22795) - How can I get historical options OI data?

5. [API - FYERS](https://myapi.fyers.in/) - Start Algo trading or integrate with third-party platforms using FYERS API, for absolutely free.

6. [Do I need to pay for Datafeeds?](https://support.fyers.in/portal/en/kb/articles/do-i-need-to-pay-for-datafeeds) - With FYERS API, you will be able to access the historical data, quotes and real-time data. This is a...

7. [Releases - DhanHQ Ver 2.0 / API Document](https://dhanhq.co/docs/v2/releases/)

8. [Expired Options Data - DhanHQ Ver 2.0 / API Document](https://dhanhq.co/docs/v2/expired-options-data/) - Level 3 data including 20 level and 200 level market depth data for NSE, streamed real-time via webs...

9. [Dhan](https://docs.openalgo.in/connect-brokers/brokers/dhan)

10. [SWAYAM_START_HERE.md](SWAYAM_START_HERE.md)

11. [Platforms & Tools | Data API](https://support.fyers.in/portal/en/kb/platforms-tools/fyers-api/api-v3/data-api) - Platforms & Tools | Data API | Support

12. [FYERS API & Integrations | Data API Knowledge Base](https://support.fyers.in/portal/en/kb/fyers-api-integrations/fyers-api/api-v3/data-api) - FYERS API & Integrations | Data API | Support

13. [Platforms & Tools | Options Chain Knowledge Base](https://support.fyers.in/portal/en/kb/platforms-tools/options/options-chain) - Platforms & Tools | Options Chain | Support

14. [Regarding Historical Data with Open Interest (OI) - Questions - FYERS](https://fyers.in/community/t/regarding-historical-data-with-open-interest-oi/21276) - I wanted to ask if Fyers offers access to historical data that includes Open Interest (OI) along wit...

15. [Historical candle data - Kite Connect 3 / API documentation](https://kite.trade/docs/connect/v3/historical/) - The historical data API provides archived data (up to date as of the time of access) for instruments...

16. [Market and instruments - Kite Connect 3 / API documentation](https://kite.trade/docs/connect/v3/market-data-and-instruments/)

17. [Does 100-day Historical API include expired index option candles?](https://kite.trade/forum/discussion/16179/does-100-day-historical-api-include-expired-index-option-candles) - We do not provide historical data for expired option instruments. Historical data is available only ...

18. [Exceptions and errors - Kite Connect 3 / API documentation](https://kite.trade/docs/connect/v3/exceptions/)

19. [Option Chain - DhanHQ Ver 2.0 / API Document](https://dhanhq.co/docs/v2/option-chain/) - Realtime Option Chain data with greeks, implied volatility, ltp, volume and open interest data for a...

20. [Enhanced: DhanHQ Data APIs with more Data and Higher Rate Limits](https://madefortrade.in/t/enhanced-dhanhq-data-apis-with-more-data-and-higher-rate-limits/50328) - Hello Everyone, Since the launch of DhanHQ v2 APIs, we have been constantly updating and enhancing o...

21. [Looking for Expired F&O Data (India) - Trading Q&A by Zerodha](https://tradingqna.com/t/looking-for-expired-f-o-data-india/193302) - vilpage.com is the only free & open source tool available for expired options data. For now we have ...

22. [Daily Market Reports - Derivative Market - NSE](https://www.nseindia.com/resources/historical-reports-capital-market-daily-monthly-archives-derivative-market) - Live Analysis of top gainers/losers, most active securities/contracts, price band hitters, overview ...

23. [Options History Data - API & Algo](https://fyers.in/community/t/options-history-data/13340) - Today is 9th June, 2024. I’ve written a code to back test my strategy for Nifty Options. But I’m not...

24. [Market Data API | Live, SnapChat, Options Chain, Option Greeks](https://www.truedata.in/market-data-apis) - The TrueData Market Data API provides direct, authorised access to real-time streaming and charting-...

25. [Real-Time Market Data API for NSE, BSE & MCX](https://www.truedata.in/products/marketdataapi) - Get low latency NSE, BSE & MCX Market Data APIs with real-time WebSocket feeds, option chain, Greeks...

26. [APIs - Real-time, historical, snapshot, delayed, end-of-day ...](https://globaldatafeeds.in/apis/) - API – how it works ? Available APIs featureS What is available We offer realtime & historical data o...

27. [API Pricing](https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/pricing-sales/api-pricing/) - Introduction We offer following types of Data through our APIs Realtime APIRealtime data updating at...

28. [Type of Data Available - Global Datafeeds](https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/introduction/type-of-data-available/) - Historical Data API Historical data of Periodicity Tick, Minute, Day, Week, Month is available – as ...

