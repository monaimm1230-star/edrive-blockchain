import os, json, uuid, time, subprocess, requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_socketio import SocketIO, emit, join_room
from utils import create_user, verify_user, find_user, load_node, save_node, now_ms, canonical_hash, append_public_proof, append_hyper_record

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
socketio = SocketIO(app, cors_allowed_origins="*")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    u = find_user(user_id)
    if not u: return None
    return User(u.get("username"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        display = request.form.get("display") or username
        initial = request.form.get("initial_balance") or "0"
        try:
            initial_balance = float(initial)
        except:
            initial_balance = 0.0
        if not username or not password:
            flash("username and password required", "error")
            return redirect(url_for("register"))
        try:
            create_user(username, password, display, initial_balance)

            # ── Auto-create EC wallet for new user ──
            try:
                from auth_token import create_wallet
                create_wallet(username)
            except Exception as e:
                print(f"[WARN] Could not create EC wallet for {username}: {e}")
            # ─────────────────────────────────────────

            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except ValueError:
            flash("Username already taken", "error")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        if verify_user(username, password):
            user = User(username)
            login_user(user)
            flash("Logged in", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    uname = current_user.username
    node = load_node(uname)
    public = json.load(open(os.path.join("data","public_chain.json"), "r", encoding="utf-8")).get("chain", [])
    hyper = json.load(open(os.path.join("data","hyper_chain.json"), "r", encoding="utf-8")).get("chain", [])
    users = [u.get("username") for u in json.load(open(os.path.join("data","users.json"), "r", encoding='utf-8')).get("users", [])]

    # ── Load EC wallet data ──────────────────────────────────
    ec_balance = 0
    ec_address = ""
    ec_txs = []
    try:
        from auth_token import get_wallet, _read_wallets
        wallet = get_wallet(uname)
        ec_balance = wallet.get("balance", 0)
        ec_address = wallet.get("address", "")
        wallets = _read_wallets()
        ec_txs = list(reversed(wallets.get(uname, {}).get("transactions", [])))[:20]
    except Exception as e:
        print(f"[WARN] Could not load EC wallet: {e}")

    # ── Load energy trades from private chain ────────────────
    energy_trades = []
    try:
        private = json.load(open(os.path.join("data","private_chain.json"), "r", encoding="utf-8")).get("chain", [])
        for block in reversed(private):
            data_field = block.get("data", {})
            txs = data_field.get("transactions", [])
            for tx in txs:
                if tx.get("type") == "energy_trade":
                    energy_trades.append({
                        "tx_id":        tx.get("tx_id", ""),
                        "buyer":        tx.get("buyer", ""),
                        "seller":       tx.get("seller", ""),
                        "units":        tx.get("units", 0),
                        "ec_amount":    tx.get("buyer_paid_ec", 0),
                        "period":       tx.get("period", ""),
                        "block_index":  block.get("index", ""),
                        "timestamp":    tx.get("timestamp", 0),
                    })
            if len(energy_trades) >= 10:
                break
    except Exception as e:
        print(f"[WARN] Could not load energy trades: {e}")
    # ────────────────────────────────────────────────────────

    return render_template(
        "dashboard.html",
        user=uname,
        node=node,
        public_tail=list(reversed(public))[:10],
        hyper_tail=list(reversed(hyper))[:10],
        users=users,
        ec_balance=ec_balance,
        ec_address=ec_address,
        ec_txs=ec_txs,
        energy_trades=energy_trades,
    )

@app.route("/", methods=["GET"])
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/add_balance", methods=["POST"])
@login_required
def add_balance():
    amt = request.form.get("amount") or request.json.get("amount")
    try:
        amt = float(amt)
    except:
        return jsonify({"ok": False, "error": "invalid_amount"}), 400
    if amt <= 0:
        return jsonify({"ok": False, "error": "amount_must_be_positive"}), 400
    uname = current_user.username
    node = load_node(uname)
    node["balance"] = float(node.get("balance",0)) + amt
    save_node(uname, node)
    socketio.emit("balance_added", {"message": f"✅ Balance updated by Rs {amt}", "balance": node["balance"]}, room=uname)
    return jsonify({"ok": True, "balance": node["balance"]})

@app.route("/tx", methods=["POST"])
@login_required
def tx():
    data = request.form or request.get_json() or {}
    from_user = current_user.username
    to_user = (data.get("to_user") or "").strip().lower()
    try:
        amount = float(data.get("amount"))
    except:
        return jsonify({"ok": False, "error": "invalid_amount"}), 400
    note = data.get("note", "")
    if from_user == to_user:
        return jsonify({"ok": False, "error": "cannot_send_to_self"}), 400
    try:
        src = load_node(from_user)
        dst = load_node(to_user)
    except FileNotFoundError as e:
        record = {"id": str(uuid.uuid4()), "kind": "failed", "why": "unknown_node", "detail": str(e), "ts": now_ms()}
        append_hyper_record(record)
        socketio.emit("tx_failed", {"message": f"Transaction failed: unknown node"}, broadcast=True)
        return jsonify({"ok": False, "error": "unknown_node"}), 404
    if src.get("balance", 0) < amount:
        record = {"id": str(uuid.uuid4()), "from": from_user, "to": to_user, "amount": amount, "kind": "failed", "why": "insufficient_funds", "ts": now_ms()}
        append_hyper_record(record)
        socketio.emit("tx_failed", {"message": f"Transaction failed: insufficient funds"}, broadcast=True)
        return jsonify({"ok": False, "error": "insufficient_funds"}), 400
    src["balance"] = src.get("balance", 0) - amount
    dst["balance"] = dst.get("balance", 0) + amount
    txrec = {"id": str(uuid.uuid4()), "from": from_user, "to": to_user, "amount": amount, "note": note, "ts": now_ms()}
    src.setdefault("txs", []).append({**txrec, "direction": "debit"})
    dst.setdefault("txs", []).append({**txrec, "direction": "credit"})
    save_node(from_user, src)
    save_node(to_user, dst)
    payload = {"tx_id": txrec["id"], "from": from_user, "to": to_user, "amount": amount, "ts": txrec["ts"]}
    proof = {"proof_hash": canonical_hash(payload), "tx_meta": {"tx_id": txrec["id"], "ts": txrec["ts"]}}
    append_public_proof(proof)
    socketio.emit("tx", {"message": f"💸 {from_user} sent Rs {amount}", "tx_id": txrec["id"], "proof_hash": proof["proof_hash"]}, broadcast=True)
    return jsonify({"ok": True, "tx_id": txrec["id"], "proof_hash": proof["proof_hash"]})

@socketio.on("join")
def on_join(data):
    username = data.get("username")
    if username:
        join_room(username)

@app.route("/api/state")
def api_state():
    out = {}
    data = json.load(open(os.path.join("data","users.json"), "r", encoding='utf-8'))
    for u in data.get("users", []):
        uname = u.get("username")
        try:
            node = load_node(uname)
            out[uname] = {"balance": node.get("balance", 0), "tx_count": len(node.get("txs", []))}
        except FileNotFoundError:
            out[uname] = {"balance": 0, "tx_count": 0}
    return jsonify(out)

@app.route("/verify/<proof_hash>")
def verify(proof_hash):
    chain = json.load(open(os.path.join("data","public_chain.json"), "r", encoding='utf-8')).get("chain", [])
    found = next((p for p in chain if p.get("proof_hash") == proof_hash), None)
    return jsonify({"ok": bool(found), "proof": found})

from arm256_with_aes import decrypt_text_with_salt
@app.route('/viewer')
@login_required
def viewer():
    try:
        chain_data = []
        chain_obj = None
        for name in ('bc','blockchain','chain','per_tx_chain','per_tx_blockchain'):
            if name in globals():
                chain_obj = globals()[name]
                break
        if chain_obj is None:
            try:
                from blockchain.chain import PerTxBlockchain
                for v in globals().values():
                    if isinstance(v, PerTxBlockchain):
                        chain_obj = v
                        break
            except Exception:
                pass
        if chain_obj is None:
            return render_template('viewer.html', chain_data=[], error='Chain object not found in app context')
        for blk in getattr(chain_obj, 'chain', []):
            decrypted = None
            try:
                dec = None
                try:
                    dec = decrypt_text_with_salt(blk.encrypted_payload, chain_obj.chain_password)
                except Exception as e:
                    try:
                        from arm256_with_aes import decrypt_text
                        dec = decrypt_text(blk.encrypted_payload, chain_obj.chain_password)
                    except Exception:
                        dec = f"Decryption failed: {e}"
                try:
                    decrypted = json.dumps(json.loads(dec), indent=2)
                except Exception:
                    decrypted = dec
            except Exception as e:
                decrypted = f"Decryption failed: {e}"
            chain_data.append({
                "index": getattr(blk, 'index', None),
                "hash": getattr(blk, 'hash', None),
                "encrypted_payload": getattr(blk, 'encrypted_payload', None),
                "decrypted_payload": decrypted,
                "miner": getattr(blk, 'miner', None),
                "timestamp": getattr(blk, 'timestamp', None)
            })
        return render_template('viewer.html', chain_data=chain_data, error=None)
    except Exception as e:
        return f"Viewer error: {e}"


# ==============================================================
# E-CREDIT TOKEN API ENDPOINTS
# ==============================================================

# ── Token API Routes ─────────────────────────────────────────

@app.route("/api/wallet/create", methods=["POST"])
def api_create_wallet():
    try:
        from auth_token import create_wallet
        data = request.get_json() or {}
        username = (data.get("username") or "").strip().lower()
        if not username:
            return jsonify({"success": False, "error": "username required"}), 400
        wallet = create_wallet(username)
        return jsonify({"success": True, "wallet": wallet})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/wallet/<username>", methods=["GET"])
def api_get_wallet(username):
    try:
        from auth_token import get_wallet
        wallet = get_wallet(username)
        return jsonify({"success": True, "wallet": wallet})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/rates", methods=["GET"])
def api_rates():
    try:
        from auth_token import get_rate_info
        return jsonify({"success": True, "rates": get_rate_info()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/cost-preview", methods=["POST"])
def api_cost_preview():
    try:
        from auth_token import calculate_cost
        data = request.get_json() or {}
        units = float(data.get("units", 0))
        seller_price_ec = float(data.get("seller_price_ec", 0))
        if units <= 0 or seller_price_ec <= 0:
            return jsonify({"success": False, "error": "units and seller_price_ec must be positive"}), 400
        cost = calculate_cost(units, seller_price_ec)
        return jsonify({"success": True, "cost": cost})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/trade", methods=["POST"])
def api_trade():
    try:
        from blockchain import process_energy_trade
        data = request.get_json() or {}
        buyer           = (data.get("buyer") or "").strip().lower()
        seller          = (data.get("seller") or "").strip().lower()
        units           = float(data.get("units", 0))
        seller_price_ec = float(data.get("seller_price_ec", 0))
        if not buyer or not seller:
            return jsonify({"success": False, "error": "buyer and seller required"}), 400
        if buyer == seller:
            return jsonify({"success": False, "error": "buyer and seller cannot be same"}), 400
        if units <= 0 or seller_price_ec <= 0:
            return jsonify({"success": False, "error": "units and price must be positive"}), 400

        print(f"[TRADE] Starting trade: {buyer} -> {seller}, {units} units @ {seller_price_ec} EC")
        result = process_energy_trade(buyer, seller, units, seller_price_ec)
        print(f"[TRADE] Done: {result}")
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/wallet/topup", methods=["POST"])
def api_wallet_topup():
    try:
        from auth_token import _read_wallets, _save_wallets
        data = request.get_json() or {}
        username  = (data.get("username") or "").strip().lower()
        amount_ec = float(data.get("amount_ec", 0))
        if not username:
            return jsonify({"success": False, "error": "username required"}), 400
        if amount_ec <= 0:
            return jsonify({"success": False, "error": "amount_ec must be positive"}), 400
        wallets = _read_wallets()
        if username not in wallets:
            return jsonify({"success": False, "error": f"Wallet not found for {username}"}), 404
        wallets[username]["balance"] = round(wallets[username]["balance"] + amount_ec, 2)
        _save_wallets(wallets)
        return jsonify({
            "success": True,
            "username": username,
            "added_ec": amount_ec,
            "new_balance": wallets[username]["balance"]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────────────────────


# ==============================================================


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    host = "0.0.0.0"
    print("\nStarting server on http://localhost:%s" % port)
    socketio.run(app, host=host, port=port, debug=True)