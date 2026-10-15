"""Headless runtime test for the Salty EDMC plugin.

Runs on Linux CI (python3-tk + xvfb): stubs the EDMC host modules, imports
the real load.py, and exercises channel routing, the toggle UIs and the real
pop-out build including the themed scrollbar under overflow.
"""

import importlib.util
import pathlib
import sys
import tkinter as tk
import types

if sys.version_info < (3, 10):
    sys.exit("test_runtime.py needs Python 3.10+")

# ---- stub EDMC host modules BEFORE importing salty ----
nb = types.ModuleType("myNotebook")
nb.Frame = tk.Frame
nb.Checkbutton = tk.Checkbutton
nb.Label = tk.Label
sys.modules["myNotebook"] = nb


class _Cfg:
    def __init__(self):
        self._d = {}

    def get_bool(self, key, default=None):
        v = self._d.get(key, default)
        return bool(v) if isinstance(v, bool) else default

    def get_int(self, key, default=None):
        v = self._d.get(key, default)
        return v if isinstance(v, int) else default

    def get_str(self, key, default=None):
        v = self._d.get(key, default)
        return v if isinstance(v, str) else default

    def set(self, key, value):
        self._d[key] = value


config_mod = types.ModuleType("config")
config_mod.appname = "EDMarketConnector"
config_mod.config = _Cfg()
sys.modules["config"] = config_mod


class _Theme:
    current = {"background": "grey4", "foreground": "#ff8000"}


theme_mod = types.ModuleType("theme")
theme_mod.theme = _Theme()
sys.modules["theme"] = theme_mod
# ---- end stubs ----

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "salty_load", REPO_ROOT / "load.py"
)
salty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(salty)
print("import OK")

# channel routing, incl. the journal's squadleaders token
for raw, want in {
    "squadleaders": "squadleaders",
    "Squadron Leaders": "squadleaders",
    "squadron": "squadron",
    "wing": "wing",
    "starsystem": "system",
    "npc": "npc",
    "player": "private",
}.items():
    assert salty._normalise_channel(raw) == want, raw
assert len(salty.CHANNELS) == 7
assert salty.CHANNEL_LABELS["squadleaders"] == "Squadron Leaders"
print("routing + registries OK")

root = tk.Tk()
root.geometry("900x700")
root.deiconify()
root.update_idletasks()
root.update()
salty._main_frame = tk.Frame(root)
salty._main_frame.pack()
salty._ensure_filter_vars()


def channel_labels(parent):
    found = []

    def rec(widget):
        if widget.winfo_class() == "Checkbutton":
            found.append(str(widget.cget("text")))
        for child in widget.winfo_children():
            rec(child)

    rec(parent)
    return found


strip = tk.Frame(root)
salty._build_toggle_strip(
    strip, include_timestamp=True, include_origin=True, font_delta=1
)
grid = tk.Frame(root)
salty._build_toggle_grid(
    grid, include_timestamp=True, include_origin=True, font_delta=0
)
for name, got in (("strip", channel_labels(strip)),
                  ("grid", channel_labels(grid))):
    for label in salty.CHANNEL_LABELS.values():
        assert label in got, (name, label)
print("toggle UIs list all channels OK")

# real pop-out build: scrollbar must pack before the text and stay mapped
# with a themed thumb, even when the text demands more width than fits
salty._open_popout()
root.update_idletasks()
root.update()
container = next(
    w
    for w in salty._popout.winfo_children()
    if w.winfo_class() == "Frame"
    and any(k.winfo_class() == "Text" for k in w.winfo_children())
)
slaves = container.pack_slaves()
assert [type(w).__name__ for w in slaves] == ["ThemedScrollbar", "Text"], [
    type(w).__name__ for w in slaves
]
sb = slaves[0]
text = slaves[1]
text.configure(width=100)  # force overflow
text.configure(state="normal")
for i in range(200):
    text.insert("end", f"line {i} chat content here\n")
text.configure(state="disabled")
salty._style_chat_texts()
root.update_idletasks()
root.update()
root.after(300)
root.update()
salty._style_chat_texts()
root.update_idletasks()
root.update()
thumbs = sb.find_withtag("thumb")
live_fg = _Theme.current["foreground"]
print(
    f"scrollbar {sb.winfo_width()}x{sb.winfo_height()} "
    f"mapped={bool(sb.winfo_ismapped())} thumbs={len(thumbs)} "
    f"thumbfill={sb.itemcget(thumbs[0], 'fill') if thumbs else None}"
)
assert sb.winfo_ismapped() and sb.winfo_width() > 1 and thumbs
assert sb.itemcget(thumbs[0], "fill") == live_fg
root.destroy()
print("ALL RUNTIME CHECKS PASS")
