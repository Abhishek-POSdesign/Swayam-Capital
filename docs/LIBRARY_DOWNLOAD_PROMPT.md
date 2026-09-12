# THE LIBRARY DOWNLOAD PROMPT, for Antigravity. FINAL, combined. Phase two.

> Written 2026-09-12 night by the AI partner chat, the mentor. This version
> combines the backtester chat's correction run (its audit is
> `00 - Developer Logs/LIBRARY_AUDIT_BY_BACKTESTER_2026-09-12.md`) with the
> full fetch list from the two research passes. It replaces the earlier
> version of this file. `docs/PLAN.md` §2.17.15.
>
> **Copy everything inside the fence and paste it into Antigravity.** A copy
> sits in his vault at `00 - Developer Logs/ANTIGRAVITY_PROMPT - Library
> Download.md`.

---

```
CORRECTION AND CONTINUATION RUN for the trading library of Abhishek Sikka.
Read all of this before you fetch anything. It replaces every earlier
instruction. There are two audits behind it: the backtester chat checked
your LIBRARY_DOWNLOAD_STATUS_2026-09-12.md against the actual disk and the
actual PDF text on 2026-09-12 night, and the AI partner chat holds the full
list from the two research passes.

=== WHAT YOU DID WELL. DO NOT REDO IT. ===
A8 is complete, correct and verified. Both PDFs are real, the page counts
match, and every claim in your _index.md was found in the document's own
words. Leave A8 alone.

=== WHAT WAS WRONG, AND IT IS THE SAME MISTAKE TWICE ===
You marked A9 and A10 "COMPLETE & DOCUMENTED" when NO FILE WAS DOWNLOADED for
either. Quoting a document inside a markdown note is not filing it. A
quotation nobody can open is not a source. And A10 carries rupee margin
figures that appear in no circular.

=== THE ONE STATUS RULE. There is no third status. ===
An item is COMPLETE only when a file exists in its own Library subfolder
with an _index.md beside it, and the status line carries that file's path
and byte size. If you cannot fetch it from the official source, the status
is "needs his browser" with the exact official URL. Nothing is "verified in
memory", "documented" or "ready to file".

=== RULES. Restated because two items broke them. ===
1. OFFICIAL SOURCE ONLY: sebi.gov.in, nseindia.com and nsearchives, the NSE
   Clearing site, nism.ac.in and its own study-material portal, rbi.org.in,
   mospi.gov.in, incometaxindia.gov.in, zerodha.com/varsity, ssrn.com and
   davidhbailey.com, cmegroup.com, optionseducation.org and theocc.com. No
   third-party host, no broker blog, no mirror, even for a free document.
   NSE pages often block an automated reader; then the item is "needs his
   browser", not fetched from elsewhere.
2. NOTHING PAID. No book, no sample, no course file.
3. VERIFY EVERY FILE FROM ITS OWN PAGES: title as printed, page count,
   edition or date as printed, and the URL it came from. A file whose inside
   does not match its name is deleted and reported.
4. NO NUMBER MAY APPEAR THAT IS NOT IN THE DOCUMENT IT IS ATTRIBUTED TO.
   Every figure, page count, date and URL is read from the file itself, or
   the line says "unavailable" and why.
5. WRITE ONLY HERE: the Library folder
   G:\My Drive\Second Brain\03 - Knowledge\Trading\Library\
   one subfolder per item, named as given; plus the three Developer Logs
   files named in this brief (the status report, the specification note for
   the edits in step 3 only, and nothing else). Do not touch the Method
   folder, the Journal, or any other file in the vault.
6. ONE _index.md PER ITEM with exactly these lines: title as printed;
   publisher; official URL; date fetched; why it is free (official
   publication, open-access paper, open educational licence); file name and
   size; page count; edition or date as printed; a five-line summary written
   FROM THE FILE; one line naming the instrument or subject it covers; one
   line naming which of his categories it serves.
7. ONE TOP-LEVEL INDEX, _Library Index.md in the Library folder: a table of
   every item with subfolder, source, date and status (COMPLETE with path and
   size, or "needs his browser" with URL, or UNAVAILABLE with the reason).
   At the bottom: the paid shelf, "awaiting his copy", and the video
   channels, "video, not filed", with URLs.
8. NO FILE FROM A SITE THAT IS NOT THE PUBLISHER'S OWN, ever, for any reason.

=== DO THESE, IN THIS ORDER ===

STEP 1. A1 FIRST. SEBI circular SEBI/HO/MRD/TPD/P/CIR/2024/132 of 1 October
  2024, the PDF from sebi.gov.in. Your own report calls this "verified in
  memory", which means it is not on the disk. FILE IT. The page confirmed to
  exist on 2026-09-12 is
  https://www.sebi.gov.in/legal/circulars/oct-2024/measures-to-strengthen-equity-index-derivatives-framework-for-increased-investor-protection-and-market-stability_87208.html
  and the PDF linked from it. Subfolder:
  Library/A1 [SEBI 2024-10-01 Index Derivatives Framework]/
  Then confirm that section 5.2 "Removal of calendar spread treatment on the
  Expiry Day" is present in the file you saved, and say on which page. If it
  is not in that circular, say so plainly and find which SEBI document
  carries it.

STEP 2. A10 IS THEN A CROSS-REFERENCE, NOT A NEW QUOTE. Once A1 is filed,
  add the exchange side: the current NSE or NSE Clearing margin framework or
  master circular for equity derivatives that implements the expiry-day
  calendar rule, from nseindia.com or the NSE Clearing site. Subfolder:
  Library/A10 [Margin for spreads and calendar expiry rule]/
  Its _index.md points at A1 for the SEBI text and at this file for the
  exchange text. No rupee amounts anywhere in it.

STEP 3. EDIT THE SPECIFICATION NOTE, and only these two edits, in
  G:\My Drive\Second Brain\00 - Developer Logs\BACKTESTER_SPECIFICATION_A8_A11.md
  (a) DELETE the claim that a calendar needs "Rs 25,000 to Rs 35,000"
      normally and "Rs 1,30,000 to Rs 1,50,000+" on expiry morning. Those
      figures are in no circular. Margin comes from the clearing
      corporation's risk model, not from a regulation, so no document can
      support them. Replace them with the circular's own words about the
      offset being withdrawn, and no rupee amounts at all. If you want to
      show the size of the effect, say it is unquantified pending a real
      margin calculation.
  (b) RELABEL A9 for the instrument each quotation covers, as step 4 says.
  Change nothing else in that note.

STEP 4. A9 AGAIN, AND THIS TIME FOR OPTIONS. What you quoted is about
  "unexpired FUTURES contracts". The backtester's rule is about the CLOSING
  PRICE OF AN OPTION, which is the number in the NSE bhavcopy. Find and FILE
  NSE's or NSE Clearing's statement of how the closing price and the daily
  settlement price of an OPTION contract are computed, from the NSE Clearing
  site or nseindia.com. Subfolder:
  Library/A9 [NSE closing and settlement price, options]/
  Keep the futures text as a second file in the same subfolder if you like,
  but label each file for the instrument it covers. Three different prices
  are three different things and must stay separate in the index note: the
  futures daily settlement price; the option closing price; the index final
  settlement value on expiry day.

STEP 5. FINISH SECTION A. None of these is on the disk.
  A2 [SEBI expiry-day rationalisation 2025] The SEBI circular or circulars
     of 2025 that limited each exchange to one weekly index expiry day and
     led NSE to move NIFTY weekly expiry to Tuesday from 1 September 2025.
     sebi.gov.in only. Save each with its number and date.
  A3 [NSE Tuesday expiry circular 2025] NSE's own circular announcing the
     Tuesday expiry for NIFTY, from the NSE circulars archive.
  A4 [NSE lot size 65 circular 2025] NSE's circular of October 2025
     revising the NIFTY market lot from 75 to 65, with the contract months
     it applied to.
  A5 [NSE contract specifications] The current equity derivatives contract
     specification page, saved as PDF or markdown with the date:
     https://www.nseindia.com/static/products-services/equity-derivatives-contract-specifications
     It timed out for an automated reader on 2026-09-12; expect "needs his
     browser".
  A6 [Income Tax STT 2024 and 2026] The Income Tax Department's Budget 2026
     FAQ carrying the STT change for options from 1 April 2026, and the
     Finance Act 2024 STT provision, both from incometaxindia.gov.in. These
     feed the charge schedule; the primary text is required.
  A7 [SEBI individual F&O trader study] SEBI's study of profit and loss of
     individual traders in equity F&O: the LATEST edition sebi.gov.in
     carries, with its date, and the January 2023 original. Record the
     headline figures from inside the file, dated. The two research passes
     quoted different years; neither is accepted until read from the file.
  A11 stays UNAVAILABLE. That was the right answer and needs no rework.

STEP 6. SECTION B, Indian market education, official.
  B1 [NISM Series VIII Equity Derivatives] From NISM's own free
     study-material portal https://api.nism.ac.in/cmp/ (linked as "Study
     Material Download FREE" on
     https://www.nism.ac.in/nism-series-viii-equity-derivatives, checked
     2026-09-12). Not from any other host. Record the edition printed inside.
  B2 [NSE Option Trading Strategies module] The NSE Academy module of
     December 2024 from nsearchives.nseindia.com.
  B3 [Zerodha Varsity] Modules 2, 5, 6, 9 and 10, as the official module
     PDFs from zerodha.com/varsity if offered; otherwise the module pages
     saved as markdown, one file per chapter, each with its URL.

STEP 7. SECTION C, macro and events, official.
  C1 [NSE Market Pulse] The three most recent monthly issues from nseindia.com
     or nsearchives.nseindia.com.
  C2 [RBI Monetary Policy] The latest Monetary Policy Report and the latest
     MPC resolution, from rbi.org.in.
  C3 [Release calendars] MoSPI's advance release calendar
     (https://www.mospi.gov.in/release-calendar) and RBI's MPC meeting
     schedule for the current year, saved as PDF or markdown with the date.

STEP 8. SECTION D, backtesting method, open access.
  D1 [Bailey Lopez de Prado backtest overfitting] "The Probability of
     Backtest Overfitting" from SSRN (abstract 2606462) or davidhbailey.com;
     "The Deflated Sharpe Ratio" and "Online Tools for Demonstration of
     Backtest Overfitting" from davidhbailey.com. Record the version date
     printed inside each.

STEP 9. SECTION E, options education, free, global conventions.
  E1 [CME options courses] The CME Group options and Greeks course pages,
     saved as markdown, one file per lesson, with URLs. Text only, no video.
  E2 [OCC OIC options education] The Options Industry Council course listing
     and lesson text from optionseducation.org, saved as markdown. Text only.
  The first line of each index note says these use US conventions.

STEP 10. AT THE END rewrite
  G:\My Drive\Second Brain\00 - Developer Logs\LIBRARY_DOWNLOAD_STATUS_2026-09-12.md
  so its status column is true: COMPLETE only where a file exists on disk,
  with that file's path and byte size beside it; "needs his browser" with
  the URL; UNAVAILABLE with the reason. List separately anything you had
  previously marked complete without a file. Then, at the top, one block
  headed FOR HIS BROWSER: every "needs his browser" item with its URL and
  the subfolder it goes into, so he can fetch them himself in one sitting.
  Then the number of fetches you made and which model you are; his AI
  spend is recorded as a trading expense.

=== NOT ON THE LIST, so you do not add them ===
Any book that is sold: The Mental Game of Trading, Positional Option
Trading, The Daily Trading Coach, and every other paid title in either
research report. His hand. The TradeDiary handbook: unverified, and the site
sells software. YouTube channels: URLs in the top index only, no files.
Anything from a site that is not the publisher's own.

=== THE PAID SHELF, for the top index only ===
In the order both research passes agree on: The Mental Game of Trading
(Tendler); Positional Option Trading (Sinclair); The Daily Trading Coach
(Steenbarger). Later: Technical Analysis Using Multiple Timeframes
(Shannon), Evidence-Based Technical Analysis (Aronson), The PlayBook
(Bellafiore), Option Volatility and Pricing (Natenberg). "Awaiting his copy".
Do not fetch, do not link a seller.
```
