# THE LIBRARY CONVERT PROMPT, for Antigravity. Phase three: PDF to markdown, verbatim, page by page.

> Written 2026-09-12 night by the AI partner chat, the mentor. The Library
> exists and was verified on the disk (`docs/PLAN.md` §2.17.15). This turns
> each PDF into text his vault and his partner can read, without touching
> the PDFs. His vault chat links the notes afterwards.
>
> **Copy everything inside the fence and paste it into Antigravity.** A copy
> sits in his vault at `00 - Developer Logs/ANTIGRAVITY_PROMPT - Library
> Convert.md`.

---

```
CONVERSION RUN for the trading library of Abhishek Sikka. You are turning
PDFs already on his disk into markdown text so his Obsidian vault and his
AI partner can read and cite them. You download nothing and you delete
nothing. Read the whole brief before you start.

WHERE. G:\My Drive\Second Brain\03 - Knowledge\Trading\Library\
Nineteen item folders exist, each with one or more PDFs and an _index.md.
Work only inside these folders. Touch nothing else in the vault.

WHAT TO PRODUCE. For every PDF, one markdown file beside it with the same
name and the extension .md, holding the PDF's text VERBATIM.
  - Page by page, in order, each page opened by a line
    `<!-- page N of M -->` so a fact can be traced to its page.
  - The text as extracted. No summarising, no paraphrase, no "cleaning" that
    changes a number, a date, a rupee sign or a circular reference. Fix only
    line breaks inside a sentence and obvious hyphenation at line ends.
  - Tables kept as tables where the extraction preserves them, otherwise
    kept as the row text with a note `<!-- table, layout lost -->`.
  - A header at the top of each markdown: the PDF file name, its byte size,
    its page count, the official URL from _index.md, the date converted,
    and the extraction tool and version you used.
  - The PDF stays where it is, unchanged. The markdown is a reading copy;
    the PDF remains the source of record.

WHAT NOT TO DO.
  - Never write a number that is not in the PDF. If a page extracts as
    empty, write `<!-- page N of M: no text layer -->` and move on. Two
    files are already known to have no text layer: A6's
    Income_Tax_STT_Rules_Schedule.pdf and possibly parts of A5. Say so; do
    not OCR guesses into the file. If an OCR tool is available, you may
    add a SEPARATE file named <name>.ocr.md, clearly headed as OCR output,
    never merged into the verbatim file.
  - Do not touch any _index.md except to add one line at the bottom:
    `Reading copy: <name>.md, N pages, converted <date>`.
  - Do not convert the three NSE Market Pulse issues in full; they are 330
    to 395 pages each and mostly charts. For each, convert only the
    contents page and the sections headed F&O, market statistics and macro
    indicators, and say in the header which pages you converted and which
    you skipped.
  - Do not rename, move or delete anything.

VERIFY EACH FILE AFTER WRITING IT. Count the page markers; the count must
equal the PDF's page count. Open the markdown and confirm the first and
last pages carry text that appears at the start and end of the PDF. Record
both checks in the report.

AT THE END write ONE report to
G:\My Drive\Second Brain\00 - Developer Logs\LIBRARY_CONVERT_2026-09-12.md
listing every markdown written with its path, page count and byte size,
every page with no text layer, every Market Pulse page range converted and
skipped, any PDF that failed to open (the NISM 220-page workbook has a
malformed object inside it; report whether extraction still worked), the
tool used, the number of files processed, and which model you are.
```
