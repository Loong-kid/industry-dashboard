"""Mineral company prices and actual reported TTM valuation bands."""
import argparse
from fetch_semicon_valuation import ROOT, collect
from fetch_mining_valuation import METHODOLOGY

def run(offline=False):
    return collect(offline, registry_path=ROOT/'manual/specialty-valuation/companies.json',
        out=ROOT/'data/commodities/specialty-valuation',cache=ROOT/'.cache/specialty-valuation',
        kind='specialty_valuation',methodology=METHODOLOGY,collect_time='08:35',
        index_id='specialty_valuation_index',index_filename='specialty_valuation_index.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    run(parser.parse_args().offline)
