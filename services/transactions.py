from datetime import datetime
from database.db import get_connection

TYPES = ["Income", "Expense", "Saving"]

CATEGORIES = {
    "Income":  ["Salary", "Freelance", "Gift", "Other Income"],
    "Expense": ["Food", "Transport", "Rent", "Utilities",
                "Subscriptions", "Shopping", "Health", "Other"],
    "Saving":  ["Savings"],          # a Saving is always linked to a goal
}

# How the three money figures relate:
#   Balance   = Income - Expense                  (goal money still counted: it isn't spent)
#   In goals  = Saving - Expense paid from goals
#   Available = Balance - In goals                (what is free to spend)


def validate_transaction(amount_text, date_text):
    """Returns (amount, error). error is None when the input is valid."""
    try:
        amount = float(amount_text.replace(",", ""))
    except ValueError:
        return None, "Amount must be a number."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        return None, "Date must be in YYYY-MM-DD format."
    return amount, None


# ---------- safety checks (run inside the same DB transaction as the change) ----------
def _available(conn, user_id):
    r = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN type='Income' THEN amount END), 0) AS inc,
               COALESCE(SUM(CASE WHEN type='Expense' AND goal_id IS NULL THEN amount END), 0) AS exp_free,
               COALESCE(SUM(CASE WHEN type='Saving' THEN amount END), 0) AS sav
        FROM transactions WHERE user_id=?""", (user_id,)).fetchone()
    return r["inc"] - r["exp_free"] - r["sav"]


def _problem(conn, user_id, check_available):
    """Returns an error message if the data is now inconsistent, else None."""
    for g in conn.execute("""
        SELECT g.name,
               COALESCE(SUM(CASE WHEN t.type='Saving' THEN t.amount
                                 WHEN t.type='Expense' THEN -t.amount END), 0) AS cur
        FROM goals g LEFT JOIN transactions t ON t.goal_id = g.goal_id
        WHERE g.user_id=? GROUP BY g.goal_id""", (user_id,)):
        if g["cur"] < -0.005:
            return f"The goal \"{g['name']}\" doesn't have enough money saved for that."
    if check_available and _available(conn, user_id) < -0.005:
        return "Not enough available balance to save that amount."
    return None


def _run(user_id, action, check_available=False):
    """Applies `action(conn)`, verifies the result, and rolls back if it breaks a rule.
    Returns (ok, message)."""
    conn = get_connection()
    try:
        action(conn)
        msg = _problem(conn, user_id, check_available)
        if msg:
            conn.rollback()
            return False, msg
        conn.commit()
        return True, ""
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _prepare(conn, user_id, type_, category, goal_id):
    """Normalises category/goal for the type. Returns (category, goal_id, error)."""
    if type_ == "Income":
        goal_id = None
    if type_ == "Saving":
        category = "Savings"
        if goal_id is None:
            return category, None, "Choose a goal to save into."
    if goal_id is not None:
        ok = conn.execute("SELECT 1 FROM goals WHERE goal_id=? AND user_id=?",
                          (goal_id, user_id)).fetchone()
        if not ok:
            return category, None, "That goal no longer exists."
    return category, goal_id, None


# ---------- CRUD ----------
def add_transaction(user_id, type_, amount, category, date, note="", goal_id=None,
                    receipt_path=None):
    """Returns (ok, message)."""
    def action(conn):
        cat, gid, err = _prepare(conn, user_id, type_, category, goal_id)
        if err:
            raise ValueError(err)
        conn.execute(
            """INSERT INTO transactions
               (user_id, type, amount, category, date, note, receipt_path, goal_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, type_, amount, cat, date, note, receipt_path, gid),
        )
    try:
        return _run(user_id, action, check_available=(type_ == "Saving"))
    except ValueError as e:
        return False, str(e)


def update_transaction(tx_id, user_id, type_, amount, category, date, note="", goal_id=None):
    """Returns (ok, message)."""
    def action(conn):
        cat, gid, err = _prepare(conn, user_id, type_, category, goal_id)
        if err:
            raise ValueError(err)
        conn.execute(
            """UPDATE transactions
               SET type=?, amount=?, category=?, date=?, note=?, goal_id=?
               WHERE tx_id=? AND user_id=?""",
            (type_, amount, cat, date, note, gid, tx_id, user_id),
        )
    try:
        return _run(user_id, action, check_available=(type_ == "Saving"))
    except ValueError as e:
        return False, str(e)


def delete_transaction(tx_id, user_id):
    """Returns (ok, message)."""
    return _run(user_id, lambda conn: conn.execute(
        "DELETE FROM transactions WHERE tx_id=? AND user_id=?", (tx_id, user_id)))


def get_transactions(user_id, keyword="", start=None, end=None, category=None):
    sql = """SELECT t.*, g.name AS goal_name
             FROM transactions t LEFT JOIN goals g ON g.goal_id = t.goal_id
             WHERE t.user_id = ?"""
    params = [user_id]
    if keyword:
        sql += " AND (t.note LIKE ? OR t.category LIKE ? OR g.name LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if start:
        sql += " AND t.date >= ?"
        params.append(start)
    if end:
        sql += " AND t.date <= ?"
        params.append(end)
    if category:
        sql += " AND t.category = ?"
        params.append(category)
    sql += " ORDER BY t.date DESC, t.tx_id DESC"

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_totals(user_id, start=None, end=None):
    """Returns (total_income, total_expense), optionally within a date range."""
    sql = "SELECT type, SUM(amount) AS total FROM transactions WHERE user_id = ?"
    params = [user_id]
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    sql += " GROUP BY type"

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    totals = {r["type"]: r["total"] for r in rows}
    return totals.get("Income", 0), totals.get("Expense", 0)


def get_summary(user_id, month=None):
    """All the dashboard numbers in one place. `month` is 'YYYY-MM' (default: nothing)."""
    conn = get_connection()
    r = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN type='Income' THEN amount END), 0)  AS income,
               COALESCE(SUM(CASE WHEN type='Expense' THEN amount END), 0) AS expense,
               COALESCE(SUM(CASE WHEN type='Saving' THEN amount END), 0)  AS saving,
               COALESCE(SUM(CASE WHEN type='Expense' AND goal_id IS NOT NULL
                                 THEN amount END), 0)                     AS goal_spent
        FROM transactions WHERE user_id=?""", (user_id,)).fetchone()
    summary = {
        "balance": r["income"] - r["expense"],                   # goal money NOT removed
        "goal_money": r["saving"] - r["goal_spent"],             # earmarked, not spent
    }
    summary["available"] = summary["balance"] - summary["goal_money"]

    m = {"income": 0.0, "expense": 0.0, "saving": 0.0}
    if month:
        for row in conn.execute("""SELECT type, SUM(amount) AS total FROM transactions
                                   WHERE user_id=? AND date >= ? AND date <= ?
                                   GROUP BY type""",
                                (user_id, f"{month}-01", f"{month}-31")):
            m[row["type"].lower()] = row["total"]
    conn.close()
    summary.update(month_income=m["income"], month_expense=m["expense"],
                   month_saving=m["saving"])
    return summary
