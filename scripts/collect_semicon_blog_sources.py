"""Archive original DART reports for eight newly selected supplier issuers."""
from pathlib import Path
from collect_ring_sources import collect

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    collect(True,cache=root/'.cache/semicon-blog-peers',metadata=root/'manual/semicon-supplychain/blog-20261118.json')
