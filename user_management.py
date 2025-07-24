"""
File: user_management.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024-25). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
"""
from pymongo import MongoClient
from argon2 import PasswordHasher
import re

ph = PasswordHasher()
client = MongoClient('mongodb://localhost:27017/')
db = client["user_db"]
users = db["users"]

def validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search("[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search("[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search("[0-9]", password):
        return "Password must contain at least one digit."
    if not re.search("[!@#$%^&*()\":{}|<>]", password):
        return "Password must contain at least one special character."
    return None

def register_user(email, password):
    if users.find_one({"email": email}):
        return "User already exists."
    password_error = validate_password(password)
    if password_error:
        return password_error
    password_hash = ph.hash(password)
    users.insert_one({"email": email, "password": password_hash})
    return "User registered successfully."
    
def authenticate_user(email, password):
    user = users.find_one({"email": email})
    if user:
        try:
            ph.verify(user['password'], password)
            return True
        except Exception as e:
            print(f"Password verification failed: {e}")
            return False
    else:
        print("User not found.")
        return False