from sqlalchemy import create_engine, text
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "sahayak.db"

engine = create_engine(f"sqlite:///{DB_PATH}")

with engine.begin() as conn:   # 🔥 begin() AUTO-COMMITS
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            balance INTEGER
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        INSERT INTO users (id, name, balance)
        VALUES (1, 'Sunita', 1000)
    """))

print("DB initialized")
