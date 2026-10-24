import json
from pathlib import Path
import unittest

from fetch_game_platforms import parse_steam_online

ROOT=Path(__file__).resolve().parents[1]


class PublicPlatforms(unittest.TestCase):
    def test_official_counter_order_and_validation(self):
        r=parse_steam_online('<p>PLAYERS ONLINE 42,000,000 PEAK ONLINE 38,000,000 ONLINE NOW</p>')
        self.assertEqual(r,dict(online_now=38000000,peak_displayed=42000000))
        for text in ['no statistics', 'PLAYERS ONLINE 1,000,000 PEAK ONLINE 5,000,000 ONLINE NOW']:
            with self.assertRaises(ValueError):
                parse_steam_online(text)

    def test_manual_metric_scope_and_comparability(self):
        doc=json.loads((ROOT/'manual/games/platforms.json').read_text(encoding='utf8'))
        for profile in doc['profiles']:
            self.assertTrue(profile['scope'] and profile['model'])
            seen=set();definitions={}
            for row in profile['metrics']:
                key=row['id'],row['period']
                self.assertNotIn(key,seen);seen.add(key)
                self.assertTrue(row['value']>0 and row['url'].startswith('https://') and row['scope'])
                definition=row['unit'],row['kind']
                self.assertEqual(definitions.setdefault(row['id'],definition),definition)
        epic=next(p for p in doc['profiles'] if p['id']=='epic')
        self.assertTrue(all(m['kind']=='spend' for m in epic['metrics'] if m['id']=='store_spend'))


if __name__=='__main__':
    unittest.main()
