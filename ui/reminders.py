import customtkinter as ctk
from config import CURRENCY
from services.recurring import get_pending, get_upcoming, confirm_recurring, skip_recurring
from services.budgets import get_alerts
from ui.theme import TYPE_COLORS, COLOR_WARN, COLOR_EXPENSE, COLOR_MUTED


class ReminderPanel(ctk.CTkFrame):
    """Recurring items waiting for an answer, bills coming up, and budget alerts.
    `on_change` is called after the user answers so the page can reload."""

    def __init__(self, parent, user, on_change, show_budget=True, height=200):
        super().__init__(parent, corner_radius=12)
        self.user, self.on_change = user, on_change
        uid = user["user_id"]

        ctk.CTkLabel(self, text="Reminders & Alerts",
                     font=("Arial", 16, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        body = ctk.CTkScrollableFrame(self, fg_color="transparent", height=height)
        body.pack(fill="both", expand=True, padx=4, pady=(2, 8))

        pending = get_pending(uid)
        upcoming = get_upcoming(uid)
        alerts = get_alerts(uid) if show_budget else []

        for p in pending:
            self._pending_row(body, p)
        for u in upcoming:
            when = "tomorrow" if u["days_left"] == 1 else f"in {u['days_left']} days"
            ctk.CTkLabel(body, anchor="w", justify="left", wraplength=330,
                         text=f"Upcoming: {u['title']} ({CURRENCY} {u['amount']:,.2f}) "
                              f"is due {when}, {u['due']}",
                         text_color=COLOR_WARN).pack(anchor="w", padx=8, pady=3)
        for text, exceeded in alerts:
            ctk.CTkLabel(body, anchor="w", justify="left", wraplength=330,
                         text=f"Budget alert - {text}",
                         text_color=COLOR_EXPENSE if exceeded else COLOR_WARN
                         ).pack(anchor="w", padx=8, pady=3)
        if not (pending or upcoming or alerts):
            ctk.CTkLabel(body, text="All clear - nothing needs your attention.",
                         text_color=COLOR_MUTED).pack(anchor="w", padx=8, pady=8)

    def _pending_row(self, body, p):
        box = ctk.CTkFrame(body)
        box.pack(fill="x", padx=4, pady=4)
        sign = "+" if p["type"] == "Income" else "-"
        ctk.CTkLabel(box, anchor="w", justify="left", wraplength=330,
                     text=f"{p['title']}  {sign}{CURRENCY} {p['amount']:,.2f}\n"
                          f"was due {p['due']} - did it actually happen?",
                     text_color=TYPE_COLORS[p["type"]]).pack(anchor="w", padx=8, pady=(6, 2))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(anchor="w", padx=6, pady=(0, 6))
        ctk.CTkButton(row, text="Yes, add it", width=100, height=26,
                      command=lambda: self._answer(confirm_recurring, p)).pack(side="left", padx=2)
        ctk.CTkButton(row, text="No, skip", width=80, height=26, fg_color="gray",
                      command=lambda: self._answer(skip_recurring, p)).pack(side="left", padx=2)

    def _answer(self, fn, p):
        fn(self.user["user_id"], p["rec_id"], p["ym"])
        self.on_change()
