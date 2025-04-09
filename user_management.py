"""
File: user_management.py
Author: Andy Xiao

References:
- ChatGPT: OpenAI. (2024, September). ChatGPT. Retrieved from https://chatgpt.com/
- GitHub Copilot: GitHub. (2025, April). Github Copilot. Retrieved from https://github.com/features/copilot
"""
import sqlite3
from argon2 import PasswordHasher
import re
ph = PasswordHasher()
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

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
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email,))
    if c.fetchone():
        conn.close()
        return "User already exists."
    
    password_error = validate_password(password)
    if password_error:
        conn.close()
        return password_error
    
    password_hash = ph.hash(password)
    c.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password_hash))
    conn.commit()
    conn.close()
    return "User registered successfully."
def authenticate_user(email, password):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE email = ?', (email,))
    result = c.fetchone()
    conn.close()
    if result:
        password_hash = result[0]
        try:
            ph.verify(password_hash, password)
            return True
        except Exception as e:
            print(f"Password verification failed: {e}")
            return False
    else:
        print("User not found.")
        return False
if __name__ == "__main__":
    init_db()