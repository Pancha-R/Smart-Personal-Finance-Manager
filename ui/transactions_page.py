import customtkinter as ctk
from datetime import date
from tkinter import ttk, messagebox
from config import CURRENCY
from services.transactions import (
    CATEGORIES, TYPES, validate_transaction, add_transaction,
    update_transaction, delete_transaction, get_transactions, get_summary,
)
from services.goals import get_goals
from services.budgets import budget_warning
from ui.goals_page import GoalDialog
from ui.theme import add_background, TYPE_COLORS, COLOR_SAVING, COLOR_WARN, COLOR_MUTED

NEW_GOAL = "+ Create new goal..."
FROM_BALANCE = "Regular balance"


class TransactionsPage(ctk.CTkFrame):
    def __init__(self, parent, user):
        super().__init__(parent, fg_color="transparent")
        add_background(self)                 # must come first
        self.user = user
        self.selected_id = None
        self.rows = {}                       # tx_id -> database row
        self.goal_ids = {}                   # goal name -> goal_id          (Saving menu)
        self.source_ids = {FROM_BALANCE: None}   # "pay from" label -> goal_id (Expense menu)
        self.last_goal = None                # to restore the menu if "new goal" is cancelled

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        header = ctk.CTkFrame(top, corner_radius=12)
        header.pack(side="left")
        ctk.CTkLabel(header, text="Transactions",
                     font=("Arial", 24, "bold")).pack(padx=20, pady=8)
        self.summary = ctk.CTkLabel(top, text="", text_color=COLOR_MUTED)
        self.summary.pack(side="left", padx=16)

        self._build_form()
        self._build_search()
        self._build_table()
        self.refresh()

    # ---------- form ----------
    def _build_form(self):
        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", pady=10)

        self.type_var = ctk.StringVar(value="Expense")
        ctk.CTkSegmentedButton(form, values=TYPES, variable=self.type_var,
                               command=self.on_type_change).grid(row=0, column=0, padx=8, pady=8)

        self.amount = ctk.CTkEntry(form, placeholder_text="Amount", width=110)
        self.amount.grid(row=0, column=1, padx=4)

        self.category = ctk.CTkOptionMenu(form, values=CATEGORIES["Expense"], width=170,
                                          command=self.on_category_change)
        self.category.grid(row=0, column=2, padx=4)

        self.date = ctk.CTkEntry(form, width=110)
        self.date.insert(0, date.today().isoformat())
        self.date.grid(row=0, column=3, padx=4)

        self.note = ctk.CTkEntry(form, placeholder_text="Note (optional)", width=200)
        self.note.grid(row=0, column=4, padx=4)

        # "Pay from" row - only visible for Expense
        self.source_row = ctk.CTkFrame(form, fg_color="transparent")
        self.source_row.grid(row=1, column=0, columnspan=5, sticky="w", padx=8)
        ctk.CTkLabel(self.source_row, text="Pay from:").pack(side="left", padx=(0, 6))
        self.source = ctk.CTkOptionMenu(self.source_row, values=[FROM_BALANCE], width=320,
                                        fg_color=COLOR_SAVING, button_color="#6D28D9")
        self.source.pack(side="left")

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=2, column=0, columnspan=5, sticky="w", padx=8, pady=(6, 8))
        ctk.CTkButton(btns, text="Add", width=90, command=self.on_add).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Update selected", width=130,
                      command=self.on_update).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete selected", width=130, fg_color="#c0392b",
                      hover_color="#962d22", command=self.on_delete).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Clear", width=70, fg_color="gray",
                      command=self.clear_form).pack(side="left", padx=4)

        self.msg = ctk.CTkLabel(form, text="")
        self.msg.grid(row=3, column=0, columnspan=5, sticky="w", padx=8)

    def _load_goals(self):
        """Reloads the goal choices for both menus (balances change after every transaction)."""
        goals = get_goals(self.user["user_id"])
        self.goal_ids = {g["name"]: g["goal_id"] for g in goals}
        self.source_ids = {FROM_BALANCE: None}
        for g in goals:
            self.source_ids[f"Goal: {g['name']}  ({CURRENCY} {g['current']:,.2f} available)"] = \
                g["goal_id"]
        self.source.configure(values=list(self.source_ids))

    def _saving_menu_values(self):
        return list(self.goal_ids) + [NEW_GOAL]

    def on_type_change(self, value):
        self._load_goals()
        if value == "Saving":
            self.source_row.grid_remove()
            self.category.configure(values=self._saving_menu_values())
            self.category.set(next(iter(self.goal_ids), NEW_GOAL))
            self.last_goal = self.category.get() if self.goal_ids else None
            if not self.goal_ids:
                self.on_category_change(NEW_GOAL)
        else:
            cats = CATEGORIES[value]
            self.category.configure(values=cats)
            self.category.set(cats[0])
            if value == "Expense":
                self.source.set(FROM_BALANCE)
                self.source_row.grid()
            else:
                self.source_row.grid_remove()

    def on_category_change(self, value):
        if self.type_var.get() != "Saving":
            return
        if value == NEW_GOAL:
            GoalDialog(self, self.user, on_created=self._goal_created,
                       on_cancel=self._goal_cancelled)
        else:
            self.last_goal = value

    def _goal_created(self, goal_id, name):
        self._load_goals()
        self.category.configure(values=self._saving_menu_values())
        self.category.set(name)
        self.last_goal = name

    def _goal_cancelled(self):
        self.category.set(self.last_goal or NEW_GOAL)

    # ---------- search ----------
    def _build_search(self):
        bar = ctk.CTkFrame(self)
        bar.grid(row=2, column=0, sticky="w")
        self.search = ctk.CTkEntry(bar, placeholder_text="Search by note, category or goal...",
                                   width=300)
        self.search.pack(side="left", padx=10, pady=10)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())

    # ---------- table ----------
    def _build_table(self):
        holder = ctk.CTkFrame(self)
        holder.grid(row=3, column=0, sticky="nsew", pady=10)
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)

        cols = ("date", "type", "category", "amount", "goal", "note")
        self.tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (95, 80, 120, 110, 220, 240)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        for t, color in TYPE_COLORS.items():       # income green, expense red, saving purple
            self.tree.tag_configure(t, foreground=color)
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    @staticmethod
    def _goal_text(r):
        if not r["goal_name"]:
            return ""
        if r["type"] == "Saving":
            return f"Saved to goal: {r['goal_name']}"
        return f"Spent from goal: {r['goal_name']}"

    def refresh(self):
        self._load_goals()
        s = get_summary(self.user["user_id"])
        self.summary.configure(
            text=f"Balance {CURRENCY} {s['balance']:,.2f}   |   In goals {CURRENCY} "
                 f"{s['goal_money']:,.2f}   |   Available {CURRENCY} {s['available']:,.2f}")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows.clear()
        for r in get_transactions(self.user["user_id"], keyword=self.search.get().strip()):
            self.rows[r["tx_id"]] = r
            self.tree.insert("", "end", iid=str(r["tx_id"]), tags=(r["type"],),
                             values=(r["date"], r["type"], r["category"],
                                     f'{r["amount"]:,.2f}', self._goal_text(r), r["note"] or ""))

    def on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        r = self.rows[self.selected_id]
        self.type_var.set(r["type"])
        self.on_type_change(r["type"])
        if r["type"] == "Saving":
            if r["goal_name"]:
                self.category.set(r["goal_name"])
                self.last_goal = r["goal_name"]
        else:
            self.category.set(r["category"])
        if r["type"] == "Expense":
            for label, gid in self.source_ids.items():
                if gid == r["goal_id"]:
                    self.source.set(label)
        for entry, value in ((self.amount, f'{r["amount"]:.2f}'),
                             (self.date, r["date"]),
                             (self.note, r["note"] or "")):
            entry.delete(0, "end")
            entry.insert(0, value)

    # ---------- actions ----------
    def _read_form(self):
        amount, err = validate_transaction(self.amount.get(), self.date.get().strip())
        if err:
            self.msg.configure(text=err, text_color="red")
            return None
        type_, category, goal_id = self.type_var.get(), self.category.get(), None
        if type_ == "Saving":
            goal_id = self.goal_ids.get(category)
            if goal_id is None:
                self.msg.configure(text="Choose a goal (or create a new one).", text_color="red")
                return None
        elif type_ == "Expense":
            goal_id = self.source_ids.get(self.source.get())
        return (type_, amount, category, self.date.get().strip(),
                self.note.get().strip(), goal_id)

    def on_add(self):
        data = self._read_form()
        if not data:
            return
        ok, message = add_transaction(self.user["user_id"], *data)
        if not ok:
            self.msg.configure(text=message, text_color="red")
            return
        warning = budget_warning(self.user["user_id"], data[2], data[3]) \
            if data[0] == "Expense" else None
        self.clear_form()
        if warning:
            self.msg.configure(text=f"Transaction saved.  Warning: {warning}", text_color=COLOR_WARN)
        else:
            self.msg.configure(text="Transaction saved.", text_color="green")
        self.refresh()

    def on_update(self):
        if self.selected_id is None:
            self.msg.configure(text="Select a transaction first.", text_color="red")
            return
        data = self._read_form()
        if not data:
            return
        ok, message = update_transaction(self.selected_id, self.user["user_id"], *data)
        if not ok:
            self.msg.configure(text=message, text_color="red")
            return
        self.clear_form()
        self.msg.configure(text="Transaction updated.", text_color="green")
        self.refresh()

    def on_delete(self):
        if self.selected_id is None:
            self.msg.configure(text="Select a transaction first.", text_color="red")
            return
        if messagebox.askyesno("Confirm delete", "Delete this transaction?"):
            ok, message = delete_transaction(self.selected_id, self.user["user_id"])
            if not ok:
                self.msg.configure(text=message, text_color="red")
                return
            self.clear_form()
            self.msg.configure(text="Transaction deleted.", text_color="green")
            self.refresh()

    def clear_form(self):
        self.selected_id = None
        self.amount.delete(0, "end")
        self.note.delete(0, "end")
        self.date.delete(0, "end")
        self.date.insert(0, date.today().isoformat())
        self.source.set(FROM_BALANCE)
        self.tree.selection_remove(self.tree.selection())
