import sqlite3
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent                  # running as the built .exe
else:
    BASE_DIR = Path(__file__).resolve().parent.parent       # running from VS Code / terminal
DB_PATH = BASE_DIR / "spfm.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name: row["amount"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


TRANSACTIONS_SQL = """
    CREATE TABLE {name} (
        tx_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        type         TEXT NOT NULL CHECK(type IN ('Income','Expense','Saving')),
        amount       REAL NOT NULL CHECK(amount > 0),
        category     TEXT NOT NULL,
        date         TEXT NOT NULL,          -- stored as YYYY-MM-DD
        note         TEXT,
        receipt_path TEXT,
        goal_id      INTEGER,                -- Saving: goal being funded
                                             -- Expense: goal the money was spent from
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (goal_id) REFERENCES goals(goal_id) ON DELETE SET NULL
    );
"""


def init_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        pw_hash   BLOB NOT NULL
    );

    CREATE TABLE IF NOT EXISTS budgets (
        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER NOT NULL,
        category  TEXT NOT NULL,
        amount    REAL NOT NULL CHECK(amount > 0),
        month     TEXT NOT NULL,             -- YYYY-MM (a budget applies from this month on)
        UNIQUE(user_id, category, month),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS goals (
        goal_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        name     TEXT NOT NULL,
        target   REAL NOT NULL CHECK(target > 0),
        saved    REAL NOT NULL DEFAULT 0,    -- unused: saved amount is calculated from transactions
        deadline TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS recurring (
        rec_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        type         TEXT NOT NULL DEFAULT 'Expense' CHECK(type IN ('Income','Expense')),
        title        TEXT NOT NULL,
        amount       REAL NOT NULL CHECK(amount > 0),
        category     TEXT NOT NULL,
        day_of_month INTEGER NOT NULL CHECK(day_of_month BETWEEN 1 AND 31),
        start_month  TEXT NOT NULL DEFAULT '',   -- YYYY-MM of the first occurrence
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    -- one row per (recurring item, month) once the user has answered
    -- "did this actually happen?"
    CREATE TABLE IF NOT EXISTS recurring_log (
        rec_id INTEGER NOT NULL,
        ym     TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('confirmed','skipped')),
        tx_id  INTEGER,
        PRIMARY KEY (rec_id, ym),
        FOREIGN KEY (rec_id) REFERENCES recurring(rec_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS reminders (
        reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        type        TEXT NOT NULL,
        due_at      TEXT NOT NULL,
        description TEXT NOT NULL,
        done        INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)
    _ensure_transactions_table(conn)
    _ensure_recurring_columns(conn)
    conn.commit()
    conn.close()


def _ensure_transactions_table(conn):
    """Creates the transactions table, or upgrades an older one (no 'Saving' type /
    no goal_id) while keeping every existing row."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
    ).fetchone()
    if row is None:
        conn.execute(TRANSACTIONS_SQL.format(name="transactions"))
        return
    if "'Saving'" in row["sql"]:
        return                                   # already up to date

    # SQLite can't change a CHECK constraint, so rebuild the table.
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(TRANSACTIONS_SQL.format(name="transactions_new"))
    conn.execute("""INSERT INTO transactions_new
                    (tx_id, user_id, type, amount, category, date, note, receipt_path)
                    SELECT tx_id, user_id, type, amount, category, date, note, receipt_path
                    FROM transactions""")
    conn.execute("DROP TABLE transactions")
    conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def _ensure_recurring_columns(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(recurring)")]
    if "type" not in cols:
        conn.execute("ALTER TABLE recurring ADD COLUMN type TEXT NOT NULL DEFAULT 'Expense'")
    if "start_month" not in cols:
        conn.execute("ALTER TABLE recurring ADD COLUMN start_month TEXT NOT NULL DEFAULT ''")