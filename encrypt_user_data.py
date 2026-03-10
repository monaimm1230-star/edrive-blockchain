import os
import json
import uuid
from arm256_with_aes import encrypt_text, decrypt_text

USERS_FILE = "users.json"

# Load existing users
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

# Generate unique user number
def generate_id_no():
    return str(uuid.uuid4())  # Generates unique ID for each user

# Register a new user
def register_user():
    print("=== Register New User ===")
    
    name = input("Enter full name: ").strip()
    password = input("Enter password: ").strip()
    
    id_no = generate_id_no()
    print(f"Assigned User ID No: {id_no}")
    
    # Collect personal info
    user_data = {
        "name": name,
        "cnic": input("Enter CNIC: ").strip(),
        "email": input("Enter email: ").strip(),
        "address": input("Enter address: ").strip(),
        "phone": input("Enter phone: ").strip(),
        "balance": 0.0  # initialize user balance
    }

    # Convert to JSON string
    plaintext = json.dumps(user_data)
    
    # Encrypt with user's password
    encrypted_info = encrypt_text(plaintext, password)
    
    # Store in users dict using id_no as key
    users[id_no] = {
        "name": name,
        "password_encrypted_data": encrypted_info
    }
    
    # Save to users.json
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)
    
    print(f"User '{name}' registered successfully!\n")

# Login user
def login_user():
    print("=== User Login ===")
    id_no = input("Enter your User ID No: ").strip()
    
    if id_no not in users:
        print("User ID not found.\n")
        return
    
    password = input("Enter password: ").strip()
    encrypted_data = users[id_no]["password_encrypted_data"]
    
    try:
        decrypted_text = decrypt_text(encrypted_data, password)
        user_info = json.loads(decrypted_text)
        
        print(f"\n=== Welcome {user_info['name']} ===")
        print("Your Dashboard Info:")
        print(f"CNIC: {user_info['cnic']}")
        print(f"Email: {user_info['email']}")
        print(f"Address: {user_info['address']}")
        print(f"Phone: {user_info['phone']}")
        print(f"Balance: {user_info['balance']}")
        print(f"User ID No: {id_no}\n")
        
    except Exception as e:
        print("Incorrect password or corrupted data.\n")

# Main menu
def main():
    while True:
        print("1. Register User")
        print("2. Login User")
        print("3. Exit")
        choice = input("Choose an option: ").strip()
        
        if choice == "1":
            register_user()
        elif choice == "2":
            login_user()
        elif choice == "3":
            break
        else:
            print("Invalid option. Try again.\n")

if __name__ == "__main__":
    main()
