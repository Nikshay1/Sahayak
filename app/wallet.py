from sqlalchemy import create_engine, text
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "sahayak.db"

engine = create_engine(f"sqlite:///{DB_PATH}")


MAX_TXN = 2000

def get_balance(user_id: int):
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT balance FROM users WHERE id=:id"),
            {"id": user_id}
        ).fetchone()

        if res is None:
            raise Exception(f"User {user_id} not found in wallet DB")

        return res[0]


def debit(user_id: int, amount: int):
    if amount > MAX_TXN:
        return False, "Amount exceeds limit"

    balance = get_balance(user_id)
    if balance < amount:
        return False, "Insufficient balance"

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET balance = balance - :amt WHERE id=:id"),
            {"amt": amount, "id": user_id}
        )
        conn.execute(
            text("INSERT INTO ledger (user_id, amount, type) VALUES (:id, :amt, 'DEBIT')"),
            {"id": user_id, "amt": amount}
        )
    return True, None
