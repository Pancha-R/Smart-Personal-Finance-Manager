import customtkinter as ctk
from datetime import date
from tkinter import messagebox
from config import APP_NAME, CURRENCY
from services.transactions import get_summary
from services.goals import get_goals
from services.recurring import get_pending
from services.budgets import get_alerts
from ui.theme import (load_logo, add_background, COLOR_INCOME, COLOR_EXPENSE,
                      COLOR_SAVING, COLOR_MUTED)
from ui.transactions_page import TransactionsPage
from ui.recurring_page import RecurringPage
from ui.goals_page import GoalsPage, GoalCard
from ui.budgets_page import BudgetsPage
from ui.reminders import ReminderPanel


class DashboardHome(ctk.CTkFrame):
    def __init__(self, parent, user):
        super().__init__(parent, fg_color="transparent")
        add_background(self)                  # must come first

        uid = user["user_id"]
        s = get_summary(uid, date.today().strftime("%Y-%m"))
        goals = get_goals(uid)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 20))
        ctk.CTkLabel(header, text=f"Welcome, {user['full_name']}",
                     font=("Arial", 24, "bold")).pack(padx=20, pady=8)

        # "Balance" still counts goal money (it isn't spent); "Available" has it set aside.
        self._card("Balance", s["balance"], 0, note="Without considering goal money")
        self._card("Available Balance", s["available"], 1, note="Including goal money")
        self._card("Income (this month)", s["month_income"], 2, COLOR_INCOME)
        self._card("Expenses (this month)", s["month_expense"], 3, COLOR_EXPENSE)
        for c in range(4):
            self.grid_columnconfigure(c, uniform="cards", weight=1)
        self.grid_rowconfigure(2, weight=1)

        #goals
        box = ctk.CTkFrame(self, corner_radius=12)
        box.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=(16, 0))
        ctk.CTkLabel(box, text=f"My Goals  -  {CURRENCY} {s['goal_money']:,.2f} set aside",
                     font=("Arial", 16, "bold"), text_color=COLOR_SAVING
                     ).pack(anchor="w", padx=12, pady=(10, 0))
        strip = ctk.CTkScrollableFrame(box, orientation="horizontal", fg_color="transparent")
        strip.pack(fill="both", expand=True, padx=4, pady=(2, 8))
        if goals:
            for g in goals:
                GoalCard(strip, g).pack(side="left", padx=6, pady=4, anchor="n")
        else:
            ctk.CTkLabel(strip, text="No goals yet. Create one in Goals, or pick the "
                                     "Saving type when adding a transaction.",
                         text_color=COLOR_MUTED, wraplength=380, justify="left"
                         ).pack(padx=10, pady=20)

        #reminders & budget alerts
        ReminderPanel(self, user, on_change=self._reload).grid(
            row=2, column=2, columnspan=2, sticky="nsew", padx=8, pady=(16, 0))

    def _reload(self):
        top = self.winfo_toplevel()
        top.after(10, lambda: top.show_page("Dashboard"))

    def _card(self, title, value, col, color=None, note=None):
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=1, column=col, padx=8, sticky="ew")
        ctk.CTkLabel(card, text=title).pack(pady=(15, 2))
        ctk.CTkLabel(card, text=f"{CURRENCY} {value:,.2f}", text_color=color,
                     font=("Arial", 22, "bold")).pack(pady=(0, 2 if note else 15))
        if note:
            ctk.CTkLabel(card, text=note, text_color=COLOR_MUTED,
                         font=("Arial", 11)).pack(pady=(0, 12))


class Dashboard(ctk.CTk):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.logged_out = False

        self.title(APP_NAME)
        self.geometry("1100x650")
        self.minsize(900, 550)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        #side bar
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")

        logo = load_logo(140)                 #Logo    
        if logo:
            ctk.CTkLabel(sidebar, image=logo, text="").pack(pady=20)
        else:
            ctk.CTkLabel(sidebar, text="SPFM", font=("Arial", 22, "bold")).pack(pady=20)

        # if want to add a page
        self.pages = {
            "Dashboard": DashboardHome,
            "Transactions": TransactionsPage,
            "Receivables and Payables": RecurringPage,
            "Goals": GoalsPage,
            "Budgets": BudgetsPage,
        }
        for name in self.pages:
            ctk.CTkButton(sidebar, text=name, width=160,
                          command=lambda n=name: self.show_page(n)).pack(pady=5, padx=15)

        ctk.CTkButton(sidebar, text="Log out", width=160, fg_color="gray",
                      command=self.logout).pack(side="bottom", pady=20, padx=15)

        #content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.show_page("Dashboard")
        self.after(500, self._startup_reminders)

    def show_page(self, name):
        for w in self.content.winfo_children():
            w.destroy()            # rebuilding a page also reloads its data
        self.pages[name](self.content, self.user).grid(row=0, column=0, sticky="nsew")

    def _startup_reminders(self):
        """One pop-up when the app opens, if something needs the user's attention."""
        uid = self.user["user_id"]
        lines = [f"- {p['title']} ({CURRENCY} {p['amount']:,.2f}) was due {p['due']}"
                 for p in get_pending(uid)]
        if lines:
            lines.insert(0, "These recurring items are waiting for you to confirm "
                            "whether they actually happened:")
        alerts = [text for text, _ in get_alerts(uid)]
        if alerts:
            lines += ["", "Budget alerts:"] + [f"- {a}" for a in alerts]
        if lines:
            messagebox.showinfo("Reminders", "\n".join(lines).strip())

    def logout(self):
        self.logged_out = True
        self.destroy()
