import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fetch_natgas as gas

class PriceTests(unittest.TestCase):
    def test_fx_uses_last_observation_not_future_or_stale(self):
        result=gas.convert_ttf([['2026-10-03',34.12],['2026-10-12',34.12]],[['2026-10-01',1.1],['2026-10-02',1.2],['2026-10-13',9]])
        self.assertEqual(result,[['2026-10-03',12.0]])

    def test_spread_requires_both_dates(self):
        self.assertEqual(gas.spread([['2026-10-01',10],['2026-10-02',12]],[['2026-10-02',8]]),[['2026-10-02',4]])

    def test_failure_preserves_old_peer_and_successful_history(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(gas,'OUT_DIR',Path(folder)):
            path=Path(folder)/'test.json'
            path.write_text(json.dumps(dict(series={'US':[['2026-10-01',3]],'Asia':[['2026-10-01',12]]},fetched='2026-10-02')),encoding='utf8')
            gas.save('test','test','USD','daily',{'US':[['2026-10-23',3.5]],'Asia':[]},'test')
            doc=json.loads(path.read_text(encoding='utf8'))
            self.assertEqual(doc['series']['US'],[['2026-10-01',3],['2026-10-23',3.5]])
            self.assertEqual(doc['series']['Asia'],[['2026-10-01',12]])
            self.assertEqual(doc['source_last_dates']['Asia'],'2026-10-01')
            self.assertFalse(doc['collection_status']['ok'])

    def test_no_future_or_missing_price(self):
        self.assertEqual(gas.validate_points([['2026-10-01',3],['2099-01-01',9],['2026-10-02',float('nan')]]),[['2026-10-01',3.0]])

    def test_prices_not_gated_by_other_industry_workflow(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/update-natgas.yml').read_text(encoding='utf8')
        self.assertIn('prices:',workflow)
        self.assertIn('midstream:',workflow)
        self.assertNotIn('needs:',workflow)

if __name__=='__main__':unittest.main()
