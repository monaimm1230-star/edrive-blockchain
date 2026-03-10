
# Final Hybrid Blockchain App (with Add Balance and Improved GUI)

Features:
- Register with optional initial balance
- Logged-in users can Add Balance (not logged as transactions)
- Transactions are still recorded privately and backed by public proofs
- Notifications: logged-in users see tx notifications (sender + amount only)
- Socket.IO real-time updates; balance-added events go only to the user
- Simple modern GUI

Quickstart:
1. Create venv and install deps:
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
2. Create admin user (optional):
   python create_admin.py
3. Run:
   python app.py
4. Open http://localhost:5050
