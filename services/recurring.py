import calendar
from datetime import date, timedelta
from database.db import get_connection
from config import UPCOMING_DAYS


def validate_recurring(title, amount_text, day_text):
    """Returns (amount, day, error)."""
    if not title.strip():
        return None, None, "Title is required."
    try:
        amount = float(amount_text.replace(",", ""))
    except ValueError:
        return None, None, "Amount must be a number."
    if amount <= 0:
        return None, None, "Amount must be greater than zero."
    try:
        day = int(day_text)
    except ValueError:
        return None, None, "Day of month must be a whole number."
    if not 1 <= day <= 31:
        return None, None, "Day of month must be between 1 and 31."
    return amount, day, None


def add_recurring(user_id, type_, title, amount, category, day):
    conn = get_connection()
    conn.execute(
        """INSERT INTO recurring (user_id, type, title, amount, category, day_of_month, start_month)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, type_, title.strip(), amount, category, day, date.today().strftime("%Y-%m")),
    )
    conn.commit()
    conn.close()


def get_recurring(user_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM recurring WHERE user_id=? ORDER BY day_of_month, title",
                        (user_id,)).fetchall()
    conn.close()
    return rows


def delete_recurring(rec_id, user_id):
    conn = get_connection()
    conn.execute("DELETE FROM recurring WHERE rec_id=? AND user_id=?", (rec_id, user_id))
    conn.commit()
    conn.close()


# ---------- date helpers ----------
def _due_date(ym, day):
    """Due date in month `ym`; day 31 in a 30-day month becomes the last day."""
    y, m = map(int, ym.split("-"))
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def _add_months(ym, n):
    y, m = map(int, ym.split("-"))
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _months(start, end):
    ym = start
    while ym <= end:
        yield ym
        ym = _add_months(ym, 1)


def _load(user_id):
    conn = get_connection()
    recs = conn.execute("SELECT * FROM recurring WHERE user_id=?", (user_id,)).fetchall()
    logged = {(r["rec_id"], r["ym"]) for r in conn.execute(
        """SELECT l.rec_id, l.ym FROM recurring_log l
           JOIN recurring r ON r.rec_id = l.rec_id WHERE r.user_id=?""", (user_id,))}
    conn.close()
    return recs, logged


# ---------- reminders ----------
def get_pending(user_id, today=None):
    """Occurrences whose date has arrived but that the user hasn't answered yet
    ("did this transaction actually happen?"). Includes months missed while the app was closed."""
    today = today or date.today()
    cur = today.strftime("%Y-%m")
    recs, logged = _load(user_id)
    pending = []
    for r in recs:
        start = max(r["start_month"] or cur, _add_months(cur, -11))   # look back at most a year
        for ym in _months(start, cur):
            due = _due_date(ym, r["day_of_month"])
            if due <= today and (r["rec_id"], ym) not in logged:
                pending.append({**dict(r), "ym": ym, "due": due})
    pending.sort(key=lambda p: p["due"])
    return pending


def get_upcoming(user_id, days=UPCOMING_DAYS, today=None):
    """Occurrences due within the next `days` days."""
    today = today or date.today()
    cur = today.strftime("%Y-%m")
    recs, logged = _load(user_id)
    limit = today + timedelta(days=days)
    upcoming = []
    for r in recs:
        for ym in (cur, _add_months(cur, 1)):
            due = _due_date(ym, r["day_of_month"])
            if today < due <= limit and (r["rec_id"], ym) not in logged:
                upcoming.append({**dict(r), "ym": ym, "due": due,
                                 "days_left": (due - today).days})
    upcoming.sort(key=lambda p: p["due"])
    return upcoming


def _answer(user_id, rec_id, ym, confirm):
    conn = get_connection()
    try:
        rec = conn.execute("SELECT * FROM recurring WHERE rec_id=? AND user_id=?",
                           (rec_id, user_id)).fetchone()
        if rec is None:
            return False
        if conn.execute("SELECT 1 FROM recurring_log WHERE rec_id=? AND ym=?",
                        (rec_id, ym)).fetchone():
            return False                          # already answered
        tx_id = None
        if confirm:
            cur = conn.execute(
                """INSERT INTO transactions (user_id, type, amount, category, date, note)
                   VALUES (?,?,?,?,?,?)""",
                (user_id, rec["type"], rec["amount"], rec["category"],
                 _due_date(ym, rec["day_of_month"]).isoformat(), f"Recurring: {rec['title']}"))
            tx_id = cur.lastrowid
        conn.execute("INSERT INTO recurring_log (rec_id, ym, status, tx_id) VALUES (?,?,?,?)",
                     (rec_id, ym, "confirmed" if confirm else "skipped", tx_id))
        conn.commit()
        return True
    finally:
        conn.close()


def confirm_recurring(user_id, rec_id, ym):
    """'Yes, it happened': adds the real transaction (dated on the due date)."""
    return _answer(user_id, rec_id, ym, confirm=True)


def skip_recurring(user_id, rec_id, ym):
    """'No, it didn't happen this month': nothing is added, and it stops reminding."""
    return _answer(user_id, rec_id, ym, confirm=False)
