# MOCVD

Route: `#/semicon/materials/mocvd` (legacy `#/semicon/mocvd` retained).
First build reviewed 2026-10-09; historical extension reviewed 2026-10-16.

15 charts and 4 searchable disclosure tables. AIXTRON: 2014Q1–2026Q2
(50 quarters). Veeco consolidated revenue: 2014Q1–2026Q2 (50 quarters);
Compound Semiconductor remains 2023Q1–2026Q2 (14 quarters). Coherent revenue,
operating profit and cash CAPEX: FY2014–FY2026 (52 quarters). Lumentum cash
CAPEX: FY2015–FY2026 (48 quarters), plus FY2014 annual disclosure. Infineon:
FY2014–FY2025 annual cash CAPEX/Investments, plus FY2026Q2–Q3 quarterly
disclosures. Annual and quarterly flows have separate card views; Infineon
opens in annual view. No year is divided by four. Fiscal labels use actual
reported dates, including Lumentum's 52/53-week years.

## Historical sources and comparability

`manual/mocvd_history.json` holds factual observations, original filing
accessions, reporting intervals, calculations and source references. SEC
companyfacts could not be downloaded directly in this environment (HTTP403).
The explicitly public [Canli Capital archive](https://canlicapital.com/companies/0000820318)
provides the original compressed SEC JSON, not just selected annual facts.
The importer checks the uncompressed SHA-256 against published metadata and
the CIK (Coherent820318, Lumentum1633978, Veeco103145). Point sources link to
original SEC filings and retain archive URLs/hashes. Only financial facts
and provenance are committed; full documents/source responses stay in tmp.
Quarterly revenue/profit uses actual quarterly contexts, with YTD differences
when absent; cash CAPEX uses cumulative differences. Source vintage is retained;
the data is not a point-in-time investment backtest. Veeco FY2016's latest
annual revenue (331.702m) differs from the older-basis quarter sum (332.450m)
by0.748m following later reporting changes; original observations are not forced
to reconcile by altering a quarter. Only the quarterly revenue series is shown.

- AIXTRON's 32 original [2014–2021 archive PDFs](https://www.aixtron.com/en/investors/publications/archive)
  supply YTD flows and closing balances. The 2014 equipment-order series is
  separate; total orders include spares/service from2015. Book-to-bill therefore
  starts2015. 2017 uses reported results including restructuring effects, not
  adjusted EBIT. EUR-thousand balance-sheet advances are divided by1000.
  AIXTRON applications/order-mix series remain limited to their confirmed scopes.
- Coherent uses the continuing **II-VI → Coherent Corp.** lineage, not the old
  Coherent Inc. target's standalone history. Finisar entered inSeptember2019;
  oldCoherent entered inJuly2022. FY2025 onward lacks an operating-profit
  subtotal: calculate pretax + interest − other net income (the XBRL concept is
  income-positive). This includes restructuring/held-for-sale impairments and
  FY2026 business-sale gain124.133m; it is not adjusted EBITDA. Cross-checked
  [FY2025 annual p.54](https://ir.coherent.com/static-files/b2fab80c-9ae6-4a5e-8954-ae877ef45550#page=56)
  and [FY2026 10-K](https://www.sec.gov/Archives/edgar/data/820318/000082031826000020/iivi-20260630.htm).
- Lumentum FY2014 annual PP&E cash64.2m is a pre-spin combined financial
  disclosure. FY2014 quarterly cash flows are absent; no JDSU company totals
  are substituted. Its later dates are the actual week-based reporting ends.
- Infineon annual cash flows: FY2014 original annual PDFp.203; FY2015–2016
  annual2016 PDFp.133; FY2017–2018 annual2018 PDFp.117 (company-authored reports
  mirrored atAnnualReports); FY2019–2020 annual2020 PDFp.147; FY2021–2022
  standalone consolidated statements2022 PDFp.4; FY2023 annual2023 PDFp.93;
  FY2024–2025 annual2025 PDFp.96. The snapshot retains each URL/page. Investments
  adds cash intangible/other-asset spending, including capitalized development.
  Old quarterly IR tables returned empty HTTP202 responses, so this collection
  does not claim a complete historical quarterly series.

## Sources and scope

- [AIXTRON financial reports](https://www.aixtron.com/en/investors/publications):
  quarterly PDFs, page 2 quarterly financials and balance sheet; equipment
  revenue table contains YTD amounts. Q4 flows = reviewed annual minus 9M.
  Annual reports 2022 p.78–79, 2023 p.82–83, 2024 p.83–84, 2025 p.88–89/95.
  Total orders/revenue include after-sales; backlog excludes it. Book-to-bill
  uses total orders / total revenue, not equipment revenue. FX, cancellations
  and order recognition prevent equating backlog changes to orders.
- Application sales 2022–24 = equipment revenue × rounded disclosed share;
  clearly marked approximate. 2025 exact disclosed Opto 101.4, Power 254.9,
  LED 65.4 million EUR; Other = equipment minus those amounts. Opto is broader
  than InP. The single Q2/26 Opto order share (about 75%) is equipment-only;
  Q1's near-70% total-order share is not put into the same series.
- [Veeco May 2026 presentation, p.27](https://s1.q4cdn.com/522285864/files/doc_presentations/2026/May/Investor-Presentation-May-2026-FINAl.pdf#page=27):
  quarterly end-market table (annual columns excluded), precision 0.1m USD.
  Latest Q2/26 amount from official SEC 10-Q: total193.481, compound20.527m.
  Compound includes MOCVD, etch/wet/IBD and multiple end uses. Not pure MOCVD.
- [Lumentum FY26 10-K](https://www.sec.gov/Archives/edgar/data/1633978/000162828026057358/lite-20260627.htm),
  Q1–Q3 10-Qs: current/comparative cumulative PP&E cash payments. The latest
  eight-quarter manual snapshot is retained; the reviewed archive extends it
  back to FY2015 quarterly/FY2014 annual. FY26 total451.3m.
- [Coherent quarterly releases](https://ir.coherent.com/financial-information/quarterly-results):
  HTML or attached official PDF cash flow Table4. Current/prior-year YTD cash
  PP&E additions; archived exact FY26 total1102.909m and Q4 difference555.681m.
  These round to1102.9/555.7m in the releases and can differ
  from rounded conference-call figures. Both optical company CAPEX series
  include buildings, assembly and other businesses, not just InP equipment.
- [Infineon Q3 FY26, p.3/13](https://www.infineon.com/content/dam/infineon/row/public/documents/corporate/press/2026/infpr202608-125e.pdf):
  cash PP&E456/422 and Investments541/514m EUR for Q2/Q3. Investments includes
  intangible assets/capitalized development; FY26 outlook2700m, stored in the
  dated disclosure table rather than as actual expenditure.
- AMEC [2024 earnings flash](https://star.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-02-28/688012_20250228_VITK.pdf)
  discloses MOCVD379m CNY. [2025 annual, p.65](https://star.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-31/688012_20260331_3UTD.pdf#page=65)
  groups semiconductor equipment products; volume is all dedicated-equipment
  chambers. Do not use those totals as MOCVD revenue or systems shipped.

## Updating

`python scripts/fetch_mocvd.py --backfill` initial archive load;
`python scripts/fetch_mocvd.py` daily AIXTRON/Coherent checks;
`python scripts/fetch_mocvd.py --offline` deterministic rebuild.
Integrated into existing `update-data.yml` schedule. No API key.

To re-import reviewed AIXTRON/SEC source snapshots:
`python scripts/import_mocvd_history.py --source-dir <source-folder> --as-of YYYY-MM-DD`.
The importer validates hashes, entity and availability dates. Infineon reviewed
annuals are preserved. Newly published Coherent revenue/profit and older manual
history require a new source review; the existing daily CAPEX collector can append
later quarters without removing reviewed historical observations.

`data/_mocvd/facts.json` stores parsed values and per-source references.
`manual/mocvd.json` contains reviewed annuals, Veeco latest quarter, Lumentum,
Infineon and dated events. `manual/mocvd_history.json` stores the reviewed
longer history and is loaded by both online and offline builds. These stay
manual until a source-stable collector
is added. Automatic checks do not reset manual review dates. Parser errors
preserve cached observations, log errors and return nonzero. No missing
periods are filled with zero or interpolated. Tests reconcile quarter/year
totals, enforce fiscal dates, reject missing-prior-quarter differencing, and
check catalog/source completeness.

Shipment-series estimates are deferred: no matching model-level equipment
revenue plus credible model ASP range was confirmed. Cumulative 100th
G10-SiC delivery is an event, not quarterly100 shipments. SiC CVD is separate
from InP/GaN MOCVD. Company CAPEX plans/production capacity are forecasts,
not delivered tools. The tables retain publication vintages; elapsed target
dates never imply completion. More suppliers and IQE/LMOC/VPEC can be added
after confirming matching disclosure scopes and primary financial histories.
