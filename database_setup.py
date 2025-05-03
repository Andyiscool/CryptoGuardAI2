#Add database 04/20 begin
"""
File: database_setup.py
Author: Andy Xiao

Description:
Setup SQLite database for storing encrypted messages.

References:
- GitHub Copilot: GitHub. (2025). Github Copilot. Retrieved from https://github.com/features/copilot
"""
import sqlite3
def create_database():
    connection = sqlite3.connect('encrypted messages.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            encrypted_aes_key BLOB NOT NULL,
            iv BLOB NOT NULL,
            encrypted_message BLOB NOT NULL
        )
    ''')
    connection.commit()
    connection.close()
#Add database 04/20 end
if __name__ == "__main__":
    #04/20/2025 change begin
    create_database()
    #04/20/2025 change end