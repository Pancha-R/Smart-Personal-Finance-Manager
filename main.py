import customtkinter as ctk
from database.db import init_db
from ui.login_window import LoginWindow
from ui.dashboard import Dashboard

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def run():
    init_db()
    while True:                          # loop so "Log out" returns to the login screen
        login = LoginWindow()
        login.mainloop()
        if login.user is None:           # window was closed without logging in
            break
        dash = Dashboard(login.user)
        dash.mainloop()
        if not dash.logged_out:          # window was closed with the X button
            break


if __name__ == "__main__":
    run()