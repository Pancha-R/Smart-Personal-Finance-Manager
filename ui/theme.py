import tkinter as tk
from pathlib import Path
from PIL import Image, ImageFilter
import customtkinter as ctk

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Money colours used everywhere: income green, expenses red, goal money purple.
COLOR_INCOME  = "#16A34A"
COLOR_EXPENSE = "#DC2626"
COLOR_SAVING  = "#7C3AED"
COLOR_WARN    = "#D97706"
COLOR_MUTED   = "#6B7280"
TYPE_COLORS = {"Income": COLOR_INCOME, "Expense": COLOR_EXPENSE, "Saving": COLOR_SAVING}


def draw_donut(parent, percent, size=96, color=COLOR_SAVING, thickness=11):
    """A ring that is `percent`% filled, with the percentage in the middle."""
    try:
        bg = parent._apply_appearance_mode(parent.cget("fg_color"))
    except Exception:
        bg = "#dbdbdb"
    c = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg=bg)
    pad = thickness // 2 + 2
    box = (pad, pad, size - pad, size - pad)
    c.create_oval(*box, outline="#E5E7EB", width=thickness)
    if percent >= 100:
        c.create_oval(*box, outline=color, width=thickness)
    elif percent > 0:
        c.create_arc(*box, start=90, extent=-360 * percent / 100,
                     style="arc", outline=color, width=thickness)
    c.create_text(size / 2, size / 2, text=f"{percent:.0f}%", fill="#1F2937",
                  font=("Arial", 13, "bold"))
    return c


def find_asset(name):
    """Looks for assets/<name>.png / .jpg / .jpeg / .webp. Returns the path or None."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = ASSETS / f"{name}{ext}"
        if path.exists():
            return path
    return None


def load_logo(width):
    """Returns the logo as a CTkImage scaled to the given width, or None if missing."""
    path = find_asset("logo")
    if path is None:
        return None
    img = Image.open(path)
    w, h = img.size
    return ctk.CTkImage(light_image=img, size=(width, int(h * width / w)))


def add_background(frame):
    """Puts assets/bg.* behind everything in `frame`.
    Call this FIRST in a page's __init__, before any other widgets are created,
    so the picture sits at the back."""
    path = find_asset("bg")
    if path is None:
        return

    original = Image.open(path)
    original.thumbnail((480, 270))
    original = original.filter(ImageFilter.GaussianBlur(radius=3))   #blur      

    label = ctk.CTkLabel(frame, text="")
    label.place(x=0, y=0, relwidth=1, relheight=1)

    last_size = {"value": None}

    def resize(event):
        size = (max(event.width, 1), max(event.height, 1))
        if size == last_size["value"]:
            return
        last_size["value"] = size
        label.configure(image=ctk.CTkImage(light_image=original, size=size))

    frame.bind("<Configure>", resize)