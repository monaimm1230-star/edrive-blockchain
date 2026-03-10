
import argparse, json
from blockchain_json import mine_block

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Mine a public block with PoW and append to JSON chain")
    ap.add_argument("--data", type=str, default="{}", help="JSON string payload for the block's data field")
    ap.add_argument("--difficulty", type=int, default=2, help="PoW difficulty (leading zeros)")
    args = ap.parse_args()
    try:
        payload = json.loads(args.data)
    except Exception:
        payload = {"note": args.data}
    blk = mine_block(payload, difficulty=args.difficulty)
    print(json.dumps(blk, indent=2))
