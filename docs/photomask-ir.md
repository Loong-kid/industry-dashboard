# Photomask IR library

The former SNS Tech subtab is labelled **포토마스크**. Its existing route
`#/semicon/snstech` and indicator IDs remain compatible. The reader is at
`#/semicon/snstech/ir`; the existing indicator order is unchanged.

The first release contains 32 verified official English PDF links:
HOYA FAQs and earnings-call transcripts for eight fiscal quarters (16 files),
Shin-Etsu conference summaries with Q&A for eight quarters (8 files), and
AGC Q&A for eight reporting periods (8 files). Verified 2026-10-11.
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

`data/semicon/photomask_ir_library.json` is a manually reviewed metadata index.
No automatic refresh, keyword search, excerpts, summaries, or translations
are included. All `translation_status` values are `not_provided`, which is
clearly displayed in the reader. Full literal translations can be added from
user-provided documents; do not describe this source-only release as translated.

The PDF frame loads only when the user clicks **여기서 원문 보기**. The official
PDF link remains available for mobile devices or providers that block framing.
Company, period and source selection are retained across theme rerenders.
Global chart range controls are hidden only in the IR view.
