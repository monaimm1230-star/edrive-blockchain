
import json
from pathlib import Path

PUB = Path("data/public_chain.json")
PRV = Path("data/private_chain.json")

def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"chain": []}

def print_chain(title, items, keys):
    print(f"\n=== {title} ({len(items)}) ===")
    if not items:
        print("(empty)"); return
    for b in items:
        vals = [str(b.get(k, "")) for k in keys]
        print(" | ".join(vals))

def main():
    pub = _load(PUB)["chain"]
    prv = _load(PRV)["chain"]
    print_chain("Public Blocks", pub, ["index","timestamp","miner","difficulty","nonce","prev_hash","curr_hash"])
    print_chain("Private Records", prv, ["index","timestamp","prev_hash","curr_hash"])

if __name__ == "__main__":
    main()
