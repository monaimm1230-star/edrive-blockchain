import json
import os
from utils import load_node

# -----------------------------
# Paths
# -----------------------------
DATA_DIR = "data"
PUBLIC_CHAIN_FILE = os.path.join(DATA_DIR, "public_chain.json")

# Load public chain
with open(PUBLIC_CHAIN_FILE, "r", encoding="utf-8") as f:
    public_chain = json.load(f).get("chain", [])

# Function to find transaction details from nodes
def find_tx_details(tx_id):
    details = {}
    # Check all nodes in data/users.json
    users_file = os.path.join(DATA_DIR, "users.json")
    with open(users_file, "r", encoding="utf-8") as f:
        users = [u["username"] for u in json.load(f).get("users", [])]

    for user in users + ["miner"]:
        try:
            node = load_node(user)
            # Scan transactions
            for tx in node.get("txs", []):
                if tx.get("id") == tx_id:
                    details[user] = tx
        except FileNotFoundError:
            continue
    return details

# -----------------------------
# Print all public chain transactions with details
# -----------------------------
for entry in public_chain:
    proof_hash = entry.get("proof_hash")
    tx_id = entry.get("tx_meta", {}).get("tx_id")
    ts = entry.get("tx_meta", {}).get("ts")
    print(f"\n=== Transaction {tx_id} ===")
    print(f"Proof Hash: {proof_hash}")
    print(f"Timestamp: {ts}")

    tx_details = find_tx_details(tx_id)
    if not tx_details:
        print("No transaction details found in nodes!")
        continue

    for node, tx in tx_details.items():
        direction = tx.get("direction", "N/A")
        amount = tx.get("amount", 0)
        note = tx.get("note", "")
        gas_fee = tx.get("gas_fee", 0)
        print(f"Node: {node}, Direction: {direction}, Amount: {amount}, Gas Fee: {gas_fee}, Note: {note}")
