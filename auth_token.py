# token.py
import json
import os
import time
import hashlib
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ── Rate Table (Pakistan NEPRA based) ──────────────────
RATE_TABLE = {
    "off_peak": {
        "hours": "10PM - 6AM",
        "pkr_per_unit": 24,
        "ec_per_unit": 2.0,
        "label": "Off-Peak 🟢"
    },
    "shoulder": {
        "hours": "6AM - 6PM",
        "pkr_per_unit": 35,
        "ec_per_unit": 3.5,
        "label": "Shoulder 🟡"
    },
    "peak": {
        "hours": "6PM - 10PM",
        "pkr_per_unit": 50,
        "ec_per_unit": 5.0,
        "label": "Peak 🔴"
    }
}

TOKEN_CONFIG = {
    "name": "E-Credit",
    "symbol": "EC",
    "ec_to_pkr": 10,           # 1 EC = Rs. 10
    "total_supply": 10000000,  # 10 million EC hard cap
    "signup_bonus": 500,       # EC given on signup
    "platform_fee_pct": 1.5,   # 1.5% per transaction
    "seller_bonus": 0.5        # EC bonus per completed trade
}

WALLETS_FILE = os.path.join(DATA_DIR, "wallets.json")

# ── Helpers ────────────────────────────────────────────
def _read_wallets():
    try:
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def _save_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=2)

# ── Period Detection ───────────────────────────────────
def get_current_period():
    now = datetime.now()
    # Weekend = off peak all day
    if now.weekday() >= 5:
        return "off_peak"
    hour = now.hour
    if 18 <= hour < 22:
        return "peak"
    elif 6 <= hour < 18:
        return "shoulder"
    else:
        return "off_peak"

def get_rate_info():
    period = get_current_period()
    return {
        "period": period,
        **RATE_TABLE[period]
    }

# ── Wallet Address Generation ──────────────────────────
def generate_wallet_address(username: str) -> str:
    seed = f"{username}{time.time()}"
    hash_val = hashlib.sha256(seed.encode()).hexdigest()[:16].upper()
    return f"EC-{hash_val}"

# ── Create Wallet (called on user signup) ─────────────
def create_wallet(username: str) -> dict:
    wallets = _read_wallets()
    if username in wallets:
        return wallets[username]  # already exists

    wallet = {
        "username": username,
        "address": generate_wallet_address(username),
        "balance": TOKEN_CONFIG["signup_bonus"],
        "created_at": int(time.time()),
        "transactions": []
    }
    wallets[username] = wallet
    _save_wallets(wallets)
    return wallet

# ── Get Wallet ─────────────────────────────────────────
def get_wallet(username: str) -> dict:
    wallets = _read_wallets()
    if username not in wallets:
        return create_wallet(username)
    return wallets[username]

# ── Calculate Cost ─────────────────────────────────────
def calculate_cost(units: float, seller_price_ec: float) -> dict:
    period = get_current_period()
    rate = RATE_TABLE[period]

    subtotal = units * seller_price_ec
    fee = round(subtotal * (TOKEN_CONFIG["platform_fee_pct"] / 100), 2)
    fee = max(fee, 0.1)   # minimum fee
    fee = min(fee, 10.0)  # maximum fee cap
    total = round(subtotal + fee, 2)
    pkr_equivalent = round(total * TOKEN_CONFIG["ec_to_pkr"], 2)

    return {
        "units": units,
        "seller_price_ec": seller_price_ec,
        "period": period,
        "period_label": rate["label"],
        "platform_rate_ec": rate["ec_per_unit"],
        "subtotal_ec": round(subtotal, 2),
        "fee_ec": fee,
        "total_ec": total,
        "pkr_equivalent": pkr_equivalent
    }

# ── Transfer Tokens ────────────────────────────────────
def transfer_tokens(buyer_username: str, seller_username: str,
                    units: float, seller_price_ec: float) -> dict:
    wallets = _read_wallets()

    # Ensure wallets exist
    if buyer_username not in wallets:
        create_wallet(buyer_username)
        wallets = _read_wallets()
    if seller_username not in wallets:
        create_wallet(seller_username)
        wallets = _read_wallets()

    cost = calculate_cost(units, seller_price_ec)

    # Check buyer balance
    if wallets[buyer_username]["balance"] < cost["total_ec"]:
        return {"success": False, "error": "Insufficient EC balance"}

    timestamp = int(time.time())
    tx_id = hashlib.sha256(
        f"{buyer_username}{seller_username}{timestamp}".encode()
    ).hexdigest()[:16]

    # Debit buyer
    wallets[buyer_username]["balance"] = round(
        wallets[buyer_username]["balance"] - cost["total_ec"], 2
    )
    wallets[buyer_username]["transactions"].append({
        "tx_id": tx_id,
        "type": "debit",
        "amount": cost["total_ec"],
        "units": units,
        "counterparty": seller_username,
        "timestamp": timestamp,
        "period": cost["period"]
    })

    # Credit seller (amount minus fee + bonus)
    seller_receives = round(cost["subtotal_ec"] - cost["fee_ec"] + TOKEN_CONFIG["seller_bonus"], 2)
    wallets[seller_username]["balance"] = round(
        wallets[seller_username]["balance"] + seller_receives, 2
    )
    wallets[seller_username]["transactions"].append({
        "tx_id": tx_id,
        "type": "credit",
        "amount": seller_receives,
        "units": units,
        "counterparty": buyer_username,
        "timestamp": timestamp,
        "period": cost["period"]
    })

    _save_wallets(wallets)

    return {
        "success": True,
        "tx_id": tx_id,
        "buyer": buyer_username,
        "seller": seller_username,
        "units": units,
        "buyer_paid_ec": cost["total_ec"],
        "seller_received_ec": seller_receives,
        "fee_ec": cost["fee_ec"],
        "pkr_equivalent": cost["pkr_equivalent"],
        "period": cost["period"],
        "timestamp": timestamp
    }