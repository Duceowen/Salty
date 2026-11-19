"""Shutdown behaviour for the Salty EDMC plugin.

EDMC only leaves mainloop after its root window is destroyed. These checks
open the real pop-out and settings windows, then make sure plugin_stop()
and a Windows session-end notification drop those windows without rewriting
the chat log or the saved settings.
"""

import logging
import os
import pathlib
import sys
import tempfile
import tkinter as tk
import types

if sys.version_info < (3, 10):
    sys.exit("test_shutdown.py needs Python 3.10+")

nb = types.ModuleType("myNotebook")
nb.Frame = tk.Frame
nb.Checkbutton = tk.Checkbutton
nb.Label = tk.Label
sys.modules["myNotebook"] = nb


class _Cfg:
    def __init__(self):
        self._d = {}

    def get_bool(self, key, default=None):
        value = self._d.get(key, default)
        return bool(value) if isinstance(value, bool) else default

    def get_int(self, key, default=None):
        value = self._d.get(key, default)
        return value if isinstance(value, int) else default

    def get_str(self, key, default=None):
        value = self._d.get(key, default)
        return value if isinstance(value, str) else default

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

import importlib.util

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
spec = importlib.util.spec_from_file_location("salty_shutdown", REPO_ROOT / "load.py")
salty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(salty)

log_dir = tempfile.mkdtemp(prefix="salty-shutdown-")
log_marker = os.path.join(log_dir, "EDMarketConnector.log")
logging.getLogger("EDMarketConnector").addHandler(logging.FileHandler(log_marker))
assert salty._chat_log_dir() == log_dir, salty._chat_log_dir()
chat_path = os.path.join(log_dir, "SaltyChat.log")
original_log = "12:00:00\tlocal\tAnn\t\tout\tkeep me\n"
with open(chat_path, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(original_log)

config_mod.config.set("salty_show_local", False)
config_mod.config.set("salty_overlay_ttl", 12)
config_mod.config.set("salty_chat_logging", True)
preserved = {
    key: value
    for key, value in config_mod.config._d.items()
    if not key.startswith("salty_popout_")
}

root = tk.Tk()
root.geometry("900x700+40+40")
root.title("E:D Market Connector")
root.update_idletasks()
holder = tk.Frame(root)
holder.pack()
frame = salty.plugin_app(holder)
frame.pack()
root.update_idletasks()
root.update()

focus = tk.Entry(root)
focus.pack()
focus.focus_set()
root.update()
assert focus.winfo_exists()

salty._open_popout()
salty._open_settings()
root.update_idletasks()
root.update()

assert salty._window_alive(salty._popout)
assert salty._window_alive(salty._settings_win)
assert str(salty._popout.wm_transient()) == str(root)
assert str(salty._settings_win.wm_transient()) == str(root)
assert root.grab_current() is None
assert root.focus_get() is focus
assert "focus_force" not in (REPO_ROOT / "load.py").read_text(encoding="utf-8")
assert "grab_set" not in (REPO_ROOT / "load.py").read_text(encoding="utf-8")
assert salty._ct_target_allowed(salty._host_hwnd()) is False
assert salty._ct_target_allowed(int(salty._popout.winfo_id())) is True
print("pop-out is owned by EDMC, has no grab and does not take focus OK")


def _click_yes():
    for widget in salty._walk(root):
        if widget.winfo_class() == "Button" and str(widget.cget("text")) == "Yes":
            widget.invoke()
            return
    raise AssertionError("Yes button was not created")


root.after(40, _click_yes)
assert salty._themed_confirm(root, "Clear the chat window?") is True
assert root.grab_current() is None
print("confirmation accepts Yes without a grab OK")


def _dismiss_dialog():
    for closer in list(salty._modal_closers):
        closer()


root.after(40, _dismiss_dialog)
salty._clear_chat_log()
with open(chat_path, "rb") as handle:
    assert handle.read() == original_log.encode("utf-8")
print("declining Clear Chat logs leaves SaltyChat.log untouched OK")

corruptions = []


def _corrupt_log():
    corruptions.append("ran")
    with open(chat_path, "w", encoding="utf-8") as handle:
        handle.write("CORRUPTED\n")


salty._after(salty._main_frame, 200, _corrupt_log)

closes = []


def _host_close():
    closes.append("close")
    salty.plugin_stop()


root.protocol("WM_DELETE_WINDOW", _host_close)
salty._on_windows_session(False)
root.update()
assert closes == []
assert salty._window_alive(salty._popout)
print("a cancelled Windows shutdown leaves Salty open OK")

salty._on_windows_session(True)
root.update()
assert closes == ["close"]
assert salty._shutting_down
assert salty._popout is None
assert salty._settings_win is None
assert salty._tracked_toplevels == []
assert root.grab_current() is None
leftover = [
    widget
    for widget in root.winfo_children()
    if isinstance(widget, tk.Toplevel)
]
assert leftover == [], leftover
print("Windows session end closes EDMC and drops every Salty window OK")

root.after(400)
root.update()
assert corruptions == []
with open(chat_path, "rb") as handle:
    assert handle.read() == original_log.encode("utf-8")
for key, value in preserved.items():
    assert config_mod.config._d.get(key) == value, (key, config_mod.config._d.get(key))
assert "salty_popout_width" in config_mod.config._d
print("shutdown keeps the chat log and saved settings, and cancels timers OK")

salty.plugin_stop()
salty._on_windows_session(True)
root.update()
assert closes == ["close"]
print("a second stop and a second session end do nothing OK")

root.destroy()
print("ALL SHUTDOWN CHECKS PASS")
