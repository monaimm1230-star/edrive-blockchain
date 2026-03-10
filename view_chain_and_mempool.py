# view_chain_and_mempool.py
import json
import os
from blockchain import get_public_chain, get_pending

DATA_DIR = "data"
PUBLIC_FILE = os.path.join(DATA_DIR, "public_chain.json")

# ------------------------------
# VIEW PUBLIC CHAIN
# ------------------------------
print("=== PUBLIC CHAIN ===\n")

public_chain = get_public_chain()

if not public_chain:
    print("No blocks in the public chain.\n")
else:
    for block in public_chain:
        index = block.get("index")
        ts = block.get("timestamp")
        prev_hash = block.get("prev_hash")
        curr_hash = block.get("curr_hash")
        print(f"--- Block Index: {index} | Timestamp: {ts} ---")
        print(f"Prev Hash: {prev_hash}")
        print(f"Curr Hash: {curr_hash}")
        
        txs = block.get("data", {}).get("transactions", [])
        if not txs:
            print("No transactions in this block.\n")
        else:
            for tx in txs:
                sender = tx.get("sender", "N/A")
                recipient = tx.get("recipient", "N/A")
                amount = tx.get("amount", 0)
                gas_fee = tx.get("gas_fee", 0)
                note = tx.get("note", "")
                print(f"Tx | From: {sender} To: {recipient} Amount: {amount} Gas Fee: {gas_fee} Note: {note}")
            print("\n")

# ------------------------------
# VIEW PENDING TRANSACTIONS
# ------------------------------
print("=== PENDING TRANSACTIONS ===\n")

pending = get_pending()

if not pending:
    print("No pending transactions.\n")
else:
    for tx in pending:
        sender = tx.get("sender", "N/A")
        recipient = tx.get("recipient", "N/A")
        amount = tx.get("amount", 0)
        gas_fee = tx.get("gas_fee", 0)
        note = tx.get("note", "")
        print(f"Tx | From: {sender} To: {recipient} Amount: {amount} Gas Fee: {gas_fee} Note: {note}")
