from datetime import date
from database.db import get_connection
from config import BUDGET_WARN_PERCENT


def set_budget(user_id, category, amount_text):
    """Sets the monthly budget for a category, starting this month. Returns error or None."""
    try:
        amount = float(amount_text.replace(",", ""))
    except ValueError:
        return "Budget must be a number."
    if amount <= 0:
        return "Budget must be greater than zero."
    month = date.today().strftime("%Y-%m")
    conn = get_connection()
    conn.execute(
        """INSERT INTO budgets (user_id, category, amount, month) VALUES (?,?,?,?)
           ON CONFLICT(user_id, category, month) DO UPDATE SET amount=excluded.amount""",
        (user_id, category, amount, month))
    conn.commit()
    conn.close()
    return None


def delete_budget(user_id, category):
    conn = get_connection()
    conn.execute("DELETE FROM budgets WHERE user_id=? AND category=?", (user_id, category))
    conn.commit()
    conn.close()


def get_budget_status(user_id, month=None):
    """One dict per budgeted category for `month`: category, budget, spent, percent.
    A budget keeps applying to every later month until you change it."""
    month = month or date.today().strftime("%Y-%m")
    conn = get_connection()
    budgets = conn.execute(
        """SELECT b.category, b.amount FROM budgets b
           WHERE b.user_id = ? AND b.month = (SELECT MAX(month) FROM budgets
                                              WHERE user_id = b.user_id
                                                AND category = b.category AND month <= ?)
           ORDER BY b.category""", (user_id, month)).fetchall()
    spent = {r["category"]: r["total"] for r in conn.execute(
        """SELECT category, SUM(amount) AS total FROM transactions
           WHERE user_id=? AND type='Expense' AND date >= ? AND date <= ?
           GROUP BY category""", (user_id, f"{month}-01", f"{month}-31"))}
    conn.close()
    return [{"category": b["category"], "budget": b["amount"],
             "spent": spent.get(b["category"], 0.0),
             "percent": spent.get(b["category"], 0.0) / b["amount"] * 100}
            for b in budgets]


def get_alerts(user_id):
    """Budgets at or above the warning level this month: [(message, exceeded)]."""
    alerts = []
    for s in get_budget_status(user_id):
        if s["percent"] >= 100:
            alerts.append((f"{s['category']}: budget exceeded "
                           f"({s['spent']:,.2f} of {s['budget']:,.2f})", True))
        elif s["percent"] >= BUDGET_WARN_PERCENT:
            alerts.append((f"{s['category']}: {s['percent']:.0f}% of budget used "
                           f"({s['spent']:,.2f} of {s['budget']:,.2f})", False))
    return alerts


def budget_warning(user_id, category, date_text):
    """Message if an expense in `category` on `date_text` put it near/over budget, else None."""
    for s in get_budget_status(user_id, date_text[:7]):
        if s["category"] == category:
            if s["percent"] >= 100:
                return f"Budget exceeded for {category} ({s['spent']:,.2f} of {s['budget']:,.2f})."
            if s["percent"] >= BUDGET_WARN_PERCENT:
                return f"{category} has used {s['percent']:.0f}% of its monthly budget."
    return None
