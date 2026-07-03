import os
import sqlite3

# This script creates the SQLite database and tables.
# Run this once before starting the app to initialize the DB.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'expense_tracker.db')

def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table: id (auto), username (unique), email (unique, Gmail only), mobile (unique), password (hashed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Create expenses table: id (auto), user_id (foreign key), amount (float), category (from list), date (YYYY-MM-DD), description
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create incomes table: id (auto), user_id (foreign key), amount (float), source (from list), date (YYYY-MM-DD), description
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database and tables created successfully!")

if __name__ == "__main__":
    create_database()