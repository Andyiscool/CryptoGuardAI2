"""
File: user_management.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""
from argon2 import PasswordHasher
import re
ph = PasswordHasher()
users = {
    "alice@example.com": ph.hash("securepass"),
    "bob@example.com": ph.hash("password123")
}
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
    if email in users:
        return "User already exists."
    password_error = validate_password(password)
    if password_error:
        return password_error
    users[email] = ph.hash(password)
    return "User registered successfully."
def authenticate_user(email, password):
    if email in users:
        try:
            print(f"Authenticating user: {email}")
            print(f"Stored hash: {users[email]}")
            ph.verify(users[email], password)
            print("Password verified successfully.")
            return True
        except Exception as e:
            print(f"Password verification failed: {e}")
            return False
    print("User not found.")
    return False
