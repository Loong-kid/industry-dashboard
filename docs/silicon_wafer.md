# Silicon wafer macro dashboard

Route: `#/semicon/materials/wafer`; legacy `#/semicon/wafer` also works.
Reviewed2026-10-24. Sixteen charts, three original SUMCO figures in one
switchable evidence panel, and a dated six-row supply/operation record.

## Coverage

| Item | Coverage and basis |
| --- | --- |
| SEMI worldwide area |46quarters2015Q1–2026Q2; annual2014–2025 |
| SEMI worldwide revenue |Annual2014–2025, billion USD rounded to0.1 |
| SUMCO |Annual2014–2025, million JPY; quarterly IR actuals2017,2021–2025,2026H1 |
| Siltronic |Annual2014–2025;42quarters2016Q1–2026Q2, million EUR |
| GlobalWafers |Annual revenue/profit2014–2025; cash CAPEX2016–2025;40observed/reconciled quarters, million TWD |
| GlobalWafers monthly |2015Jan–2026Sep,141months; reported million TWD |
| Shin-Etsu |Existing reviewed Electronics Materials series, including separate old business scope |

Annual figures are not divided by four. Financial quarter gaps are explicit
nulls, never zeros or bridged lines. Calendar quarters apply to all three
wafer suppliers. Company original currencies are preserved and never summed.
GlobalWafers and its parent SAS are not double counted. Its2016 SunEdison
Semiconductor acquisition changes the consolidated scope.

## Industry statistics

Public SEMI SMG releases and the [shipment statistics page](https://www.semi.org/en/products-services/market-data/materials/si-shipment-statistics)
provide the actuals. Point references preserve each source. Shipment area
is MSI, million square inches, for semiconductor applications excluding solar.
It measures supplier shipments to customers, not fab wafer starts or chips.
Older releases contain scope/footnote differences; see original vintages.
2015Q2 is the published9M7930 minus Q12637 minus Q32591=2702MSI.
Some annual totals differ from rounded quarterly sums by1MSI; neither is
silently changed. Revenue/area is not presented as an ASP because of mix,
diameter, currency and scope effects. Forecast releases are excluded.

Direct requests to SEMI returned403; the original public releases were
reviewed through the web reader. This initial SEMI snapshot requires review
of new releases; daily automation does not claim to update SEMI actuals.

## Financial extraction and interpretation

`scripts/import_wafer_financials.py` reads reviewed original company PDFs,
their registries and extracted page text, verifying original PDF hashes.
Only facts and provenance are committed, not whole documents. Public issuer
filing copies at TDnet mirrors are still issuer-authored statements.
Two older SUMCO statements were reviewed through cached original filing text
after the PDF host failed; their references explicitly identify that method.

- SUMCO annual CAPEX is cash paid for tangible and intangible assets from
  consolidated cash-flow statements. FY2025 revenue409670, operating profit
  1342, cash CAPEX111033million JPY. Quarterly IR CAPEX is **acceptance basis**,
  not cash:2026Q2 is10000million JPY, H1total19400. Separate views retain this
  distinction. Quarterly IR figures are rounded to0.1billion JPY, converted
  to million JPY; quarter sums can differ from precise annual statements.
- Siltronic CAPEX in key figures is capital expenditure in PP&E and intangible
  assets on an accrual basis. Annual separately reported cash payments are
  retained as a second series where available:2025 investment369.1 versus
  cash380.1million EUR. EBIT is operating profit, not EBITDA. FY2014 uses the
  reported comparative846.0sales and-17.1EBIT, not adjusted SSW results.
  FY2017's quarterly CAPEX cells sum167.9 versus annual123.2; unexplained
  quarter cells are withheld, with annual preserved and a card explanation.
  The2020 annual sales value1207.0 differs from later rounded/restated1207.1;
  the original-year annual and original quarterly observations are retained.
- GlobalWafers uses original consolidated statements. Scanned2017 and2019
  financial pages were OCR-read and visually checked. FY2017 operating
  profit7413.542 is gross profit11807.766 less operating expenses4394.224.
  FY2018 original2019 comparative operating profit17578.051 differs from
  the website's annual-highlight15578; the filing value is used without
  inventing a reconciliation. Cash spending on PPE is used; recent combined
  disclosure includes equipment prepayments. Acquisitions, securities,
  leases and proceeds from disposals are not silently added/netted.
  Q4 flows are annual minus nine-month actuals; cash quarters require the
  actual prior YTD. The English2017Q3 website link actually containsQ2;
  document dates are checked before admitting a period. Missing2014/15
  CAPEX is left absent rather than estimated from operating cash flow.
- Shin-Etsu's Electronics Materials includes photoresists, photomask blanks
  and other materials. It is a supplementary segment reference, not standalone
  silicon-wafer revenue/profit, and not a market-share denominator.

## Customer inventory and supply records

SUMCO2026Q2 original presentation pages7–9 supply three reference images.
The inventory plots have no numerical y-axis, so values are **not digitized**.
Input, purchase, customer inventory and turnover-day legend labels remain in
the original image, with Korean explanations and direct page links. Logic
and memory plots cover2014Q1–2026Q2 and are company estimates, not measured
global totals. They are not finished DRAM/NAND chip inventory. Global range
buttons affect interactive charts, not fixed original figures or record tables.

The supply table keeps publication dates and separates actual reported events
from outlooks. Factory opening, customer qualification, ramp and full capacity
are distinct. A passed target date never automatically becomes completion.
Unquantified utilization comments are never converted into percentages.

## Updating and validation

`python scripts/fetch_silicon_wafer.py` checks the public GlobalWafers monthly
table, validates schema/history, stores `data/_wafer/gw_monthly.json` and rebuilds
charts. Source failure preserves prior data and returns nonzero for visible CI
failure. `--offline` rebuilds deterministically without network.
Financials, SEMI, original-figure vintages and supply records remain reviewed
snapshots in `manual/silicon_wafer.json`; importer preserves the reviewed
nonfinancial fields. Neither daily rebuilds nor monthly checks advance their
financial review dates.

Monthly3MMA requires three consecutive calendar months, and YoY uses the same
calendar month a year earlier. Current-year columns take precedence over
comparative copies. The old2019Nov typo`4.344` is rejected and the public
comparative`4,344` is used. Monthly rounded totals can differ from quarterly
statements; they are not forced to reconcile.

Run `python -m unittest discover -s scripts -p test_silicon_wafer.py` plus the
semiconductor navigation regression and desktop/mobile browser checks.
