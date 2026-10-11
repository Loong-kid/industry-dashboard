# Photomask IR library

The former SNS Tech subtab is labelled **포토마스크**. Its existing route
`#/semicon/snstech` and indicator IDs remain compatible. The reader is at
`#/semicon/snstech/ir`; the existing indicator order is unchanged.

The library contains 82 original PDF links and user-supplied Korean Markdown
translations, registered 2026-10-12. Coverage is calendar 2021 Q1–2026 Q2:
HOYA 38 documents, AGC 22 and Shin-Etsu 22 (22 periods per company).
The HOYA FY2022 Q2 FAQ original is Japanese; other originals are English.
PDF bodies were inspected to verify file type, page counts, and AGC meeting
identity/date; none are copied into the public repository.

- [HOYA archive](https://www.hoya.com/en/investor/kessan/)
- [AGC archive](https://www.agc.com/en/ir/library/briefing/index.html)
- [Shin-Etsu archive](https://www.shinetsu.co.jp/en/ir/ir-data/ir-briefing/)

FY starts in April for HOYA and Shin-Etsu, and January for AGC. Every period
also shows actual calendar months. AGC annual results Q&A is labelled annual,
not a standalone Q4 disclosure. AGC's 2026 Q2 archive lists July 28, but the
PDF itself says August 4; retain both in metadata and show the meeting date.
HOYA has a true archive publication timestamp. Shin-Etsu dates are conference
dates, not inferred publication dates or URL upload-directory dates.

`data/semicon/photomask_ir_library.json` is a manually maintained metadata index.
No automatic refresh, keyword search or generated summaries are included.
Korean content is loaded on document selection from `data/semicon/photomask-ir-ko/`.
The registered Markdown bytes match the supplied files; importing does not
translate, rephrase, correct numbers or omit document text. The reader renders
headings, paragraphs, lists, quotes and bold labels without executing source HTML.
File notes remain available in a disclosure panel, and relative source PDF links
resolve to the official PDF. The unchanged Markdown can also be downloaded.

All translations remain marked drafts. The supplied manifest labels 80 as
automatic drafts with sample review and two HOYA FAQs as full-document review.
Show each file's own scope and review note; do not imply that all documents were
manually verified. HOYA transcripts cover Q&A through the end of the document,
not the entire earnings presentation; FAQs and AGC/Shin-Etsu files cover the
whole document. Original PDF page headings are retained for comparison.

To register supplied files again:
`python scripts/import_photomask_translations.py --source <download-folder>`.
The folder must contain `download-manifest.json` and
`ko-translation/translation-manifest.json` with the corresponding Markdown files.
The import checks source URL, source PDF hash, reporting period and file scope
before writing. The source/output folder, original PDFs, combined translations,
extraction/alignment JSON and ZIPs are not part of this release.

The PDF frame loads only when the user clicks **여기서 원문 보기**. The official
PDF link remains available for mobile devices or providers that block framing.
Company, period and source selection are retained across theme rerenders.
Global chart range controls are hidden only in the IR view.
The quarter list scrolls within the desktop sidebar and horizontally on mobile.
Failed translation loads offer retry/download; a slow earlier request cannot
replace the document selected later.
