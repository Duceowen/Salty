"""
Salty
=====

A port of the "Communicator" plugin from Elite Observatory Core to
EDMarketConnector.

It records all in-game chat messages (sent and received), displays them in the
EDMC main window (with an optional larger pop-out window), lets you filter by
channel, and can raise on-screen notifications for incoming messages through
the Modern Overlay plugin.

Original plugin: Observatory Communicator by Vithigar (part of
https://github.com/Xjph/ObservatoryCore), MIT licensed.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

import myNotebook as nb
from config import appname, config

try:
    from theme import theme
except Exception:  # pragma: no cover - theme is optional
    theme = None

__version__ = "1.0.0"

PLUGIN_DISPLAY_NAME = "Salty"
PLUGIN_INTERNAL_NAME = "Salty"

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
plugin_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(f"{appname}.{plugin_name}")
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s"
    )
    _formatter.default_time_format = "%Y-%m-%d %H:%M:%S"
    _formatter.default_msec_format = "%s.%03d"
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
CONFIG_PREFIX = "salty"

CHANNELS = ("local", "system", "private", "wing", "squadron", "npc")
CHANNEL_LABELS = {
    "local": "Local",
    "system": "System",
    "private": "Private",
    "wing": "Wing",
    "squadron": "Squadron",
    "npc": "NPC",
}
CHANNEL_COLORS = {
    "local": "#ffcf00",
    "system": "#00d7ff",
    "private": "#ff7ad9",
    "wing": "#59a5ff",
    "squadron": "#35d07f",
    "npc": "#ff9f43",
}

DEFAULT_SHOW = {
    "local": True,
    "system": True,
    "private": True,
    "wing": True,
    "squadron": True,
    "npc": False,
}
DEFAULT_NOTIFY = {
    "local": True,
    "system": True,
    "private": True,
    "wing": True,
    "squadron": True,
    "npc": False,
}

DEFAULT_OVERLAY_ENABLED = True
# Default overlay anchor: left side of the screen, 30% of the way down from the
# top. The live default is derived from the screen size at runtime (see
# _overlay_default_pos); these values are the static fallbacks.
DEFAULT_OVERLAY_X = 32
DEFAULT_OVERLAY_Y = 324
DEFAULT_OVERLAY_TTL = 8
DEFAULT_OVERLAY_SIZE = "large"
OVERLAY_SIZES = ("normal", "large", "huge")

DEFAULT_TIMESTAMPS = True
DEFAULT_ORIGINS = True

MAX_MESSAGES = 1000

NOTIFY_ID_PREFIX = "salty-"

# Vertical spacing (in overlay units) between stacked notifications, per size.
OVERLAY_LINE_STEP = {"normal": 20, "large": 28, "huge": 36}
# Maximum number of simultaneous on-screen notifications (oldest are cleared).
OVERLAY_MAX_STACK = 8

# --------------------------------------------------------------------------- #
# Runtime state
# --------------------------------------------------------------------------- #
_messages: List[Dict[str, Any]] = []

_main_frame: Optional[tk.Frame] = None
_filter_vars: Dict[str, tk.BooleanVar] = {}
_timestamp_var: Optional[tk.BooleanVar] = None
_origin_var: Optional[tk.BooleanVar] = None
_freeze_var: Optional[tk.BooleanVar] = None
_views: List[tk.Text] = []
_popout: Optional[tk.Toplevel] = None
_settings_win: Optional[tk.Toplevel] = None

_prefs_vars: Dict[str, Any] = {}

# Overlay (Modern Overlay) state
_overlay_send = None
_overlay_import_done = False
_overlay_group_registered = False
_overlay_active: List[Dict[str, Any]] = []
_overlay_seq = 0


# --------------------------------------------------------------------------- #
# Config helpers
# --------------------------------------------------------------------------- #
def _cfg_bool(key: str, default: bool) -> bool:
    try:
        return config.get_bool(key, default)
    except Exception:
        return default


def _cfg_int(key: str, default: int) -> int:
    try:
        return config.get_int(key, default)
    except Exception:
        return default


def _cfg_str(key: str, default: str) -> str:
    try:
        return config.get_str(key, default) or default
    except Exception:
        return default


def _show_key(channel: str) -> str:
    return f"{CONFIG_PREFIX}_show_{channel}"


def _notify_key(channel: str) -> str:
    return f"{CONFIG_PREFIX}_notify_{channel}"


def _channel_shown(channel: str) -> bool:
    var = _filter_vars.get(channel)
    if var is not None:
        try:
            return bool(var.get())
        except Exception:
            pass
    return _cfg_bool(_show_key(channel), DEFAULT_SHOW.get(channel, True))


def _channel_notify(channel: str) -> bool:
    return _cfg_bool(_notify_key(channel), DEFAULT_NOTIFY.get(channel, True))


def _timestamp_key() -> str:
    return f"{CONFIG_PREFIX}_timestamps"


def _origin_key() -> str:
    return f"{CONFIG_PREFIX}_origins"


def _ensure_filter_vars() -> None:
    """Lazily create the shared show/timestamp/origin Tk variables (needs a Tk root)."""
    global _timestamp_var, _origin_var
    if not _filter_vars:
        for channel in CHANNELS:
            _filter_vars[channel] = tk.BooleanVar(
                value=_cfg_bool(_show_key(channel), DEFAULT_SHOW.get(channel, True))
            )
    if _timestamp_var is None:
        _timestamp_var = tk.BooleanVar(value=_cfg_bool(_timestamp_key(), DEFAULT_TIMESTAMPS))
    if _origin_var is None:
        _origin_var = tk.BooleanVar(value=_cfg_bool(_origin_key(), DEFAULT_ORIGINS))


def _timestamps_shown() -> bool:
    if _timestamp_var is not None:
        try:
            return bool(_timestamp_var.get())
        except Exception:
            pass
    return _cfg_bool(_timestamp_key(), DEFAULT_TIMESTAMPS)


def _origins_shown() -> bool:
    if _origin_var is not None:
        try:
            return bool(_origin_var.get())
        except Exception:
            pass
    return _cfg_bool(_origin_key(), DEFAULT_ORIGINS)


def _overlay_default_pos() -> tuple:
    """Default overlay anchor: left side, 30% down from the top of the screen."""
    width = height = 0
    try:
        root = tk._default_root  # type: ignore[attr-defined]
        if root is not None:
            width = int(root.winfo_screenwidth())
            height = int(root.winfo_screenheight())
    except Exception:
        width = height = 0
    x = DEFAULT_OVERLAY_X
    y = DEFAULT_OVERLAY_Y
    if width > 0:
        x = max(8, int(round(width * 0.02)))
    if height > 0:
        y = max(8, int(round(height * 0.30)))
    return x, y


def _is_frozen() -> bool:
    if _freeze_var is None:
        return False
    try:
        return bool(_freeze_var.get())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Channel mapping
# --------------------------------------------------------------------------- #
def _normalise_channel(raw: Optional[str]) -> str:
    """Map an Elite Dangerous channel token onto one of our buckets."""
    token = (raw or "").strip().lower()
    if token in ("starsystem", "system"):
        return "system"
    if token == "local":
        return "local"
    if token == "wing":
        return "wing"
    if token == "squadron":
        return "squadron"
    if token == "npc":
        return "npc"
    # player / friend / voicechat / direct and anything unknown -> private
    return "private"


def _event_time(entry: Dict[str, Any]) -> str:
    raw = entry.get("timestamp")
    if isinstance(raw, str) and raw:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                return dt.astimezone().strftime("%H:%M:%S")
            except ValueError:
                continue
    return datetime.now().strftime("%H:%M:%S")


# --------------------------------------------------------------------------- #
# Modern Overlay integration
# --------------------------------------------------------------------------- #
def _import_edmcoverlay():
    """Best-effort import of the Modern Overlay legacy compatibility facade."""
    try:
        from EDMCOverlay import edmcoverlay  # type: ignore
        return edmcoverlay
    except Exception:
        pass

    try:
        plugins_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        overlay_dir = os.path.join(plugins_dir, "ModernOverlay")
        if os.path.isdir(overlay_dir) and overlay_dir not in sys.path:
            sys.path.append(overlay_dir)
        from EDMCOverlay import edmcoverlay  # type: ignore
        return edmcoverlay
    except Exception:
        pass

    try:
        from edmcoverlay import edmcoverlay  # type: ignore
        return edmcoverlay
    except Exception:
        return None


def _get_overlay_send():
    global _overlay_send, _overlay_import_done
    if _overlay_import_done:
        return _overlay_send

    _overlay_import_done = True
    module = _import_edmcoverlay()
    if module is None:
        logger.info("Modern Overlay not found; on-screen notifications unavailable")
        return None

    send = getattr(module, "send_overlay_message", None)
    if send is None:
        logger.info("Modern Overlay has no send_overlay_message; notifications unavailable")
        return None

    _overlay_send = send
    logger.info("Modern Overlay notifications enabled")
    return _overlay_send


def _ensure_overlay_group() -> None:
    global _overlay_group_registered
    if _overlay_group_registered:
        return
    try:
        from overlay_plugin import overlay_api  # type: ignore
    except Exception:
        return

    define_group = getattr(overlay_api, "define_plugin_group", None)
    if define_group is None:
        return

    try:
        define_group(
            plugin_name=PLUGIN_DISPLAY_NAME,
            plugin_matching_prefixes=[NOTIFY_ID_PREFIX],
            plugin_group_name="Salty Messages",
            plugin_group_prefixes=[NOTIFY_ID_PREFIX],
            plugin_group_anchor="nw",
            plugin_group_offset_x=0,
            plugin_group_offset_y=0,
            payload_justification="left",
            controller_preview_box_mode="last",
        )
        _overlay_group_registered = True
        logger.info("Registered Salty overlay group with Modern Overlay")
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Could not register Salty overlay group: %s", exc)


def _toast_clear(send, overlay_id: str) -> None:
    """Tell the overlay to remove a single notification immediately."""
    try:
        send({
            "event": "LegacyOverlay",
            "type": "message",
            "id": overlay_id,
            "text": "",
            "ttl": 0,
            "x": 0,
            "y": 0,
        })
    except Exception:
        pass


def _notify(channel: str, sender: str, message: str) -> None:
    if not _cfg_bool(f"{CONFIG_PREFIX}_overlay", DEFAULT_OVERLAY_ENABLED):
        return
    if not _channel_notify(channel):
        return

    send = _get_overlay_send()
    if send is None:
        return

    _ensure_overlay_group()

    size = _cfg_str(f"{CONFIG_PREFIX}_overlay_size", DEFAULT_OVERLAY_SIZE)
    if size not in OVERLAY_SIZES:
        size = DEFAULT_OVERLAY_SIZE
    step = OVERLAY_LINE_STEP.get(size, OVERLAY_LINE_STEP[DEFAULT_OVERLAY_SIZE])

    default_x, default_y = _overlay_default_pos()
    base_x = _cfg_int(f"{CONFIG_PREFIX}_overlay_x", default_x)
    base_y = _cfg_int(f"{CONFIG_PREFIX}_overlay_y", default_y)
    ttl = max(1, _cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL))

    global _overlay_seq
    _overlay_seq += 1
    now = time.monotonic()

    # Drop notifications that have already expired.
    _overlay_active[:] = [e for e in _overlay_active if e["expire"] > now]

    # Enforce the maximum number of simultaneous lines (evict oldest).
    while len(_overlay_active) >= OVERLAY_MAX_STACK:
        _toast_clear(send, _overlay_active.pop()["id"])

    # Newest notification goes on top; older ones are pushed down.
    _overlay_active.insert(0, {
        "id": f"{NOTIFY_ID_PREFIX}{channel}-{_overlay_seq}",
        "text": f"{sender}: {message}",
        "color": CHANNEL_COLORS.get(channel, "#ffffff"),
        "size": size,
        "expire": now + ttl,
    })

    # Re-emit every active notification so they stack without overlapping.
    for index, entry in enumerate(_overlay_active):
        remaining = max(1, int(round(entry["expire"] - now)))
        payload = {
            "event": "LegacyOverlay",
            "type": "message",
            "id": entry["id"],
            "plugin": PLUGIN_DISPLAY_NAME,
            "text": entry["text"],
            "color": entry["color"],
            "size": entry["size"],
            "x": base_x,
            "y": base_y + index * step,
            "ttl": remaining,
        }
        try:
            send(payload)
        except Exception:
            logger.exception("Failed to send overlay notification")

    logger.debug(
        "Overlay notifications updated: %d active, ys=%s (newest: %s)",
        len(_overlay_active),
        [base_y + i * step for i in range(len(_overlay_active))],
        _overlay_active[0]["text"],
    )


# --------------------------------------------------------------------------- #
# Message store / rendering
# --------------------------------------------------------------------------- #
def _format_prefix(item: Dict[str, Any]) -> str:
    label = CHANNEL_LABELS.get(item["channel"], item["channel"])
    bits: List[str] = []
    if _timestamps_shown():
        bits.append(f"[{item['time']}]")
    if _origins_shown():
        bits.append(f"[{label}]")
    prefix = (" ".join(bits) + " ") if bits else ""
    return f"{prefix}{item['from']}: "


def _trim(text: tk.Text) -> None:
    try:
        lines = int(text.index("end-1c").split(".")[0])
        if lines > MAX_MESSAGES:
            text.delete("1.0", f"{lines - MAX_MESSAGES}.0")
    except Exception:
        pass


def _append_item(text: tk.Text, item: Dict[str, Any]) -> None:
    text.configure(state="normal")
    try:
        text.insert("end", _format_prefix(item), (f"ch_{item['channel']}",))
        text.insert("end", f"{item['message']}\n")
        _trim(text)
        if not _is_frozen():
            text.see("end")
    finally:
        text.configure(state="disabled")


def _render_all(text: tk.Text) -> None:
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.configure(state="disabled")
    for item in _messages:
        if _channel_shown(item["channel"]):
            _append_item(text, item)


def _add_message(channel: str, sender: str, message: str, incoming: bool, entry: Dict[str, Any]) -> None:
    item = {
        "time": _event_time(entry),
        "channel": channel,
        "from": sender,
        "message": message or "",
        "incoming": incoming,
    }
    _messages.append(item)
    if len(_messages) > MAX_MESSAGES:
        del _messages[: len(_messages) - MAX_MESSAGES]

    if _channel_shown(channel):
        for text in list(_views):
            try:
                _append_item(text, item)
            except Exception:
                logger.exception("Failed to append message to a chat view")

    if incoming:
        _notify(channel, sender, item["message"])


def _rerender_views() -> None:
    for text in list(_views):
        try:
            _render_all(text)
        except Exception:
            logger.exception("Failed to re-render a chat view")


def _themed_confirm(parent: tk.Misc, message: str) -> bool:
    """Show a modal Yes/No dialog styled with EDMC's active theme colours."""
    try:
        dlg = tk.Toplevel(parent)
    except Exception:
        return True

    bg, fg = _theme_colors()
    dlg.title(PLUGIN_DISPLAY_NAME)
    dlg.configure(background=bg)
    dlg.resizable(False, False)

    result = {"value": False}

    label = tk.Label(
        dlg, text=message, background=bg, foreground=fg,
        font=_ui_font(0), padx=24, pady=18, anchor="w", justify="left",
    )
    label.pack(fill="x")

    def _choose(value: bool) -> None:
        result["value"] = value
        try:
            dlg.grab_release()
        except Exception:
            pass
        try:
            dlg.destroy()
        except Exception:
            pass

    btns = tk.Frame(dlg, background=bg)
    btns.pack(fill="x", padx=12, pady=(0, 12))

    def _mk(text: str, value: bool) -> tk.Button:
        return tk.Button(
            btns, text=text, width=10, command=lambda: _choose(value),
            background=bg, foreground=fg, activebackground=bg, activeforeground=fg,
            highlightthickness=0, highlightbackground=bg, font=_ui_font(0),
        )

    no = _mk("No", False)
    yes = _mk("Yes", True)
    no.pack(side="right", padx=(8, 0))
    yes.pack(side="right")

    dlg.protocol("WM_DELETE_WINDOW", lambda: _choose(False))
    dlg.bind("<Escape>", lambda _e: _choose(False))
    dlg.bind("<Return>", lambda _e: _choose(True))

    try:
        dlg.update_idletasks()
        if parent is not None:
            px = parent.winfo_rootx() + (parent.winfo_width() - dlg.winfo_width()) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_height()) // 2
            dlg.geometry(f"+{max(0, px)}+{max(0, py)}")
    except Exception:
        pass

    try:
        dlg.transient(parent.winfo_toplevel() if parent is not None else None)
    except Exception:
        pass

    _theme_titlebar(dlg)

    try:
        dlg.grab_set()
        dlg.focus_force()
        dlg.wait_window()
    except Exception:
        pass

    return bool(result["value"])


def _confirm_clear() -> bool:
    """Ask the user to confirm clearing the chat history."""
    parent = None
    try:
        if _popout is not None and _popout.winfo_exists():
            parent = _popout
        elif _main_frame is not None and _main_frame.winfo_exists():
            parent = _main_frame.winfo_toplevel()
    except Exception:
        parent = None
    return _themed_confirm(parent, "Clear chat history?")


def _clear_messages() -> None:
    if not _confirm_clear():
        return
    _messages.clear()
    for text in list(_views):
        try:
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.configure(state="disabled")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# UI construction
# --------------------------------------------------------------------------- #
def _tag_text(text: tk.Text) -> None:
    for channel in CHANNELS:
        text.tag_configure(f"ch_{channel}", foreground=CHANNEL_COLORS[channel])


def _walk(widget: tk.Widget):
    """Yield a widget and all of its descendants."""
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield from _walk(child)


class ThemedScrollbar(tk.Canvas):
    """
    A Canvas-drawn scrollbar that can follow EDMC's theme colours.

    A classic ``tk.Scrollbar`` keeps its native (light) thumb on Windows and
    cannot be recoloured reliably, so we draw the trough and thumb ourselves on
    a ``tk.Canvas`` (which is fully colourable).
    """

    def __init__(self, master, command=None, background="grey4",
                 foreground="#ff8000", width=14, **kw):
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        # A Canvas defaults to ~265px tall, which would force the whole chat row
        # to that height. Keep the requested height tiny; fill="y" stretches it
        # to match the neighbouring Text widget.
        kw.setdefault("height", 1)
        super().__init__(master, width=width, background=background, **kw)
        self.command = command
        self._trough = background
        self._thumb = foreground
        self._thumb_active = foreground
        self._first = 0.0
        self._last = 1.0
        self._drag = False
        self._offset = 0
        self._top = 0
        self._bottom = 0
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_move)
        self.bind("<ButtonRelease-1>", self._on_release)

    def apply_theme(self, bg=None, fg=None) -> None:
        if bg:
            self._trough = bg
            try:
                self.configure(background=bg)
            except Exception:
                pass
        if fg:
            self._thumb = fg
            self._thumb_active = fg
        self._redraw()

    def set(self, first, last) -> None:
        try:
            self._first = float(first)
            self._last = float(last)
        except Exception:
            return
        self._redraw()

    def _redraw(self) -> None:
        self.delete("thumb")
        w = self.winfo_width()
        h = self.winfo_height()
        if h <= 1 or w <= 1:
            return
        if self._last - self._first >= 0.999:
            self._top = 0
            self._bottom = h
            return
        top = int(self._first * h)
        bottom = int(self._last * h)
        if bottom - top < 8:
            bottom = min(h, top + 8)
        self._top = top
        self._bottom = bottom
        color = self._thumb_active if self._drag else self._thumb
        self.create_rectangle(2, top + 1, w - 2, bottom - 1, fill=color, outline="", tags="thumb")

    def _on_press(self, event) -> None:
        h = self.winfo_height() or 1
        if self._top <= event.y <= self._bottom:
            self._drag = True
            self._offset = event.y - self._top
        else:
            self._drag = True
            self._offset = max(0, (self._bottom - self._top) // 2)
            self._move_to(event.y - self._offset, h)
        self._redraw()

    def _on_move(self, event) -> None:
        if not self._drag:
            return
        self._move_to(event.y - self._offset, self.winfo_height() or 1)

    def _on_release(self, _event) -> None:
        self._drag = False
        self._redraw()

    def _move_to(self, top, height) -> None:
        if not self.command:
            return
        frac = max(0.0, min(1.0, top / height))
        self.command("moveto", frac)


def _theme_colors() -> tuple:
    """Return the (background, foreground) colours of EDMC's active theme."""
    if theme is not None:
        current = getattr(theme, "current", None)
        if isinstance(current, dict):
            bg = current.get("background")
            fg = current.get("foreground")
            if isinstance(bg, str) and isinstance(fg, str) and bg and fg:
                return bg, fg

        probe = None
        try:
            probe = tk.Label(_main_frame if _main_frame is not None else None)
            theme.update(probe)
            bg = str(probe.cget("background"))
            fg = str(probe.cget("foreground"))
            if bg and fg:
                return bg, fg
        except Exception:
            pass
        finally:
            if probe is not None:
                try:
                    probe.destroy()
                except Exception:
                    pass

    try:
        is_dark = config.get_int("theme") in (1, 2)
    except Exception:
        is_dark = False
    if is_dark:
        return "grey4", _cfg_str("dark_text", "#ff8000")
    return "SystemWindow", "SystemWindowText"


def _colorref(window: tk.Widget, color: str) -> int:
    """Convert a Tk colour name to a Win32 COLORREF (0x00BBGGRR)."""
    try:
        r, g, b = window.winfo_rgb(color)
    except Exception:
        return 0
    return ((b >> 8) & 0xFF) << 16 | ((g >> 8) & 0xFF) << 8 | ((r >> 8) & 0xFF)


def _theme_titlebar(window: tk.Widget) -> None:
    """Apply EDMC's theme colours to a native Windows title bar."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        handle = window.winfo_id()
        user32 = ctypes.windll.user32
        hwnd = user32.GetAncestor(handle, 2) or handle
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        bg, fg = _theme_colors()
        if bg:
            value = ctypes.c_uint(_colorref(window, bg))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(value), ctypes.sizeof(value))
        if fg:
            value = ctypes.c_uint(_colorref(window, fg))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def _ui_font(delta: int = 0):
    """Return a default-font spec, resized by ``delta`` points."""
    try:
        base = tkfont.nametofont("TkDefaultFont")
        size = base.actual("size")
        if size < 0:
            size = -size
        return (base.actual("family"), size + delta)
    except Exception:
        return None


def _style_tree(root: tk.Widget, bg: str, fg: str) -> None:
    """Recolour every widget under ``root`` to match the active EDMC theme."""
    for widget in _walk(root):
        try:
            if isinstance(widget, ThemedScrollbar):
                widget.apply_theme(bg, fg)
            elif isinstance(widget, (tk.Toplevel, tk.Frame)):
                widget.configure(background=bg)
            elif isinstance(widget, tk.Checkbutton):
                widget.configure(
                    background=bg,
                    foreground=fg,
                    activebackground=bg,
                    activeforeground=fg,
                    disabledforeground=fg,
                    selectcolor=bg,
                    highlightthickness=0,
                    bd=0,
                )
            elif isinstance(widget, tk.Scrollbar):
                widget.configure(
                    background=fg,
                    troughcolor=bg,
                    activebackground=fg,
                    highlightthickness=0,
                    bd=0,
                    relief="flat",
                    elementborderwidth=0,
                )
            elif isinstance(widget, tk.Menubutton):
                widget.configure(
                    background=bg,
                    foreground=fg,
                    activebackground=bg,
                    activeforeground=fg,
                    highlightthickness=0,
                )
            elif isinstance(widget, tk.Menu):
                widget.configure(
                    background=bg,
                    foreground=fg,
                    activebackground=fg,
                    activeforeground=bg,
                    borderwidth=0,
                )
            elif isinstance(widget, tk.Button):
                widget.configure(
                    background=bg,
                    foreground=fg,
                    activebackground=bg,
                    activeforeground=fg,
                    highlightthickness=0,
                )
            elif isinstance(widget, tk.Entry):
                widget.configure(
                    background=bg,
                    foreground=fg,
                    insertbackground=fg,
                    highlightthickness=0,
                    highlightbackground=bg,
                )
            elif isinstance(widget, tk.Text):
                widget.configure(background=bg, foreground=fg, insertbackground=fg)
            elif isinstance(widget, tk.Label):
                widget.configure(background=bg, foreground=fg)
        except Exception:
            pass


def _style_chat_texts() -> None:
    """
    Apply the active EDMC theme to our whole widget tree.

    EDMC's ``theme.update()`` skips widgets it considers explicitly styled
    (notably ``tk.Text``) and never themes classic scrollbars, so we recolour
    everything ourselves from the live theme colours.
    """
    bg, fg = _theme_colors()

    if _main_frame is not None:
        _style_tree(_main_frame, bg, fg)
    if _popout is not None:
        _style_tree(_popout, bg, fg)
    if _settings_win is not None:
        try:
            if _settings_win.winfo_exists():
                _style_tree(_settings_win, bg, fg)
                _theme_titlebar(_settings_win)
        except Exception:
            pass

    for text in list(_views):
        try:
            text.configure(background=bg, foreground=fg, insertbackground=fg)
        except Exception:
            pass

    if _popout is not None:
        try:
            if _popout.winfo_exists():
                _theme_titlebar(_popout)
        except Exception:
            pass


def _register_view(text: tk.Text) -> None:
    if text not in _views:
        _views.append(text)
    _render_all(text)


def _unregister_view(text: tk.Text) -> None:
    if text in _views:
        _views.remove(text)


def _on_filter_change() -> None:
    for channel in CHANNELS:
        var = _filter_vars.get(channel)
        if var is not None:
            try:
                config.set(_show_key(channel), bool(var.get()))
            except Exception:
                logger.exception("Failed to persist filter for %s", channel)
    _rerender_views()


def _on_timestamps_change() -> None:
    try:
        config.set(_timestamp_key(), _timestamps_shown())
    except Exception:
        logger.exception("Failed to persist timestamp setting")
    _rerender_views()


def _on_origins_change() -> None:
    try:
        config.set(_origin_key(), _origins_shown())
    except Exception:
        logger.exception("Failed to persist origin setting")
    _rerender_views()


def _make_toggle_checks(parent: tk.Widget, include_timestamp: bool,
                        include_origin: bool, font_delta: int) -> List[tk.Checkbutton]:
    """Create the channel (and optional timestamp/origin) checkboxes."""
    _ensure_filter_vars()
    checks: List[tk.Checkbutton] = []
    for channel in CHANNELS:
        checks.append(tk.Checkbutton(
            parent,
            text=CHANNEL_LABELS[channel],
            variable=_filter_vars[channel],
            command=_on_filter_change,
            font=_ui_font(font_delta),
            anchor="w",
        ))
    if include_timestamp:
        checks.append(tk.Checkbutton(
            parent,
            text="Time",
            variable=_timestamp_var,
            command=_on_timestamps_change,
            font=_ui_font(font_delta),
            anchor="w",
        ))
    if include_origin:
        checks.append(tk.Checkbutton(
            parent,
            text="Origin",
            variable=_origin_var,
            command=_on_origins_change,
            font=_ui_font(font_delta),
            anchor="w",
        ))
    return checks


def _build_toggle_grid(parent: tk.Widget, *, include_timestamp: bool = False,
                       include_origin: bool = False, columns: int = 3,
                       font_delta: int = 0, padx: int = 6,
                       pady: int = 2) -> List[tk.Checkbutton]:
    """Lay the checkboxes out in a fixed grid (deterministic size, no reflow)."""
    checks = _make_toggle_checks(parent, include_timestamp, include_origin, font_delta)
    for index, check in enumerate(checks):
        check.grid(row=index // columns, column=index % columns,
                   sticky="w", padx=padx, pady=pady)
    return checks


def _build_toggle_strip(parent: tk.Widget, *, include_timestamp: bool = False,
                        include_origin: bool = False, font_delta: int = 1,
                        padx: int = 6, pady: int = 2) -> List[tk.Checkbutton]:
    """Create the channel (and optional timestamp/origin) checkboxes, reflowing to fit."""
    checks = _make_toggle_checks(parent, include_timestamp, include_origin, font_delta)

    state: Dict[str, Any] = {"sig": None}

    def _layout(_event=None) -> None:
        try:
            avail = parent.winfo_width()
        except Exception:
            return
        if avail <= 1 or not checks:
            return
        row = col = cell = 0
        placements = []
        for check in checks:
            width = check.winfo_reqwidth() + padx * 2
            if col > 0 and cell + width > avail:
                row += 1
                col = 0
                cell = 0
            placements.append((check, row, col))
            cell += width
            col += 1
        sig = tuple((c, r, cc) for c, r, cc in placements)
        if state["sig"] == sig:
            return
        state["sig"] = sig
        for check, r, c in placements:
            check.grid_configure(row=r, column=c, sticky="w", padx=padx, pady=pady)

    for check in checks:
        check.grid(row=0, column=0, sticky="w", padx=padx, pady=pady)
    parent.bind("<Configure>", _layout, add="+")
    try:
        parent.after_idle(_layout)
        parent.after(200, _layout)
    except Exception:
        pass
    return checks


def _save_overlay_settings(overlay_var, x_var, y_var, ttl_var, size_var) -> None:
    try:
        config.set(f"{CONFIG_PREFIX}_overlay", bool(overlay_var.get()))
        config.set(f"{CONFIG_PREFIX}_overlay_x", _to_int(x_var.get(), DEFAULT_OVERLAY_X))
        config.set(f"{CONFIG_PREFIX}_overlay_y", _to_int(y_var.get(), DEFAULT_OVERLAY_Y))
        config.set(f"{CONFIG_PREFIX}_overlay_ttl", _to_int(ttl_var.get(), DEFAULT_OVERLAY_TTL))
        size = size_var.get()
        config.set(
            f"{CONFIG_PREFIX}_overlay_size",
            size if size in OVERLAY_SIZES else DEFAULT_OVERLAY_SIZE,
        )
    except Exception:
        logger.exception("Failed to save Salty overlay settings")


def _open_settings() -> None:
    """Open the themed Salty settings window (channels, timestamps, overlay)."""
    global _settings_win

    if _settings_win is not None:
        try:
            if _settings_win.winfo_exists():
                _settings_win.deiconify()
                _settings_win.lift()
                _settings_win.focus_force()
                return
        except Exception:
            pass
        _settings_win = None

    parent = None
    for candidate in (_popout, _main_frame):
        try:
            if candidate is not None and candidate.winfo_exists():
                parent = candidate
                break
        except Exception:
            continue
    if parent is None:
        return

    try:
        dlg = tk.Toplevel(parent)
    except Exception:
        logger.exception("Could not open Salty settings window")
        return

    _settings_win = dlg
    # Build the window hidden and only show it once it has been sized and
    # positioned, so it never flashes open at the OS default location first.
    try:
        dlg.withdraw()
    except Exception:
        pass
    bg, fg = _theme_colors()
    dlg.title(f"{PLUGIN_DISPLAY_NAME} Settings")
    dlg.configure(background=bg)
    dlg.resizable(True, True)

    body = tk.Frame(dlg, background=bg)
    body.pack(fill="both", expand=True, padx=14, pady=12)

    tk.Label(body, text="Show messages in:", background=bg, foreground=fg,
             font=_ui_font(0)).pack(anchor="w")
    strip = tk.Frame(body, background=bg)
    strip.pack(fill="x", pady=(2, 8))
    _build_toggle_grid(strip, include_timestamp=True, include_origin=True, font_delta=0)

    default_x, default_y = _overlay_default_pos()
    overlay_var = tk.BooleanVar(value=_cfg_bool(f"{CONFIG_PREFIX}_overlay", DEFAULT_OVERLAY_ENABLED))
    x_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_x", default_x)))
    y_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_y", default_y)))
    ttl_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL)))
    size_var = tk.StringVar(value=_cfg_str(f"{CONFIG_PREFIX}_overlay_size", DEFAULT_OVERLAY_SIZE))
    if size_var.get() not in OVERLAY_SIZES:
        size_var.set(DEFAULT_OVERLAY_SIZE)

    tk.Checkbutton(
        body,
        text="On-screen notifications (requires Modern Overlay)",
        variable=overlay_var,
        background=bg, foreground=fg, activebackground=bg, activeforeground=fg,
        selectcolor=bg, highlightthickness=0, bd=0, font=_ui_font(0), anchor="w",
    ).pack(anchor="w", pady=(0, 8))

    grid = tk.Frame(body, background=bg)
    grid.pack(fill="x")

    def _label(text: str, row: int, col: int) -> None:
        tk.Label(grid, text=text, background=bg, foreground=fg,
                 font=_ui_font(0)).grid(row=row, column=col, sticky="w", pady=2)

    def _entry(var: tk.StringVar, row: int, col: int) -> None:
        tk.Entry(grid, textvariable=var, width=6, justify="right",
                 background=bg, foreground=fg, insertbackground=fg,
                 highlightthickness=0, bd=1).grid(row=row, column=col, sticky="w",
                                                  padx=(4, 14), pady=2)

    _label("Position X:", 0, 0)
    _entry(x_var, 0, 1)
    _label("Y:", 0, 2)
    _entry(y_var, 0, 3)
    _label("Duration (s):", 1, 0)
    _entry(ttl_var, 1, 1)
    _label("Size:", 1, 2)
    size_menu = tk.OptionMenu(grid, size_var, *OVERLAY_SIZES)
    size_menu.configure(background=bg, foreground=fg, activebackground=bg,
                        activeforeground=fg, highlightthickness=0, bd=1, width=6,
                        anchor="w", font=_ui_font(0))
    size_menu["menu"].configure(background=bg, foreground=fg,
                                activebackground=fg, activeforeground=bg, borderwidth=0)
    size_menu.grid(row=1, column=3, sticky="w", padx=(4, 0), pady=2)

    btns = tk.Frame(body, background=bg)
    btns.pack(fill="x", pady=(12, 0))

    def _close() -> None:
        global _settings_win
        _save_overlay_settings(overlay_var, x_var, y_var, ttl_var, size_var)
        try:
            dlg.destroy()
        except Exception:
            pass
        _settings_win = None

    tk.Button(btns, text="Close", width=10, command=_close, background=bg, foreground=fg,
              activebackground=bg, activeforeground=fg, highlightthickness=0,
              font=_ui_font(0)).pack(side="right")

    dlg.protocol("WM_DELETE_WINDOW", _close)
    dlg.bind("<Escape>", lambda _e: _close())

    if theme is not None:
        try:
            theme.update(dlg)
        except Exception:
            pass
    _style_tree(dlg, bg, fg)
    _theme_titlebar(dlg)

    def _retheme(_event=None) -> None:
        # Re-apply once the window is mapped; DWM title-bar attributes are only
        # honoured reliably after the frame exists, and EDMC may re-theme on map.
        try:
            new_bg, new_fg = _theme_colors()
            _style_tree(dlg, new_bg, new_fg)
            _theme_titlebar(dlg)
        except Exception:
            pass

    try:
        dlg.bind("<Map>", _retheme, add="+")
        dlg.after_idle(_retheme)
        dlg.after(300, _retheme)
    except Exception:
        pass

    try:
        dlg.transient(parent.winfo_toplevel())
    except Exception:
        pass

    try:
        # Size and position while still hidden, then reveal in one step.
        dlg.update_idletasks()
        width = dlg.winfo_reqwidth()
        height = dlg.winfo_reqheight()
        dlg.minsize(width, height)
        px = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        dlg.geometry(f"{width}x{height}+{max(0, px)}+{max(0, py)}")
    except Exception:
        pass

    try:
        dlg.deiconify()
        dlg.lift()
        dlg.focus_force()
    except Exception:
        pass


def _open_popout() -> None:
    global _popout

    if _popout is not None:
        try:
            if _popout.winfo_exists():
                _popout.deiconify()
                _popout.lift()
                _popout.focus_force()
                return
        except Exception:
            pass

    parent = _main_frame if _main_frame is not None else None
    if parent is None:
        return

    try:
        _popout = tk.Toplevel(parent)
    except Exception:
        logger.exception("Could not create Salty pop-out window")
        _popout = None
        return

    _popout.title(PLUGIN_DISPLAY_NAME)
    _popout.geometry("560x360")
    _popout.minsize(320, 200)

    # Pack the bottom controls first (from the bottom edge) so that shrinking the
    # window never clips the Clear button / Pause Chat checkbutton; the chat area
    # absorbs whatever space is left.
    bottom = tk.Frame(_popout)
    bottom.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
    tk.Button(bottom, text="Clear", command=_clear_messages, font=_ui_font(1)).pack(side="left")
    freeze = tk.Checkbutton(bottom, text="Pause Chat", variable=_freeze_var, font=_ui_font(1))
    freeze.pack(side="left", padx=(8, 0))

    # Channel + timestamp toggles, tucked just above the bottom controls so they
    # are always reachable (packed bottom-up, after the controls row).
    toggles = tk.Frame(_popout)
    toggles.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
    _build_toggle_strip(toggles, include_timestamp=True, include_origin=True, font_delta=1)

    container = tk.Frame(_popout)
    container.pack(fill="both", expand=True, padx=4, pady=4)

    text = tk.Text(container, wrap="word", state="disabled", height=16, width=64)
    text.pack(side="left", fill="both", expand=True)
    bg, fg = _theme_colors()
    scroll = ThemedScrollbar(container, command=text.yview, background=bg, foreground=fg)
    scroll.pack(side="right", fill="y")
    text.configure(yscrollcommand=scroll.set)
    _tag_text(text)

    def _on_close() -> None:
        global _popout
        _unregister_view(text)
        try:
            _popout.destroy()
        except Exception:
            pass
        _popout = None

    _popout.protocol("WM_DELETE_WINDOW", _on_close)

    _register_view(text)

    try:
        _popout.after_idle(_style_chat_texts)
        _popout.after(300, _style_chat_texts)
        _popout.after(150, lambda: _theme_titlebar(_popout))
    except Exception:
        pass


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Build the Salty widget for the EDMC main window."""
    global _main_frame, _freeze_var

    _main_frame = tk.Frame(parent)

    _ensure_filter_vars()

    log_frame = tk.Frame(_main_frame)
    log_frame.pack(fill="x", expand=False, padx=2, pady=2)

    # Fixed height (no vertical fill) so the panel stays compact instead of
    # stretching to fill the whole EDMC window; expand=True lets it grow
    # horizontally as the window is widened.
    text = tk.Text(log_frame, wrap="word", state="disabled", height=4, width=34)
    text.pack(side="left", fill="both", expand=True)
    bg, fg = _theme_colors()
    scroll = ThemedScrollbar(log_frame, command=text.yview, background=bg, foreground=fg)
    scroll.pack(side="right", fill="y")
    text.configure(yscrollcommand=scroll.set)
    _tag_text(text)

    buttons = tk.Frame(_main_frame)
    buttons.pack(fill="x", expand=False, padx=2, pady=(0, 2))

    _freeze_var = tk.BooleanVar(value=False)
    tk.Button(buttons, text="Clear", command=_clear_messages, font=_ui_font(1)).pack(side="left")
    tk.Button(buttons, text="Window", command=_open_popout, font=_ui_font(1)).pack(side="left", padx=(6, 0))
    tk.Checkbutton(buttons, text="Pause Chat", variable=_freeze_var, font=_ui_font(1)).pack(side="left", padx=(6, 0))
    tk.Button(buttons, text="Settings", command=_open_settings, font=_ui_font(1)).pack(side="right")

    _register_view(text)

    if theme is not None:
        try:
            theme.update(_main_frame)
        except Exception:
            pass

    # EDMC re-applies its theme on every <Map> (e.g. after restore), which can
    # reset our scrollbar/text colours, so re-apply ours shortly afterwards.
    def _on_map(_event=None):
        try:
            _main_frame.after(50, _style_chat_texts)
        except Exception:
            pass

    try:
        _main_frame.bind("<Map>", _on_map, add="+")
    except Exception:
        pass

    try:
        _main_frame.after_idle(_style_chat_texts)
        _main_frame.after(600, _style_chat_texts)
    except Exception:
        pass

    return _main_frame


# --------------------------------------------------------------------------- #
# Settings tab
# --------------------------------------------------------------------------- #
def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> Optional[tk.Frame]:
    global _prefs_vars

    _prefs_vars = {}
    _ensure_filter_vars()
    frame = nb.Frame(parent)

    nb.Label(frame, text=PLUGIN_DISPLAY_NAME).grid(row=0, column=0, columnspan=4, sticky="w")
    nb.Label(
        frame,
        text="Records sent and received in-game chat and can show on-screen notifications.",
        wraplength=440,
        justify="left",
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 8))

    row = 2

    nb.Label(frame, text="Show messages in:").grid(
        row=row, column=0, columnspan=4, sticky="w", pady=(0, 2)
    )
    row += 1
    for index, channel in enumerate(CHANNELS):
        nb.Checkbutton(
            frame,
            text=CHANNEL_LABELS[channel],
            variable=_filter_vars[channel],
            command=_on_filter_change,
        ).grid(row=row + index // 3, column=index % 3, sticky="w")
    row += (len(CHANNELS) + 2) // 3

    nb.Checkbutton(
        frame,
        text="Show timestamps",
        variable=_timestamp_var,
        command=_on_timestamps_change,
    ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(4, 2))
    row += 1

    nb.Checkbutton(
        frame,
        text="Show message origin (e.g. [Local], [System], \u2026)",
        variable=_origin_var,
        command=_on_origins_change,
    ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
    row += 1

    overlay_var = tk.BooleanVar(value=_cfg_bool(f"{CONFIG_PREFIX}_overlay", DEFAULT_OVERLAY_ENABLED))
    _prefs_vars["overlay"] = overlay_var
    nb.Checkbutton(
        frame,
        text="Show incoming messages on screen (requires Modern Overlay)",
        variable=overlay_var,
    ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
    row += 1

    nb.Label(frame, text="Notify me on messages in:").grid(
        row=row, column=0, columnspan=4, sticky="w", pady=(0, 2)
    )
    row += 1

    for index, channel in enumerate(CHANNELS):
        var = tk.BooleanVar(value=_cfg_bool(_notify_key(channel), DEFAULT_NOTIFY.get(channel, True)))
        _prefs_vars[f"notify_{channel}"] = var
        nb.Checkbutton(frame, text=CHANNEL_LABELS[channel], variable=var).grid(
            row=row + index // 3, column=index % 3, sticky="w"
        )
    row += (len(CHANNELS) + 2) // 3

    base_row = row + 1

    default_x, default_y = _overlay_default_pos()

    nb.Label(frame, text="Overlay position X:").grid(row=base_row, column=0, sticky="w", pady=(8, 0))
    x_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_x", default_x)))
    _prefs_vars["overlay_x"] = x_var
    nb.EntryMenu(frame, textvariable=x_var, width=6).grid(row=base_row, column=1, sticky="w", pady=(8, 0))

    nb.Label(frame, text="Y:").grid(row=base_row, column=2, sticky="e", pady=(8, 0))
    y_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_y", default_y)))
    _prefs_vars["overlay_y"] = y_var
    nb.EntryMenu(frame, textvariable=y_var, width=6).grid(row=base_row, column=3, sticky="w", pady=(8, 0))

    nb.Label(frame, text="Display duration (s):").grid(row=base_row + 1, column=0, sticky="w")
    ttl_var = tk.StringVar(value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL)))
    _prefs_vars["overlay_ttl"] = ttl_var
    nb.EntryMenu(frame, textvariable=ttl_var, width=6).grid(row=base_row + 1, column=1, sticky="w")

    nb.Label(frame, text="Text size:").grid(row=base_row + 1, column=2, sticky="e")
    size_var = tk.StringVar(value=_cfg_str(f"{CONFIG_PREFIX}_overlay_size", DEFAULT_OVERLAY_SIZE))
    if size_var.get() not in OVERLAY_SIZES:
        size_var.set(DEFAULT_OVERLAY_SIZE)
    _prefs_vars["overlay_size"] = size_var
    size_box = ttk.Combobox(frame, textvariable=size_var, values=list(OVERLAY_SIZES), width=7, state="readonly")
    size_box.grid(row=base_row + 1, column=3, sticky="w")

    # Theme the ttk combobox drop-down list (its popup Listbox ignores ttk styling).
    try:
        tbg, tfg = _theme_colors()
        for opt, val in (
            ("*TCombobox*Listbox.background", tbg),
            ("*TCombobox*Listbox.foreground", tfg),
            ("*TCombobox*Listbox.selectBackground", tfg),
            ("*TCombobox*Listbox.selectForeground", tbg),
        ):
            frame.option_add(opt, val)
    except Exception:
        pass

    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    try:
        config.set(f"{CONFIG_PREFIX}_overlay", bool(_prefs_vars["overlay"].get()))
        for channel in CHANNELS:
            var = _prefs_vars.get(f"notify_{channel}")
            if var is not None:
                config.set(_notify_key(channel), bool(var.get()))
        config.set(f"{CONFIG_PREFIX}_overlay_x", _to_int(_prefs_vars["overlay_x"].get(), DEFAULT_OVERLAY_X))
        config.set(f"{CONFIG_PREFIX}_overlay_y", _to_int(_prefs_vars["overlay_y"].get(), DEFAULT_OVERLAY_Y))
        config.set(f"{CONFIG_PREFIX}_overlay_ttl", _to_int(_prefs_vars["overlay_ttl"].get(), DEFAULT_OVERLAY_TTL))
        size = _prefs_vars["overlay_size"].get()
        config.set(
            f"{CONFIG_PREFIX}_overlay_size",
            size if size in OVERLAY_SIZES else DEFAULT_OVERLAY_SIZE,
        )
    except Exception:
        logger.exception("Failed to save Salty preferences")

    try:
        _style_chat_texts()
    except Exception:
        pass


def _to_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# EDMC plugin hooks
# --------------------------------------------------------------------------- #
def plugin_start3(plugin_dir: str) -> str:
    logger.info("%s v%s loaded", PLUGIN_DISPLAY_NAME, __version__)
    return PLUGIN_INTERNAL_NAME


def plugin_stop() -> None:
    logger.info("%s stopped", PLUGIN_DISPLAY_NAME)


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: Optional[str],
    station: Optional[str],
    entry: Dict[str, Any],
    state: Dict[str, Any],
) -> None:
    event = entry.get("event")

    if event in ("SendText", "ReceiveText"):
        logger.debug("journal_entry received %s: %r", event, entry.get("Message"))

    if event == "SendText":
        channel = _normalise_channel(entry.get("To_Localised") or entry.get("To"))
        sender = cmdr or "You"
        _add_message(channel, sender, entry.get("Message", ""), incoming=False, entry=entry)

    elif event == "ReceiveText":
        channel = _normalise_channel(entry.get("Channel"))
        sender = entry.get("From_Localised") or entry.get("From") or "Unknown"
        message = entry.get("Message_Localised") or entry.get("Message") or ""
        _add_message(channel, sender, message, incoming=True, entry=entry)
