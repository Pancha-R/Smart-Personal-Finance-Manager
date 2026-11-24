import customtkinter as ctk
from datetime import date
from tkinter import messagebox
from config import CURRENCY
from services.goals import add_goal, get_goals, delete_goal
from ui.theme import add_background, draw_donut, COLOR_SAVING, COLOR_MUTED


class GoalCard(ctk.CTkFrame):
    """One goal as a small widget: a ring showing how much is filled, plus the numbers."""

    def __init__(self, parent, goal, on_delete=None, width=170):
        super().__init__(parent, corner_radius=12, width=width)
        draw_donut(self, goal["percent"]).pack(pady=(12, 4), padx=10)
        ctk.CTkLabel(self, text=goal["name"], font=("Arial", 14, "bold")).pack()
        ctk.CTkLabel(self, text=f"{CURRENCY} {goal['current']:,.0f} / {goal['target']:,.0f}"
                     ).pack()
        if goal["percent"] >= 100:
            ctk.CTkLabel(self, text="Goal reached!", text_color=COLOR_SAVING,
                         font=("Arial", 12, "bold")).pack()
        else:
            left = goal["days_left"]
            text = f"{left} days left" if left >= 0 else "deadline passed"
            ctk.CTkLabel(self, text=f"by {goal['deadline']}  ({text})",
                         text_color=COLOR_MUTED, font=("Arial", 11)).pack()
        if on_delete:
            ctk.CTkButton(self, text="Delete", width=70, height=24, fg_color="#c0392b",
                          hover_color="#962d22",
                          command=lambda: on_delete(goal)).pack(pady=(6, 0))
        ctk.CTkFrame(self, height=8, fg_color="transparent").pack()


class GoalDialog(ctk.CTkToplevel):
    """Small pop-up for creating a goal (used from the Transactions page)."""

    def __init__(self, parent, user, on_created, on_cancel=None):
        super().__init__(parent)
        self.user, self.on_created, self.on_cancel = user, on_created, on_cancel
        self.title("New savings goal")
        self.geometry("340x300")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        ctk.CTkLabel(self, text="New savings goal", font=("Arial", 18, "bold")).pack(pady=(16, 8))
        self.name = ctk.CTkEntry(self, placeholder_text="Goal name (e.g. New laptop)", width=260)
        self.name.pack(pady=4)
        self.target = ctk.CTkEntry(self, placeholder_text="Target amount", width=260)
        self.target.pack(pady=4)
        self.deadline = ctk.CTkEntry(self, placeholder_text="Deadline (YYYY-MM-DD)", width=260)
        self.deadline.pack(pady=4)
        self.msg = ctk.CTkLabel(self, text="", text_color="red")
        self.msg.pack()
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        ctk.CTkButton(row, text="Create", width=110, fg_color=COLOR_SAVING,
                      hover_color="#6D28D9", command=self._create).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Cancel", width=110, fg_color="gray",
                      command=self._cancel).pack(side="left", padx=4)
        self.after(150, self._focus)

    def _focus(self):
        self.lift()
        self.grab_set()
        self.name.focus()

    def _create(self):
        goal_id, err = add_goal(self.user["user_id"], self.name.get(),
                                self.target.get(), self.deadline.get())
        if err:
            self.msg.configure(text=err)
            return
        self.grab_release()
        self.destroy()
        self.on_created(goal_id, self.name.get().strip())

    def _cancel(self):
        self.grab_release()
        self.destroy()
        if self.on_cancel:
            self.on_cancel()


class GoalsPage(ctk.CTkFrame):
    COLUMNS = 3

    def __init__(self, parent, user):
        super().__init__(parent, fg_color="transparent")
        add_background(self)                 # must come first
        self.user = user
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, corner_radius=12)
        header.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Savings Goals",
                     font=("Arial", 24, "bold")).pack(padx=20, pady=8)

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", pady=10)
        self.name = ctk.CTkEntry(form, placeholder_text="Goal name", width=200)
        self.name.grid(row=0, column=0, padx=8, pady=8)
        self.target = ctk.CTkEntry(form, placeholder_text="Target amount", width=130)
        self.target.grid(row=0, column=1, padx=4)
        self.deadline = ctk.CTkEntry(form, placeholder_text="Deadline YYYY-MM-DD", width=160)
        self.deadline.grid(row=0, column=2, padx=4)
        ctk.CTkButton(form, text="Add goal", width=100, fg_color=COLOR_SAVING,
                      hover_color="#6D28D9", command=self.on_add).grid(row=0, column=3, padx=8)
        self.msg = ctk.CTkLabel(form, text="Add money to a goal from the Transactions page "
                                           "by choosing the Saving type.",
                                text_color=COLOR_MUTED)
        self.msg.grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(0, 8))

        self.holder = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.holder.grid(row=2, column=0, sticky="nsew")
        self.refresh()

    def refresh(self):
        for w in self.holder.winfo_children():
            w.destroy()
        goals = get_goals(self.user["user_id"])
        if not goals:
            ctk.CTkLabel(self.holder, text="No goals yet - add your first one above.",
                         text_color=COLOR_MUTED).pack(pady=30)
            return
        for i, g in enumerate(goals):
            GoalCard(self.holder, g, on_delete=self.on_delete).grid(
                row=i // self.COLUMNS, column=i % self.COLUMNS, padx=8, pady=8, sticky="n")

    def on_add(self):
        goal_id, err = add_goal(self.user["user_id"], self.name.get(),
                                self.target.get(), self.deadline.get())
        if err:
            self.msg.configure(text=err, text_color="red")
            return
        for e in (self.name, self.target, self.deadline):
            e.delete(0, "end")
        self.msg.configure(text="Goal created.", text_color="green")
        self.refresh()

    def on_delete(self, goal):
        if messagebox.askyesno(
                "Delete goal",
                f"Delete \"{goal['name']}\"?\n\nThe {CURRENCY} {goal['current']:,.2f} saved in it "
                "goes back to your available balance. Past expenses paid from this goal stay "
                "in your history as normal expenses."):
            delete_goal(goal["goal_id"], self.user["user_id"])
            self.refresh()
