# blockchain.py
import json
import os
import time
import random
from typing import Dict, Any, List, Optional

# ------------------------------
# IMPORT CUSTOM ARM HASH
# ------------------------------
from arm256_with_aes import arm256_hexdigest as arm256  # your custom hashing algorithm

# ------------------------------
# FILE LOCATIONS
# ------------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

PUBLIC_FILE = os.path.join(DATA_DIR, "public_chain.json")
PRIVATE_FILE = os.path.join(DATA_DIR, "private_chain.json")
MINERS_FILE = os.path.join(DATA_DIR, "miners.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending_transactions.json")

# ------------------------------
# BASIC JSON READ/WRITE HELPERS
# ------------------------------
def _read(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if path == PENDING_FILE:
            return []
        return {"chain": []}

def _write(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ------------------------------
# CANONICAL HASH — USING ARM256
# ------------------------------
def canonical_hash(obj: Dict[str, Any]) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return arm256(s)

# ------------------------------
# CHAIN HELPERS
# ------------------------------
def last_hash(chain: Dict[str, Any]) -> str:
    if not chain["chain"]:
        return "0" * 64
    last = chain["chain"][-1]
    # Handle both old format (curr_hash) and any other format
    for key in ["curr_hash", "hash", "block_hash"]:
        if key in last:
            return last[key]
    return "0" * 64

def pick_miner() -> str:
    try:
        with open(MINERS_FILE, "r", encoding="utf-8") as f:
            miners = json.load(f)
        return random.choice(miners)
    except Exception:
        return "miner-local"

# ------------------------------
# MEMPOOL (PENDING TRANSACTIONS)
# ------------------------------
def get_pending() -> List[Dict[str, Any]]:
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_pending(pending: List[Dict[str, Any]]):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2)

def add_transaction(tx: Dict[str, Any]) -> bool:
    """
    Add a transaction to the mempool.
    Required fields: sender, recipient, amount
    Optional: timestamp, gas_fee
    """
    required = {"sender", "recipient", "amount"}
    if not required.issubset(tx.keys()):
        raise ValueError("Transaction missing required fields: sender, recipient, amount")
    
    tx_copy = dict(tx)
    
    if "timestamp" not in tx_copy:
        tx_copy["timestamp"] = int(time.time())
    
    # Add default gas_fee if not provided
    if "gas_fee" not in tx_copy:
        tx_copy["gas_fee"] = 0.1  # default fee
    
    pending = get_pending()
    pending.append(tx_copy)
    save_pending(pending)
    return True

# ------------------------------
# PRIVATE CHAIN FUNCTION
# ------------------------------
def add_private(cipher_blob: Dict[str, Any]) -> Dict[str, Any]:
    chain = _read(PRIVATE_FILE)
    record = {
        "index": len(chain["chain"]),
        "timestamp": int(time.time()),
        "prev_hash": "0" * 64 if not chain["chain"] else chain["chain"][-1]["curr_hash"],
        "payload": cipher_blob,
    }
    record["curr_hash"] = canonical_hash(record)
    chain["chain"].append(record)
    _write(PRIVATE_FILE, chain)
    return record

# ------------------------------
# PUBLIC CHAIN: MINE BLOCK FROM MEMPOOL
# ------------------------------
def mine_block(difficulty: int = 2, miner_address: Optional[str] = None, reward: float = 1.0) -> Dict[str, Any]:
    chain = _read(PUBLIC_FILE)
    pending = get_pending()

    miner = miner_address or pick_miner()
    
    # Coinbase includes sum of gas fees
    total_gas = sum(tx.get("gas_fee", 0) for tx in pending)
    coinbase = {
        "sender": "NETWORK_REWARD",
        "recipient": miner,
        "amount": reward + total_gas,
        "timestamp": int(time.time()),
        "note": "coinbase"
    }

    txs_for_block = pending.copy()
    data = {"transactions": [coinbase] + txs_for_block} if txs_for_block else {"transactions": [coinbase]}

    header = {
        "index": len(chain["chain"]),
        "timestamp": int(time.time()),
        "prev_hash": last_hash(chain),
        "difficulty": int(difficulty),
        "miner": miner,
        "nonce": 0,
    }

    target = "0" * header["difficulty"]

    while True:
        to_hash = {"header": header, "data": data}
        h = canonical_hash(to_hash)
        if h.startswith(target):
            block = {
                **header,
                "data": data,
                "curr_hash": h,
            }
            chain["chain"].append(block)
            _write(PUBLIC_FILE, chain)
            _remove_included_from_pending(txs_for_block)
            return block
        header["nonce"] += 1

# ------------------------------
# REMOVE INCLUDED TXS FROM MEMPOOL
# ------------------------------
def _remove_included_from_pending(included_txs: List[Dict[str, Any]]):
    pending = get_pending()
    if not pending:
        return
    new_pending = [tx for tx in pending if tx not in included_txs]
    save_pending(new_pending)

# ------------------------------
# READERS
# ------------------------------
def get_public_chain() -> List[Dict[str, Any]]:
    return _read(PUBLIC_FILE)["chain"]

def get_private_chain() -> List[Dict[str, Any]]:
    return _read(PRIVATE_FILE)["chain"]

# ------------------------------
# ENERGY TRADE PIPELINE
# Calls token.py for EC transfer, then records on both chains
# ------------------------------
def process_energy_trade(buyer: str, seller: str,
                          units: float, seller_price_ec: float) -> Dict[str, Any]:
    """
    Full pipeline for an energy trade:
      1. Transfer EC tokens (buyer -> seller) via token.py
      2. Add transaction to mempool (goes onto public chain when mined)
      3. Add encrypted record to private chain immediately

    Args:
        buyer:           username of the buyer
        seller:          username of the seller
        units:           number of energy units being traded
        seller_price_ec: price per unit in EC set by the seller

    Returns:
        dict with success status, tx_id, balances, and chain record
    """
    # Lazy import to avoid circular dependency issues
    from auth_token import transfer_tokens

    # Step 1 — Transfer EC tokens between wallets
    result = transfer_tokens(buyer, seller, units, seller_price_ec)

    if not result["success"]:
        # Token transfer failed (e.g. insufficient balance) — stop here
        return result

    # Step 2 — Add to mempool so it gets included in the next mined public block
    add_transaction({
        "sender":          buyer,
        "recipient":       seller,
        "amount":          result["buyer_paid_ec"],   # EC amount paid
        "gas_fee":         result["fee_ec"],           # platform fee as gas
        "units":           units,
        "period":          result["period"],           # peak / shoulder / off_peak
        "tx_id":           result["tx_id"],
        "pkr_equivalent":  result["pkr_equivalent"],
        "timestamp":       result["timestamp"]
    })

    # Step 3 — Write encrypted full details to private chain immediately
    private_record = add_private({
        "tx_id":           result["tx_id"],
        "buyer":           buyer,
        "seller":          seller,
        "units":           units,
        "seller_price_ec": seller_price_ec,
        "buyer_paid_ec":   result["buyer_paid_ec"],
        "seller_recv_ec":  result["seller_received_ec"],
        "fee_ec":          result["fee_ec"],
        "pkr_equivalent":  result["pkr_equivalent"],
        "period":          result["period"],
        "timestamp":       result["timestamp"]
    })

    # Return everything the app needs to display confirmation
    # Step 4 — Auto mine the mempool into a public block
    # Step 4 — Auto mine the mempool into a public block
    try:
        print("⛏️  Starting auto-mine...")
        mined = mine_block(difficulty=2)
        print(f"⛏️  Mined block keys: {list(mined.keys())}")  # show us the keys
        public_block_index = mined.get("index")
        public_block_hash  = mined.get("curr_hash") or mined.get("hash") or mined.get("block_hash")
        print(f"⛏️  Auto-mined block #{public_block_index}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[WARN] Auto-mine failed: {e}")
        public_block_index = None
        public_block_hash  = None


    # Return everything the app needs to display confirmation
    return {
        **result,
        "private_block_index": private_record["index"],
        "private_block_hash":  private_record["curr_hash"],
        "public_block_index":  public_block_index,
        "public_block_hash":   public_block_hash,
        "message": (
            f"Trade confirmed. {units} units transferred from {seller} to {buyer}. "
            f"{result['buyer_paid_ec']} EC deducted. "
            f"Recorded on private chain (block {private_record['index']}) "
            f"and mined into public block #{public_block_index}."
        )
    }


# ------------------------------
# QUICK STATUS (for testing)
# ------------------------------
if __name__ == "__main__":
    pub = _read(PUBLIC_FILE)
    priv = _read(PRIVATE_FILE)
    pend = get_pending()
    print("PUBLIC blocks:", len(pub.get("chain", [])))
    print("PRIVATE records:", len(priv.get("chain", [])))
    print("PENDING txs:", len(pend))
