import customtkinter as ctk
from datetime import date
from config import CURRENCY, BUDGET_WARN_PERCENT
from services.transactions import CATEGORIES
from services.budgets import set_budget, delete_budget, get_budget_status
from ui.theme import add_background, COLOR_INCOME, COLOR_WARN, COLOR_EXPENSE, COLOR_MUTED


class BudgetsPage(ctk.CTkFrame):
    def __init__(self, parent, user):
        super().__init__(parent, fg_color="transparent")
        add_background(self)                 # must come first
        self.user = user
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text=f"Monthly Budgets - {date.today():%B %Y}",
                     font=("Arial", 24, "bold")).pack(padx=20, pady=8)

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", pady=10)
        self.category = ctk.CTkOptionMenu(form, values=CATEGORIES["Expense"], width=150)
        self.category.grid(row=0, column=0, padx=8, pady=8)
        self.amount = ctk.CTkEntry(form, placeholder_text="Monthly budget", width=150)
        self.amount.grid(row=0, column=1, padx=4)
        ctk.CTkButton(form, text="Set budget", width=110,
                      command=self.on_set).grid(row=0, column=2, padx=8)
        self.msg = ctk.CTkLabel(form, text="A budget keeps applying every month until you change it.",
                                text_color=COLOR_MUTED)
        self.msg.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

        self.holder = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.holder.grid(row=2, column=0, sticky="nsew")
        self.holder.grid_columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self):
        for w in self.holder.winfo_children():
            w.destroy()
        statuses = get_budget_status(self.user["user_id"])
        if not statuses:
            ctk.CTkLabel(self.holder, text="No budgets yet - set one above.",
                         text_color=COLOR_MUTED).pack(pady=30)
            return
        for s in statuses:
            pct = s["percent"]
            color = (COLOR_EXPENSE if pct >= 100 else
                     COLOR_WARN if pct >= BUDGET_WARN_PERCENT else COLOR_INCOME)
            row = ctk.CTkFrame(self.holder, corner_radius=10)
            row.pack(fill="x", padx=4, pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=s["category"], font=("Arial", 14, "bold")
                         ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(row, text=f"{CURRENCY} {s['spent']:,.2f} of {s['budget']:,.2f}"
                                   f"  ({pct:.0f}%)", text_color=color
                         ).grid(row=0, column=1, padx=8, pady=(8, 0))
            ctk.CTkButton(row, text="Remove", width=70, height=24, fg_color="gray",
                          command=lambda c=s["category"]: self.on_delete(c)
                          ).grid(row=0, column=2, padx=8, pady=(8, 0))
            bar = ctk.CTkProgressBar(row, progress_color=color)
            bar.set(min(pct / 100, 1))
            bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(6, 10))

    def on_set(self):
        err = set_budget(self.user["user_id"], self.category.get(), self.amount.get())
        if err:
            self.msg.configure(text=err, text_color="red")
            return
        self.amount.delete(0, "end")
        self.msg.configure(text="Budget saved.", text_color="green")
        self.refresh()

    def on_delete(self, category):
        delete_budget(self.user["user_id"], category)
        self.refresh()
