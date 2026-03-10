import os
import json
import time
from werkzeug.security import generate_password_hash, check_password_hash
from arm256_with_aes import arm256_hexdigest  # your custom hash

# ----------------------------
# Create a new user
# ----------------------------
def create_user(username, password, display=None, initial_balance=0.0):
    os.makedirs("users", exist_ok=True)
    os.makedirs("nodes", exist_ok=True)

    user_file = f"users/{username}.json"
    node_file = f"nodes/{username}.json"

    if os.path.exists(user_file):
        return False  # user already exists

    hashed_password = generate_password_hash(password)
    display = display or username

    # User JSON
    user_data = {
        "username": username,
        "display": display,
        "password": hashed_password,
        "balance": initial_balance,
        "transactions": []
    }

    with open(user_file, "w") as f:
        json.dump(user_data, f, indent=4)

    # Node JSON
    node_data = {
        "username": username,
        "balance": initial_balance,
        "txs": []
    }

    with open(node_file, "w") as f:
        json.dump(node_data, f, indent=4)

    return True


# ----------------------------
# Load user
# ----------------------------
def get_user(username):
    user_file = f"users/{username}.json"
    if not os.path.exists(user_file):
        return None
    with open(user_file, "r") as f:
        return json.load(f)

def find_user(username):
    return get_user(username)

# ----------------------------
# Verify login
# ----------------------------
def verify_user(username, password):
    u = get_user(username)
    if not u:
        return False
    return check_password_hash(u.get("password"), password)

# ----------------------------
# Node helpers
# ----------------------------
def load_node(username):
    node_file = f"nodes/{username}.json"
    if not os.path.exists(node_file):
        return None
    with open(node_file, "r") as f:
        return json.load(f)

def save_node(username, data):
    os.makedirs("nodes", exist_ok=True)
    node_file = f"nodes/{username}.json"
    with open(node_file, "w") as f:
        json.dump(data, f, indent=4)

# ----------------------------
# Timestamp helper
# ----------------------------
def now_ms():
    return int(time.time() * 1000)

# ----------------------------
# Canonical hash (ARM256)
# ----------------------------
def canonical_hash(data):
    """
    Use ARM256 custom hash to hash any string or JSON data
    """
    if isinstance(data, dict) or isinstance(data, list):
        data = json.dumps(data, sort_keys=True)
    return arm256_hexdigest(data)

# ----------------------------
# Public / Hyper chain
# ----------------------------
PUBLIC_CHAIN_FILE = "data/public_chain.json"
HYPER_CHAIN_FILE = "data/hyper_chain.json"

os.makedirs("data", exist_ok=True)
for file in [PUBLIC_CHAIN_FILE, HYPER_CHAIN_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({"chain": []}, f, indent=4)

def append_public_proof(block):
    data = json.load(open(PUBLIC_CHAIN_FILE, "r"))
    data.setdefault("chain", []).append(block)
    json.dump(data, open(PUBLIC_CHAIN_FILE, "w"), indent=4)

def append_hyper_record(tx):
    data = json.load(open(HYPER_CHAIN_FILE, "r"))
    data.setdefault("chain", []).append(tx)
    json.dump(data, open(HYPER_CHAIN_FILE, "w"), indent=4)
