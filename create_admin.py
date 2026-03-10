
from utils import create_user, find_user, save_node, load_node
if not find_user("aqib"):
    create_user("aqib", "password123", "Aqib", initial_balance=1000.0)
    print("Created user aqib / password123 with Rs 1000")
else:
    print("User aqib exists")
