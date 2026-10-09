# MOCVD

Route: `#/semicon/mocvd`. First build reviewed 2026-10-09.

13 charts and 4 searchable disclosure tables. AIXTRON: 2022Q1–2026Q2
(18 quarters), Veeco: 2023Q1–2026Q2 (14 quarters), Coherent cash CAPEX:
FY2024–FY2026 (12 quarters), Lumentum: FY2025–FY2026 (8 quarters).
Infineon initial snapshot: FY2026Q2–Q3. Fiscal labels use the reported dates;
Lumentum's June 27 is not relabelled June 30.

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
  Q1–Q3 10-Qs: current/comparative cumulative PP&E cash payments. Eight
  quarterly amounts derive from year-to-date differences; FY26 total451.3m.
- [Coherent quarterly releases](https://ir.coherent.com/financial-information/quarterly-results):
  HTML or attached official PDF cash flow Table4. Current/prior-year YTD cash
  PP&E additions; FY26 total1102.9m. Quarterly Q4 difference555.7m can differ
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

`data/_mocvd/facts.json` stores parsed values and per-source references.
`manual/mocvd.json` contains reviewed annuals, Veeco latest quarter, Lumentum,
Infineon and dated events. These stay manual until a source-stable collector
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
