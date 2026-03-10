import json, os

DATA_DIR = "data"
PUBLIC_FILE = os.path.join(DATA_DIR, "public_chain.json")

with open(PUBLIC_FILE, "r", encoding="utf-8") as f:
    old_chain = json.load(f).get("chain", [])

new_chain = []
for i, block in enumerate(old_chain):
    # Determine previous hash
    prev_hash = "0"*64 if i == 0 else (
        old_chain[i-1].get("curr_hash") or old_chain[i-1].get("proof_hash")
    )
    
    # Determine current hash
    curr_hash = block.get("curr_hash") or block.get("proof_hash")
    
    # Transactions: migrate tx_meta into transactions list
    txs = []
    if "tx_meta" in block:
        txs.append(block["tx_meta"])
    elif "data" in block and "transactions" in block["data"]:
        txs = block["data"]["transactions"]
    
    new_block = {
        "index": i,
        "timestamp": txs[0]["ts"] if txs else int(block.get("timestamp", 0)),
        "prev_hash": prev_hash,
        "curr_hash": curr_hash,
        "data": {
            "transactions": txs
        }
    }
    new_chain.append(new_block)

# Write back
with open(PUBLIC_FILE, "w", encoding="utf-8") as f:
    json.dump({"chain": new_chain}, f, indent=2)

print("✅ Public chain migrated to proper block format!")
