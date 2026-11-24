import customtkinter as ctk
from pathlib import Path
from PIL import Image
from auth import register_user, login_user
from config import APP_NAME

# ---------- EDIT THESE TO CHANGE THE LOOK ----------
BG_COLOR        = "#EEF3F8"   # window background
CARD_COLOR      = "#FFFFFF"   # the white panel
PRIMARY         = "#2563EB"   # main button
PRIMARY_HOVER   = "#1D4ED8"
SECONDARY       = "#E5E7EB"   # secondary button
SECONDARY_HOVER = "#D1D5DB"
TEXT_DARK       = "#1F2937"
TEXT_MUTED      = "#6B7280"
ERROR_COLOR     = "#DC2626"
SUCCESS_COLOR   = "#16A34A"
FONT_FAMILY     = "Segoe UI"
# ----------------------------------------------------

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


class LoginWindow(ctk.CTk):
    """Login and registration in one window. Sets self.user on successful login."""

    def __init__(self):
        super().__init__()
        self.user = None
        self.mode = "login"

        self.title(APP_NAME)
        self.configure(fg_color=BG_COLOR)
        self.resizable(False, False)
        self._center(440, 720)

        # ----- logo (skipped automatically if the file is missing) -----
        top_padding = 40
        if LOGO_PATH.exists():
            logo_img = ctk.CTkImage(light_image=Image.open(LOGO_PATH), size=(250, 250))
            ctk.CTkLabel(self, image=logo_img, text="").pack(pady=(30, 0))
            top_padding = 5

        # ----- white card -----
        self.card = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=16, width=340)
        self.card.pack(padx=40, pady=5, fill="x")

        self.subtitle = ctk.CTkLabel(self.card, text="Welcome back", text_color=TEXT_DARK,
                                     font=(FONT_FAMILY, 20, "bold"))
        self.subtitle.pack(pady=(25, 15))

        self.full_name = self._entry("Full name")
        self.username = self._entry("Username")
        self.username.pack(padx=25, pady=6, fill="x")
        self.password = self._entry("Password", show="*")
        self.password.pack(padx=25, pady=6, fill="x")
        self.confirm = self._entry("Confirm password", show="*")

        self.show_pw = ctk.BooleanVar(value=False)
        self.show_pw_box = ctk.CTkCheckBox(
            self.card, text="Show password", variable=self.show_pw,
            command=self.toggle_password, text_color=TEXT_MUTED,
            font=(FONT_FAMILY, 12), fg_color=PRIMARY, hover_color=PRIMARY_HOVER)
        self.show_pw_box.pack(padx=27, pady=(6, 0), anchor="w")

        self.message = ctk.CTkLabel(self.card, text="", wraplength=280,
                                    font=(FONT_FAMILY, 12))
        self.message.pack(pady=(8, 0))

        self.main_btn = ctk.CTkButton(
            self.card, text="Login", height=42, corner_radius=8,
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
            font=(FONT_FAMILY, 14, "bold"), command=self.submit)
        self.main_btn.pack(padx=25, pady=(8, 8), fill="x")

        self.switch_btn = ctk.CTkButton(
            self.card, text="Create an account", height=38, corner_radius=8,
            fg_color=SECONDARY, hover_color=SECONDARY_HOVER, text_color=TEXT_DARK,
            font=(FONT_FAMILY, 13), command=self.toggle_mode)
        self.switch_btn.pack(padx=25, pady=(0, 25), fill="x")

        self.bind("<Return>", lambda e: self.submit())    # Enter key submits
        self.username.focus()

    # ---------- helpers ----------
    def _center(self, w, h):
        """Set the window size and place it in the middle of the screen."""
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _entry(self, placeholder, show=None):
        """Create a styled text box inside the white card."""
        return ctk.CTkEntry(
            self.card, placeholder_text=placeholder, show=show, height=42,
            corner_radius=8, border_width=1, border_color="#D1D5DB",
            fg_color="#F9FAFB", text_color=TEXT_DARK, font=(FONT_FAMILY, 13))

    def toggle_password(self):
        char = "" if self.show_pw.get() else "*"
        self.password.configure(show=char)
        self.confirm.configure(show=char)

    # ---------- switching between login and register ----------
    def toggle_mode(self):
        self.message.configure(text="")
        if self.mode == "login":
            self.mode = "register"
            self.subtitle.configure(text="Create your account")
            self.full_name.pack(padx=25, pady=6, fill="x", before=self.username)
            self.confirm.pack(padx=25, pady=6, fill="x", after=self.password)
            self.main_btn.configure(text="Register")
            self.switch_btn.configure(text="Back to login")
        else:
            self.mode = "login"
            self.subtitle.configure(text="Welcome back")
            self.full_name.pack_forget()
            self.confirm.pack_forget()
            self.main_btn.configure(text="Login")
            self.switch_btn.configure(text="Create an account")

    def submit(self):
        if self.mode == "login":
            self.do_login()
        else:
            self.do_register()

    # ---------- actions ----------
    def do_login(self):
        user = login_user(self.username.get(), self.password.get())
        if user:
            self.user = user
            self.destroy()                  # ends mainloop(); main.py opens the dashboard
        else:
            self.message.configure(text="Invalid username or password.", text_color=ERROR_COLOR)

    def do_register(self):
        if self.password.get() != self.confirm.get():
            self.message.configure(text="Passwords do not match.", text_color=ERROR_COLOR)
            return
        ok, msg = register_user(self.username.get(), self.full_name.get(), self.password.get())
        if ok:
            self.password.delete(0, "end")
            self.confirm.delete(0, "end")
            self.toggle_mode()
            self.message.configure(text=msg, text_color=SUCCESS_COLOR)
        else:
            self.message.configure(text=msg, text_color=ERROR_COLOR)