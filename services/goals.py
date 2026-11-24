from datetime import datetime, date
from database.db import get_connection

# Money in a goal = everything saved into it - everything spent from it.
# It is always calculated from the transactions table, so editing or deleting
# a transaction can never leave the goal out of sync.
GOAL_SQL = """
    SELECT g.goal_id, g.name, g.target, g.deadline,
           COALESCE(SUM(CASE WHEN t.type='Saving'  THEN  t.amount
                             WHEN t.type='Expense' THEN -t.amount END), 0) AS current
    FROM goals g
    LEFT JOIN transactions t ON t.goal_id = g.goal_id
    WHERE g.user_id = ?
    GROUP BY g.goal_id
    ORDER BY g.deadline, g.goal_id
"""


def validate_goal(name, target_text, deadline_text):
    """Returns (target, error). error is None when the input is valid."""
    if not name.strip():
        return None, "Goal name is required."
    try:
        target = float(target_text.replace(",", ""))
    except ValueError:
        return None, "Target must be a number."
    if target <= 0:
        return None, "Target must be greater than zero."
    try:
        d = datetime.strptime(deadline_text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "Deadline must be in YYYY-MM-DD format."
    if d < date.today():
        return None, "Deadline can't be in the past."
    return target, None


def add_goal(user_id, name, target_text, deadline_text):
    """Returns (goal_id, error)."""
    target, err = validate_goal(name, target_text, deadline_text)
    if err:
        return None, err
    name = name.strip()
    conn = get_connection()
    try:
        dup = conn.execute(
            "SELECT 1 FROM goals WHERE user_id=? AND LOWER(name)=LOWER(?)", (user_id, name)
        ).fetchone()
        if dup:
            return None, "You already have a goal with that name."
        cur = conn.execute(
            "INSERT INTO goals (user_id, name, target, deadline) VALUES (?,?,?,?)",
            (user_id, name, target, deadline_text.strip()),
        )
        conn.commit()
        return cur.lastrowid, None
    finally:
        conn.close()


def get_goals(user_id):
    """List of dicts: goal_id, name, target, deadline, current, percent (0-100), days_left."""
    conn = get_connection()
    rows = conn.execute(GOAL_SQL, (user_id,)).fetchall()
    conn.close()
    goals = []
    for r in rows:
        g = dict(r)
        g["current"] = max(g["current"], 0.0)
        g["percent"] = min(100.0, g["current"] / g["target"] * 100)
        g["days_left"] = (datetime.strptime(g["deadline"], "%Y-%m-%d").date() - date.today()).days
        goals.append(g)
    return goals


def delete_goal(goal_id, user_id):
    """Deletes the goal. Money saved into it is released back to the available balance;
    expenses that were paid from it stay in the history as normal expenses."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM transactions WHERE goal_id=? AND user_id=? AND type='Saving'",
                     (goal_id, user_id))
        conn.execute("UPDATE transactions SET goal_id=NULL WHERE goal_id=? AND user_id=?",
                     (goal_id, user_id))
        conn.execute("DELETE FROM goals WHERE goal_id=? AND user_id=?", (goal_id, user_id))
        conn.commit()
    finally:
        conn.close()
