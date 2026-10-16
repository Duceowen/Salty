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
assert salty.CHANNEL_LABELS["squadleaders"] == "Officer"
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

assert salty._popout_toggles is not None and salty._popout_toggles.winfo_ismapped()
salty._open_settings()
root.update_idletasks()
root.update()


def find_button(parent, text):
    found = []

    def rec(widget):
        if widget.winfo_class() == "Button" and str(widget.cget("text")) == text:
            found.append(widget)
        for child in widget.winfo_children():
            rec(child)

    rec(parent)
    return found


hide_btns = find_button(salty._settings_win, "Hide Boxes")
assert len(hide_btns) == 1, hide_btns
hide_btns[0].invoke()
root.update_idletasks()
root.update()
assert not salty._popout_toggles.winfo_ismapped()
assert salty._boxes_hidden()
assert find_button(salty._settings_win, "Show Boxes")
show_btns = find_button(salty._settings_win, "Show Boxes")
show_btns[0].invoke()
root.update_idletasks()
root.update()
assert salty._popout_toggles.winfo_ismapped()
assert not salty._boxes_hidden()
print("Hide Boxes toggles the pop-out Show Messages row OK")
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
assert str(text.cget("cursor")) == "arrow"
assert int(str(text.cget("highlightthickness"))) == 0
assert str(text.cget("relief")) == "flat"
assert find_button(salty._popout, "Options"), "pop-out Options button missing"
assert find_button(salty._popout, "Clear"), "pop-out Clear button missing"
assert find_button(salty._settings_win, "Clear Chat logs")
assert find_button(salty._settings_win, "Open Log Folder")
settings_checks = channel_labels(salty._settings_win)
assert "From:" in settings_checks
assert "To:" in settings_checks
for label in ("Local", "System", "Private", "Wing", "Squadron", "Officer"):
    assert find_button(salty._settings_win, label), label
print("options, log buttons, From/To and colour swatches OK")

assert salty.STARTUP_HINT_MS == 6000
assert "Double Click for Options" in salty.HOVER_TIP_TEXT

config_mod.config.set("salty_chat_logging", False)
salty._messages.clear()


def _entry(event, **fields):
    fields["event"] = event
    fields.setdefault("timestamp", "2026-10-16T12:00:00Z")
    return fields


salty.journal_entry(
    "Cmdr Example",
    False,
    "Sol",
    None,
    _entry("SendText", To="Bob", Message="hello there"),
    {},
)
sent = salty._messages[-1]
assert sent["from"] == "Me" and sent["to"] == "Bob" and sent["incoming"] is False
assert sent["channel"] == "private"
sent_line = salty._format_prefix(sent)
assert "[Private]" in sent_line
assert "To: Bob" in sent_line
assert sent_line.rstrip().endswith("Me:")
assert "Cmdr Example" not in sent_line

salty.journal_entry(
    "Cmdr Example",
    False,
    "Sol",
    None,
    _entry("ReceiveText", Channel="player", From="Bob", Message="hi"),
    {},
)
got = salty._messages[-1]
assert got["from"] == "Bob" and got["to"] == "Me" and got["incoming"] is True
got_line = salty._format_prefix(got)
assert "[Private]" in got_line
assert "From: Bob:" in got_line

salty.journal_entry(
    "Cmdr Example",
    False,
    "Sol",
    None,
    _entry("SendText", To="local", Message="in system"),
    {},
)
local_sent = salty._messages[-1]
assert local_sent["from"] == "Me" and local_sent["channel"] == "local"
assert "Cmdr Example" not in salty._format_prefix(local_sent)

salty._to_var.set(False)
salty._from_var.set(False)
assert "To:" not in salty._format_prefix(sent)
assert salty._format_prefix(sent).rstrip().endswith("Me:")
assert "From:" not in salty._format_prefix(got)
assert "Bob:" in salty._format_prefix(got)
salty._to_var.set(True)
salty._from_var.set(True)
print("private From/To and Me OK")

parsed = salty._parse_chat_log_line("12:00:00\tprivate\tMe\tBob\tout\thello")
assert parsed["from"] == "Me" and parsed["to"] == "Bob" and parsed["incoming"] is False
legacy = salty._parse_chat_log_line("12:00:00\tlocal\tAnn\thi")
assert legacy["incoming"] is False and legacy["to"] == "" and legacy["from"] == "Ann"
print("chat log rows OK")

wrapped = salty._wrap_overlay_text(
    "This is a private message that should wrap onto more than one line cleanly"
)
wrap_lines = wrapped.split("\n")
assert len(wrap_lines) >= 2
assert all(len(line) <= 40 for line in wrap_lines)
for word in (
    "This is a private message that should wrap onto more than one line cleanly"
).split():
    assert any(word in line for line in wrap_lines)
long_word = "Z" * 50
long_wrap = salty._wrap_overlay_text(
    f"Hello {long_word} friend plus several extra words so the line has to wrap"
)
assert any(long_word in line for line in long_wrap.split("\n"))
assert all(len(line) <= max(40, len(long_word)) for line in long_wrap.split("\n"))
body = salty._overlay_body(
    "private",
    "Bob",
    "a fairly long incoming private note that will not fit on one overlay line",
)
assert body.startswith("From: Bob:")
assert "\n" in body
print("overlay wrap OK")

salty._set_channel_color("private", "#112233")
assert salty._channel_color("private") == "#112233"
assert str(text.tag_cget("ch_private", "foreground")).lower() == "#112233"
captured = []

def _fake_send(payload):
    captured.append(payload)

salty._overlay_send = _fake_send
salty._overlay_import_done = True
salty._notify("private", "Bob", "colour me in")
assert captured and captured[-1]["color"].lower() == "#112233"
assert "From:" in captured[-1]["text"]
print("overlay colour OK")

holder = tk.Frame(root)
holder.pack(fill="both", expand=True)
salty.plugin_app(holder)
root.update_idletasks()
root.update()
main = salty._main_text
assert str(main.cget("cursor")) == "arrow"
assert int(str(main.cget("highlightthickness"))) == 0
bars = [w for w in salty._walk(holder) if isinstance(w, salty.ThemedScrollbar)]
assert bars and any(
    bar._min_thumb >= 32 and int(str(bar.cget("width"))) == 18 for bar in bars
)
print("main chat cursor, border and scrollbar OK")


class _Click:
    widget = main


assert salty._dismiss_startup_hint_fn is not None
salty._on_chat_click(_Click())
assert salty._hint_shown is True
assert salty._pending_click is not None
salty._cancel_pending_click()
print("startup hint click dismisses and arms the pop-out OK")

root.destroy()
print("ALL RUNTIME CHECKS PASS")
