import sqlite3
import bcrypt
from database.db import get_connection
from config import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH


def register_user(username, full_name, password):
    """Returns (success: bool, message: str)."""
    username = username.strip()
    full_name = full_name.strip()

    if not username or not full_name or not password:
        return False, "All fields are required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters."

    # bcrypt creates and embeds its own random salt inside the hash
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, full_name, pw_hash) VALUES (?,?,?)",
            (username, full_name, pw_hash),
        )
        conn.commit()
        return True, "Registration successful. You can log in now."
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    finally:
        conn.close()


def login_user(username, password):
    """Returns a user dict on success, or None on failure."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    conn.close()

    if row is None:
        return None
    try:
        if bcrypt.checkpw(password.encode("utf-8"), row["pw_hash"]):
            return {"user_id": row["user_id"],
                    "username": row["username"],
                    "full_name": row["full_name"]}
    except ValueError:      # e.g. an over-long password
        pass
    return None