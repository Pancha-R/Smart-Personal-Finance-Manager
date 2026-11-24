import customtkinter as ctk
from tkinter import ttk, messagebox
from config import CURRENCY
from services.transactions import CATEGORIES
from services.recurring import (validate_recurring, add_recurring,
                                get_recurring, delete_recurring)
from ui.reminders import ReminderPanel
from ui.theme import add_background, TYPE_COLORS


class RecurringPage(ctk.CTkFrame):
    def __init__(self, parent, user):
        super().__init__(parent, fg_color="transparent")
        add_background(self)                 # must come first
        self.user = user
        self.rows = {}
        self.selected_id = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Recurring Income & Expenses",
                     font=("Arial", 24, "bold")).pack(padx=20, pady=8)

        self._build_form()
        ReminderPanel(self, user, on_change=self._reload, show_budget=False,
                      height=110).grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._build_table()
        self.refresh()

    def _reload(self):
        top = self.winfo_toplevel()
        top.after(10, lambda: top.show_page("Receivables and Payables"))

    def _build_form(self):
        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", pady=10)

        self.type_var = ctk.StringVar(value="Expense")
        ctk.CTkSegmentedButton(form, values=["Income", "Expense"], variable=self.type_var,
                               command=self.on_type_change).grid(row=0, column=0, padx=8, pady=8)
        self.title_entry = ctk.CTkEntry(form, placeholder_text="Title (e.g. Rent)", width=170)
        self.title_entry.grid(row=0, column=1, padx=4)
        self.amount = ctk.CTkEntry(form, placeholder_text="Amount", width=100)
        self.amount.grid(row=0, column=2, padx=4)
        self.category = ctk.CTkOptionMenu(form, values=CATEGORIES["Expense"], width=130)
        self.category.grid(row=0, column=3, padx=4)
        self.day = ctk.CTkEntry(form, placeholder_text="Day (1-31)", width=90)
        self.day.grid(row=0, column=4, padx=4)

        btns = ctk.CTkFrame(form, fg_color="transparent")
        btns.grid(row=1, column=0, columnspan=5, sticky="w", padx=8, pady=(0, 8))
        ctk.CTkButton(btns, text="Add", width=90, command=self.on_add).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete selected", width=130, fg_color="#c0392b",
                      hover_color="#962d22", command=self.on_delete).pack(side="left", padx=4)
        self.msg = ctk.CTkLabel(btns, text="")
        self.msg.pack(side="left", padx=10)

    def on_type_change(self, value):
        cats = CATEGORIES[value]
        self.category.configure(values=cats)
        self.category.set(cats[0])

    def _build_table(self):
        holder = ctk.CTkFrame(self)
        holder.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)

        cols = ("type", "title", "category", "amount", "day")
        self.tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (90, 220, 140, 120, 140)):
            self.tree.heading(c, text="Every month on day" if c == "day" else c.title())
            self.tree.column(c, width=w, anchor="w")
        for t, color in TYPE_COLORS.items():
            self.tree.tag_configure(t, foreground=color)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows.clear()
        for r in get_recurring(self.user["user_id"]):
            self.rows[r["rec_id"]] = r
            self.tree.insert("", "end", iid=str(r["rec_id"]), tags=(r["type"],),
                             values=(r["type"], r["title"], r["category"],
                                     f'{r["amount"]:,.2f}', r["day_of_month"]))

    def on_select(self, _event):
        sel = self.tree.selection()
        self.selected_id = int(sel[0]) if sel else None

    def on_add(self):
        amount, day, err = validate_recurring(self.title_entry.get(), self.amount.get(),
                                              self.day.get())
        if err:
            self.msg.configure(text=err, text_color="red")
            return
        add_recurring(self.user["user_id"], self.type_var.get(), self.title_entry.get(),
                      amount, self.category.get(), day)
        self._reload()          # reload so a reminder shows up straight away if it is due

    def on_delete(self):
        if self.selected_id is None:
            self.msg.configure(text="Select an item first.", text_color="red")
            return
        if messagebox.askyesno("Confirm delete",
                               "Stop this recurring item? Transactions already added stay."):
            delete_recurring(self.selected_id, self.user["user_id"])
            self.selected_id = None
            self.refresh()
