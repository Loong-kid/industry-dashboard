# Natural gas prices and midstream history

Routes: `#/natgas` / `#/natgas/overview` retain the price and LNG dashboard;
`#/natgas/midstream` adds 30 charts (24 financial, six compressor operating).
Initial source review: 2026-10-26.

## Price outage and repair

The committed gas price files had last been fetched on 2026-10-08. Recent
`update-data` runs failed in mineral-company UI validation before the gas step;
the gas step and final data commit were skipped. A separate `update-natgas`
workflow now checks prices and company disclosures in independent jobs daily
at 08:55 KST. It also supports the dashboard refresh button. Its completion
triggers Pages publication. Other industries' failures do not gate either job.

Henry Hub cash uses FRED DHHNGSP, with the EIA original daily XLS as an explicit,
keyless fallback: <https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls>.
Futures retain Yahoo's NG=F, TTF=F and JKM=F public daily histories. These are
front-month futures rather than a common spot-price basket. TTF is converted
from EUR/MWh using 3.412 MMBtu/MWh and the latest preceding EURUSD observation,
never a future FX observation or one over seven days stale.

Each series fails independently. A failed peer retains old dated observations;
successful histories merge without truncating older points. Collection warnings
and every series' latest actual observation date are visible on the card. No
price is forward-filled and no old observation is dated as today. Curves are
dated by their actual quote date, not by the future contract delivery date.
IMF monthly series still require the FRED key; missing keys preserve the prior
published monthly history and explicitly report the failed series.

## Company financials

Source: SEC Company Facts, supplemented by original SEC 10-K/10-Q statements
and Kodiak's IPO prospectus. The source collector follows normal public EDGAR
endpoints, identifies itself and throttles requests. If one issuer fails, its
previous successful history and fetched date are retained. Raw originals go
to `.cache/midstream`, not the published site; parsed facts and references go
to `data/natgas/midstream_state.json` and individual chart documents.

| Company | Financial coverage / scope |
| --- | --- |
| Kinder Morgan (KMI) | Annual 2014–2025, quarters 2014 Q1–2026 Q3; gas, products, terminals and CO2 |
| Williams (WMB) | Annual 2014–2025, quarters through 2026 Q2; gas transport, gathering, processing, marketing |
| Energy Transfer (ET) | Annual 2014–2025, quarters through 2026 Q2; gas, NGL, oil, products and subsidiaries, including USAC |
| Enterprise Products (EPD) | Annual 2014–2025, quarters through 2026 Q2; gas/NGL, oil, petrochemicals and exports |
| Targa Resources (TRGP) | Annual 2014–2025, quarters through 2026 Q2; gas processing, NGL logistics and exports |
| Archrock (AROC) | Annual 2014–2025, quarters through 2026 Q2; continuing US compression/aftermarket and spin-off scope changes |
| Kodiak (KGS) | Annual 2021–2025; revenue quarters from 2021 Q1 (IPO), profit from 2022 Q2 and cash CAPEX from 2022 Q3; other missing quarters remain null |
| USA Compression (USAC) | Annual 2014–2025, quarters through 2026 Q2; CDM and J-W acquisitions change the fleet |

Amounts are original USD millions. Consolidated sales are not gas-only fee
revenue. KMI and WMB use **total Revenues**, not their different ASC 606
customer-revenue note totals. TRGP's older total is tagged
`GasGatheringTransportationMarketingAndProcessingRevenue`; its gas/mineral
component tags are not mistaken for the whole company. ET and USAC must not
be summed because of consolidation. ET's legal/accounting predecessor changes
and Targa's partnership consolidation also limit long-run comparability.

CAPEX is the issuer's cash-flow capital expenditure line: PP&E for most,
productive assets for ET/AROC and newer EPD filings. It excludes separate
business acquisitions, JV/equity investments, noncash leases and asset-sale
proceeds. Do not substitute Williams's much broader productive-asset line or
company guidance for cash PP&E. Growth/sustaining/net CAPEX definitions differ.

AROC does not disclose a GAAP operating-income subtotal. Its card explicitly
shows a **calculated operating subtotal**: revenue less cost of sales, SG&A,
depreciation, impairment, restructuring, restatement and transaction costs.
Asset-sale, other and financing gains/losses are excluded. Inputs and source
filings are retained. Pre-spin global cost statements are rejected where their
revenue basis differs from continuing-US revenue comparatives.

Quarterly cash flows are same-year YTD differences. A Q4 is rebuilt as annual
minus reported nine months only if Q1–Q3 reconcile to that nine-month disclosure.
Materially inconsistent/reclassified quarter metrics are withheld; original
annuals remain. Explicit nulls prevent a continuous line across those gaps,
and each affected card names the years. No annual is divided by four or
unfinished year annualized. Source dates and components are linked in tables.

## Horsepower and utilization

All HP charts are **period-end stocks**, expressed in thousand HP. They have
no annual-sum switch. No available capacity is back-solved from rounded rates.

- AROC: Total available / Total operating HP; source already in thousand HP.
  Coverage 2014 Q4–2026 Q2 (47 observed quarter ends). International/Exterran
  Partners figures are not added to the continuing US fleet.
- KGS: Fleet horsepower / Revenue-generating horsepower, divided by 1,000.
  Active HP from 2021 Q1, with available HP only where directly disclosed.
  IPO tables distinguish quarterly March dates from annual December dates;
  missing capacity in 2021 Q1–Q3 is not inferred. From 2024 Q3 the definition
  includes contracted/firmly committed deployable units; it is not identical
  to AROC's physically operating HP. 2026 Q2 uses the compression infrastructure
  HP columns, never the separately reported power infrastructure MW columns.
- USAC: Total available / Revenue-generating HP, divided by 1,000, 2014 Q1–
  2026 Q2 (50 quarter ends). Available HP may include contracted on-order units,
  so Fleet horsepower is never silently used as a replacement. Company
  utilization includes contracted standby and repair adjustments; the published
  utilization is displayed separately rather than calculated as active/available.

Increases from acquisitions are included in reported totals, not claimed to
be organic growth. Neither total HP nor utilization is a claim of market share.

## Reproduction and checks

```powershell
python scripts/collect_midstream_sources.py --full
python scripts/fetch_midstream.py --offline --full
python scripts/fetch_natgas.py
python -m unittest discover -s scripts -p test_midstream.py
python -m unittest discover -s scripts -p test_natgas_prices.py
```

Normal scheduled `fetch_midstream.py` refreshes structured financial facts and
recent original filings, merging historical HP, IPO revenue and AROC calculation
inputs from the previously successful state. `--full` additionally reviews all
available original filings from 2014. Source review uses official issuer/SEC
facts only; estimates, utilization-derived capacity and fabricated private-company
2014 history are excluded.
