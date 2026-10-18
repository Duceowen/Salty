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
import subprocess
import sys
import textwrap
import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import colorchooser
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

import myNotebook as nb
from config import appname, config

try:
    from theme import theme
except Exception:  # pragma: no cover - theme is optional
    theme = None

__version__ = "1.2.0"

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

CHANNELS = ("local", "system", "private", "wing", "squadron", "squadleaders", "npc")
CHANNEL_LABELS = {
    "local": "Local",
    "system": "System",
    "private": "Private",
    "wing": "Wing",
    "squadron": "Squadron",
    "squadleaders": "Officer",
    "npc": "NPC",
}
CHANNEL_COLORS = {
    "local": "#ffcf00",
    "system": "#00d7ff",
    "private": "#ff7ad9",
    "wing": "#59a5ff",
    "squadron": "#35d07f",
    "squadleaders": "#b388ff",
    "npc": "#ff9f43",
}

DEFAULT_SHOW = {
    "local": True,
    "system": True,
    "private": True,
    "wing": True,
    "squadron": True,
    "squadleaders": True,
    "npc": False,
}
DEFAULT_NOTIFY = {
    "local": True,
    "system": True,
    "private": True,
    "wing": True,
    "squadron": True,
    "squadleaders": True,
    "npc": False,
}

DEFAULT_POPOUT_OPACITY = 100

DEFAULT_OVERLAY_ENABLED = True
# Default overlay anchor: left side, 30% of the way down the visible overlay
# canvas. The live default is derived at runtime from the screen's aspect ratio
# (see _overlay_default_pos); these values are the static fallbacks expressed in
# overlay units (the canvas is 1280x960, see OVERLAY_BASE_WIDTH/HEIGHT).
DEFAULT_OVERLAY_X = 26
DEFAULT_OVERLAY_Y = 288
DEFAULT_OVERLAY_TTL = 8
DEFAULT_OVERLAY_SIZE = "large"
OVERLAY_SIZES = ("normal", "large", "huge")

DEFAULT_TIMESTAMPS = True
DEFAULT_ORIGINS = True
DEFAULT_STAY_ON_TOP = False

# Channels the player can recolour. NPC keeps its built-in colour.
COLOR_CHANNELS = ("local", "system", "private", "wing", "squadron", "squadleaders")

# Overlay notifications wrap near the middle of the requested 30-40 character
# range. Words are never split; a word that does not fit moves to the next line.
OVERLAY_WRAP_WIDTH = 36

DEFAULT_POPOUT_X = 100
DEFAULT_POPOUT_Y = 100
DEFAULT_POPOUT_WIDTH = 560
DEFAULT_POPOUT_HEIGHT = 360

MAX_MESSAGES = 1000
# The compact EDMC widget only shows the newest lines. The pop-out window and
# the chat log file keep the full history, up to MAX_MESSAGES.
MAIN_HISTORY_LIMIT = 30
# The compact EDMC widget shows at most this many chat lines before it scrolls.
# It shrinks to fit a short or empty log so it does not leave a tall blank gap,
# and grows again as messages arrive.
MAIN_TEXT_MAX_LINES = 4

NOTIFY_ID_PREFIX = "salty-"

# Vertical spacing (in overlay units) between stacked notifications, per size.
OVERLAY_LINE_STEP = {"normal": 20, "large": 28, "huge": 36}
# Maximum number of simultaneous on-screen notifications (oldest are cleared).
OVERLAY_MAX_STACK = 8

# Modern Overlay maps legacy payload coordinates onto a fixed 1280x960 canvas
# (ModernOverlay's DEFAULT_WINDOW_BASE_WIDTH/HEIGHT). These are overlay units,
# not screen pixels. On wider-than-4:3 displays the default "fill" scale mode
# shows only the top-left slice of that canvas, so we keep the anchor inside the
# region that is actually visible to prevent notifications rendering off screen.
OVERLAY_BASE_WIDTH = 1280
OVERLAY_BASE_HEIGHT = 960

# Main widget interaction: a single click opens the pop-out window, a double
# click opens settings, a right click offers both. The single-click delay has
# to outlast the platform double-click interval so the two are not confused.
CLICK_ACTION_DELAY_MS = 500

# One-time hint shown inside the chat box at startup, before the saved chat log
# is loaded. A click before it expires dismisses it and opens the pop-out.
STARTUP_HINT_MS = 6000
STARTUP_HINT_TEXT = "Single Click to pop window out Double Click for Options."
HOVER_TIP_TEXT = "Single Click to pop window out Double Click for Options."
# The hover tip waits this long after the pointer enters before it appears,
# then hides itself this long after it appears even if the pointer stays put.
HOVER_TIP_DELAY_MS = 1000
HOVER_TIP_LINGER_MS = 6000
# Shown in the main widget when it is scrolled to the top and older lines exist
# beyond MAIN_HISTORY_LIMIT. A click still opens the pop-out.
HISTORY_HINT_TEXT = "Click the box to expand for more history"

# SendText/ReceiveText tokens that are channels, not commander names.
_NOT_A_COMMANDER = {
    "local",
    "starsystem",
    "system",
    "wing",
    "squadron",
    "squadleaders",
    "squadron leaders",
    "squadron_leaders",
    "squadronleaders",
    "npc",
    "player",
    "friend",
    "voicechat",
    "voice chat",
    "direct",
    "private",
    "commander",
}

# Shown in the main widget while the pop-out window owns the full chat log.
POPOUT_ACTIVE_TEXT = "Chat Pop-out Active"

# Chat logging appends every message to a log file in EDMC's logs folder so the
# history survives an EDMC restart.
DEFAULT_CHAT_LOGGING = True
CHAT_LOG_FILENAME = "SaltyChat.log"

# --------------------------------------------------------------------------- #
# Runtime state
# --------------------------------------------------------------------------- #
_messages: list[dict[str, Any]] = []

_main_frame: tk.Frame | None = None
_main_text: tk.Text | None = None
# True while the one-time startup hint overlay is on screen, so the chat box
# keeps its height until the hint is gone.
_startup_hint_up = False
_history_hint: tk.Label | None = None
_filter_vars: dict[str, tk.BooleanVar] = {}
_timestamp_var: tk.BooleanVar | None = None
_origin_var: tk.BooleanVar | None = None
_freeze_var: tk.BooleanVar | None = None
_topmost_var: tk.BooleanVar | None = None
_views: list[tk.Text] = []
# Set when the main window is rendered. Scroll handling reads it instead of
# scanning the log on every thumb movement.
_main_history_overflow = False
_popout: tk.Toplevel | None = None
_popout_toggles: tk.Frame | None = None
_popout_chat: tk.Frame | None = None
_settings_win: tk.Toplevel | None = None

# Hide from mouse: session-only manual override (auto / hidden / shown) plus
# the last known on-foot state. The persisted option lives in config.
_hide_manual = "auto"
_hide_on_foot = False
_hide_on_foot_seeded = False

_prefs_vars: dict[str, Any] = {}

# Main-widget single/double click arbitration.
_pending_click: str | None = None
_suppress_until = 0.0

# Saved chat log waiting to be shown once the startup hint has been displayed.
_history_pending: list[dict[str, Any]] = []
_history_snapshot_taken = False
_history_flushed = False
_hint_started = False
_hint_shown = False
_dismiss_startup_hint_fn = None

# Overlay (Modern Overlay) state
_overlay_send = None
_overlay_import_done = False
_overlay_group_registered = False
_overlay_active: list[dict[str, Any]] = []
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


def _color_key(channel: str) -> str:
    return f"{CONFIG_PREFIX}_color_{channel}"


def _chat_logging_key() -> str:
    return f"{CONFIG_PREFIX}_chat_logging"


def _chat_logging_enabled() -> bool:
    return _cfg_bool(_chat_logging_key(), DEFAULT_CHAT_LOGGING)


def _stay_on_top_key() -> str:
    return f"{CONFIG_PREFIX}_stay_on_top"


def _hide_on_foot_key() -> str:
    return f"{CONFIG_PREFIX}_hide_from_mouse_on_foot"


def _hide_boxes_key() -> str:
    return f"{CONFIG_PREFIX}_hide_boxes"


def _boxes_hidden() -> bool:
    return _cfg_bool(_hide_boxes_key(), False)


def _popout_opacity_key() -> str:
    return f"{CONFIG_PREFIX}_popout_opacity"


def _popout_opacity() -> int:
    return _cfg_int(_popout_opacity_key(), DEFAULT_POPOUT_OPACITY)


def _stay_on_top_enabled() -> bool:
    var = _topmost_var
    if var is not None:
        try:
            return bool(var.get())
        except Exception:
            pass
    return _cfg_bool(_stay_on_top_key(), DEFAULT_STAY_ON_TOP)


def _ensure_filter_vars() -> None:
    """Lazily create the shared show/timestamp/origin/freeze Tk variables (needs a Tk root)."""
    global _timestamp_var, _origin_var, _freeze_var, _topmost_var
    if not _filter_vars:
        for channel in CHANNELS:
            _filter_vars[channel] = tk.BooleanVar(
                value=_cfg_bool(_show_key(channel), DEFAULT_SHOW.get(channel, True))
            )
    if _timestamp_var is None:
        _timestamp_var = tk.BooleanVar(
            value=_cfg_bool(_timestamp_key(), DEFAULT_TIMESTAMPS)
        )
    if _origin_var is None:
        _origin_var = tk.BooleanVar(value=_cfg_bool(_origin_key(), DEFAULT_ORIGINS))
    if _freeze_var is None:
        _freeze_var = tk.BooleanVar(value=False)
    if _topmost_var is None:
        _topmost_var = tk.BooleanVar(
            value=_cfg_bool(_stay_on_top_key(), DEFAULT_STAY_ON_TOP)
        )


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


def _valid_color(value: str) -> bool:
    text = (value or "").strip()
    if text.startswith("#"):
        hexpart = text[1:]
        return len(hexpart) in (3, 6, 8) and all(
            char in "0123456789abcdefABCDEF" for char in hexpart
        )
    return bool(text)


def _channel_color(channel: str) -> str:
    """Configured text colour for a channel, used by the log and the overlay."""
    default = CHANNEL_COLORS.get(channel, "#ffffff")
    raw = _cfg_str(_color_key(channel), default).strip()
    if _valid_color(raw):
        return raw
    return default


def _contrast_on(color: str) -> str:
    """Pick black or white text so a swatch label stays readable."""
    hexpart = color[1:] if color.startswith("#") else ""
    if len(hexpart) == 3:
        hexpart = "".join(char * 2 for char in hexpart)
    if len(hexpart) < 6:
        return "#000000"
    try:
        red = int(hexpart[0:2], 16)
        green = int(hexpart[2:4], 16)
        blue = int(hexpart[4:6], 16)
    except ValueError:
        return "#000000"
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#000000" if luminance > 150 else "#ffffff"


def _overlay_visible_size() -> tuple:
    """Return the (width, height) of the overlay canvas that is actually visible.

    Modern Overlay renders legacy payload coordinates on a fixed 1280x960 canvas
    (``OVERLAY_BASE_WIDTH``/``OVERLAY_BASE_HEIGHT``). In the default "fill" scale
    mode that canvas is scaled until it covers the screen, so on wider-than-4:3
    displays only the top-left region stays visible (the rest overflows past the
    bottom/sides). Clamping into this region keeps notifications on screen for
    "fill", "fit" and "stretch" alike, since all of those modes show at least the
    top-left 4:3 slice. Falls back to the full canvas when the screen size is
    unavailable.
    """
    base_w = OVERLAY_BASE_WIDTH
    base_h = OVERLAY_BASE_HEIGHT
    width = height = 0
    try:
        root = tk._default_root  # type: ignore[attr-defined]
        if root is not None:
            width = int(root.winfo_screenwidth())
            height = int(root.winfo_screenheight())
    except Exception:
        width = height = 0
    if width <= 0 or height <= 0:
        return base_w, base_h
    screen_ratio = width / float(height)
    base_ratio = base_w / float(base_h)
    if screen_ratio >= base_ratio:
        visible_w = float(base_w)
        visible_h = base_w / screen_ratio
    else:
        visible_w = base_h * screen_ratio
        visible_h = float(base_h)
    visible_w = max(1, min(base_w, round(visible_w)))
    visible_h = max(1, min(base_h, round(visible_h)))
    return visible_w, visible_h


def _overlay_default_pos() -> tuple:
    """Default overlay anchor: left side, 30% down the visible overlay canvas."""
    visible_w, visible_h = _overlay_visible_size()
    x = max(8, round(visible_w * 0.02))
    y = max(8, round(visible_h * 0.30))
    return x, y


def _clamp_overlay_draw_pos(x: int, y: int, count: int, step: int) -> tuple:
    """Clamp the draw anchor so a column of ``count`` lines stays on screen.

    The configured anchor is left untouched; this only nudges the rendered
    column back inside the visible canvas. Y is shifted up by just enough to fit
    the current number of stacked lines, so single messages stay exactly where
    the anchor was placed and the column only moves when it would overflow.
    """
    visible_w, visible_h = _overlay_visible_size()
    max_x = max(0, visible_w - 8)
    # The column's last line ends one line-height below its own top, and that
    # height is `step`, so the full column occupies `count * step`.
    stack_height = max(0, step) * max(0, count)
    max_y = max(0, visible_h - stack_height)
    x = min(max(0, int(x)), max_x)
    y = min(max(0, int(y)), max_y)
    return x, y


def _overlay_pos_from_cfg() -> tuple:
    """Read the configured overlay anchor (X, Y) from config."""
    default_x, default_y = _overlay_default_pos()
    x = _cfg_int(f"{CONFIG_PREFIX}_overlay_x", default_x)
    y = _cfg_int(f"{CONFIG_PREFIX}_overlay_y", default_y)
    return x, y


def _is_frozen() -> bool:
    if _freeze_var is None:
        return False
    try:
        return bool(_freeze_var.get())
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Chat log persistence
# --------------------------------------------------------------------------- #
def _chat_log_dir() -> str:
    """Best-effort location of EDMC's logs folder, with safe fallbacks."""
    fallback = None
    for name in (None, str(appname)):
        try:
            handlers = (
                list(logging.getLogger(name).handlers)
                if name
                else list(logging.getLogger().handlers)
            )
        except Exception:
            handlers = []
        for handler in handlers:
            base = getattr(handler, "baseFilename", None)
            if not base:
                continue
            try:
                directory = os.path.dirname(os.path.abspath(str(base)))
            except Exception:
                continue
            if not os.path.isdir(directory):
                continue
            if os.path.basename(directory).lower() == "logs":
                return directory
            fallback = fallback or directory
    if fallback:
        return fallback
    # <EDMC data dir>/plugins/<this plugin> -> <EDMC data dir>/logs
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    logs = os.path.join(os.path.dirname(os.path.dirname(plugin_dir)), "logs")
    if os.path.isdir(logs):
        return logs
    return plugin_dir


def _chat_log_path() -> str:
    return os.path.join(_chat_log_dir(), CHAT_LOG_FILENAME)


def _sanitise_field(value: Any) -> str:
    """Flatten a value so it always survives a single log line."""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _write_chat_log(item: dict[str, Any]) -> None:
    # time, channel, from, to, direction, message. Direction is "in" or "out"
    # so a reloaded private line still knows who spoke and who it was for.
    line = "\t".join(
        (
            _sanitise_field(item.get("time", "")),
            _sanitise_field(item.get("channel", "")),
            _sanitise_field(item.get("from", "")),
            _sanitise_field(item.get("to", "")),
            "in" if item.get("incoming") else "out",
            _sanitise_field(item.get("message", "")),
        )
    )
    try:
        with open(_chat_log_path(), "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except Exception:
        logger.exception("Failed to append to the Salty chat log")


def _parse_chat_log_line(line: str) -> dict[str, Any] | None:
    """Parse one chat-log row, including the older 4-field rows."""
    parts = line.split("\t")
    if len(parts) >= 6:
        stamp, channel, sender, target, direction = parts[:5]
        message = "\t".join(parts[5:])
        incoming = direction == "in"
    elif len(parts) == 4:
        stamp, channel, sender, message = parts
        target = ""
        incoming = False
    else:
        return None
    if channel not in CHANNELS:
        channel = "private"
    return {
        "time": stamp,
        "channel": channel,
        "from": sender,
        "to": target,
        "message": message,
        "incoming": incoming,
    }


def _read_chat_log() -> list[dict[str, Any]]:
    path = _chat_log_path()
    items: list[dict[str, Any]] = []
    if not os.path.isfile(path):
        return items
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            item = _parse_chat_log_line(line)
            if item is not None:
                items.append(item)
    if len(items) > MAX_MESSAGES:
        items = items[-MAX_MESSAGES:]
    return items


def _snapshot_chat_log() -> None:
    """Read the saved chat log once, before any live message is written."""
    global _history_pending, _history_snapshot_taken
    if _history_snapshot_taken:
        return
    if not _chat_logging_enabled():
        return
    _history_snapshot_taken = True
    try:
        _history_pending = _read_chat_log()
    except Exception:
        logger.exception("Failed to read the Salty chat log")
        _history_pending = []


def _flush_startup_history() -> None:
    """Show the saved chat log once the startup hint has been displayed."""
    global _history_pending, _history_flushed
    if _history_flushed:
        return
    _history_flushed = True
    history = _history_pending
    _history_pending = []
    if not history:
        return
    _messages[:0] = history
    if len(_messages) > MAX_MESSAGES:
        del _messages[: len(_messages) - MAX_MESSAGES]
    try:
        _rerender_views()
    except Exception:
        logger.exception("Failed to display the saved chat log")


def _set_chat_logging(enabled: bool) -> None:
    try:
        config.set(_chat_logging_key(), bool(enabled))
    except Exception:
        logger.exception("Failed to persist the chat logging setting")
    if enabled:
        _snapshot_chat_log()
        if _hint_shown:
            _flush_startup_history()


# --------------------------------------------------------------------------- #
# Toplevel windows
# --------------------------------------------------------------------------- #
def _dialog_master(preferred: tk.Misc | None = None) -> tk.Misc | None:
    """Pick the master for a Salty toplevel window.

    EDMC's ``theme.register`` recursively walks plugin frames and raises
    ``TypeError`` on any ``tk.Toplevel`` it finds, because ``Toplevel`` is a
    subclass of ``BaseWidget`` rather than of ``tk.Widget``. Anything parented
    to the plugin frame would therefore crash EDMC the next time it walks the
    widget tree, so our windows hang off the application's root window instead
    and use the plugin frame only for positioning.
    """
    for candidate in (_main_frame, preferred):
        if candidate is None:
            continue
        try:
            return candidate.winfo_toplevel()
        except Exception:
            continue
    return getattr(tk, "_default_root", None)


# --------------------------------------------------------------------------- #
# Startup hint
# --------------------------------------------------------------------------- #
def _dismiss_startup_hint() -> None:
    """Hide the startup hint immediately, if it is still on screen."""
    fn = _dismiss_startup_hint_fn
    if fn is not None:
        fn()


def _show_startup_hint() -> None:
    """Show a one-time hint inside the chat box, then load the saved chat log.

    The hint is an overlay label tucked into the chat box itself rather than a
    floating window, so it always appears exactly where the click controls it
    describes actually are. A click before the timer ends removes it at once.
    """
    global _hint_started, _dismiss_startup_hint_fn, _startup_hint_up

    if _hint_started:
        return
    _hint_started = True
    _startup_hint_up = True

    def _finish() -> None:
        global _hint_shown, _dismiss_startup_hint_fn, _startup_hint_up
        _dismiss_startup_hint_fn = None
        _hint_shown = True
        _startup_hint_up = False
        logger.debug("Salty startup hint dismissed; loading the saved chat log")
        _flush_startup_history()
        _fit_main_text_height()

    box = _main_text
    if box is None:
        _finish()
        return

    bg, fg = _theme_colors()
    try:
        label = tk.Label(
            box,
            text=STARTUP_HINT_TEXT,
            background=bg,
            foreground=fg,
            font=_ui_font(0),
            padx=8,
            pady=4,
            relief="flat",
            bd=0,
            justify="center",
            wraplength=220,
            cursor="arrow",
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        label.bind("<Button-1>", _on_chat_click)
        label.bind("<Double-Button-1>", _on_chat_double_click)
        label.bind("<Button-3>", _on_chat_menu)
        _attach_hover_tip(label, HOVER_TIP_TEXT)
    except Exception:
        logger.exception("Could not show the Salty startup hint")
        _finish()
        return

    state: dict[str, Any] = {"timer": None, "poll": None, "dismissed": False}

    def _dismiss() -> None:
        if state["dismissed"]:
            return
        state["dismissed"] = True
        for key in ("timer", "poll"):
            handle = state.pop(key, None)
            if handle is not None:
                try:
                    box.after_cancel(handle)
                except Exception:
                    pass
        _dismiss_hover_tips()
        try:
            label.destroy()
        except Exception:
            pass
        _finish()

    _dismiss_startup_hint_fn = _dismiss

    def _arm() -> None:
        # Only start counting down once the box is really on screen: the Salty
        # tab is usually not the one EDMC shows first, and a hint that expired
        # before the box was ever displayed would be wasted.
        state["poll"] = None
        try:
            if not box.winfo_exists():
                return
            if box.winfo_ismapped():
                logger.debug("Salty startup hint shown inside the chat box")
                state["timer"] = box.after(STARTUP_HINT_MS, _dismiss)
                return
            state["poll"] = box.after(200, _arm)
        except Exception:
            pass

    try:
        _arm()
    except Exception:
        _dismiss()


# --------------------------------------------------------------------------- #
# Main widget interaction
# --------------------------------------------------------------------------- #
def _cancel_pending_click() -> None:
    global _pending_click
    if _pending_click is None:
        return
    try:
        if _main_text is not None:
            _main_text.after_cancel(_pending_click)
    except Exception:
        pass
    _pending_click = None


def _open_popout_deferred() -> None:
    global _pending_click
    _pending_click = None
    _open_popout()


def _on_chat_click(event: tk.Event) -> str:
    global _pending_click
    # Returning "break" stops the tip's own button binding, and the pointer
    # never leaves the chat box when the pop-out opens, so close the tip here.
    _dismiss_hover_tips()
    _cancel_pending_click()
    # Tk may deliver <Button-1> and <Double-Button-1> for the same physical
    # press in either order, so ignore the trailing single click too.
    if time.monotonic() < _suppress_until:
        _dismiss_startup_hint()
        return "break"
    # Schedule on the chat box itself. The hint label is destroyed as soon as
    # it is clicked, and a timer parked on that label would be cancelled with it.
    host = _main_text if _main_text is not None else event.widget
    try:
        _pending_click = host.after(CLICK_ACTION_DELAY_MS, _open_popout_deferred)
    except Exception:
        _open_popout()
    _dismiss_startup_hint()
    return "break"


def _on_chat_double_click(event: tk.Event) -> str:
    global _suppress_until
    _dismiss_hover_tips()
    _cancel_pending_click()
    _suppress_until = time.monotonic() + (CLICK_ACTION_DELAY_MS / 1000.0)
    _dismiss_startup_hint()
    _open_settings()
    return "break"


_hover_tip_hiders: list[Any] = []


def _dismiss_hover_tips() -> None:
    """Close every hover tip, including one whose widget never received Leave."""
    for hide in list(_hover_tip_hiders):
        try:
            hide()
        except Exception:
            pass


def _attach_hover_tip(widget: tk.Widget, text: str) -> None:
    """Show a small hover tip. The tip window hangs off the app root, not the
    plugin frame, so EDMC's theme walk never finds a Toplevel in the plugin.

    The tip waits HOVER_TIP_DELAY_MS before it appears and hides itself after
    HOVER_TIP_LINGER_MS even if the pointer never leaves the widget.
    """
    state: dict[str, Any] = {"win": None, "after": None, "linger": None}

    def _cancel(handle: Any) -> None:
        if handle is not None:
            try:
                widget.after_cancel(handle)
            except Exception:
                pass

    def _hide(_event: tk.Event | None = None) -> None:
        _cancel(state.get("after"))
        _cancel(state.get("linger"))
        state["after"] = None
        state["linger"] = None
        win = state.get("win")
        state["win"] = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    _hover_tip_hiders.append(_hide)

    def _reveal(event: tk.Event) -> None:
        state["after"] = None
        try:
            if not widget.winfo_exists():
                return
        except Exception:
            return
        try:
            win = tk.Toplevel(_dialog_master(widget))
        except Exception:
            return
        state["win"] = win
        try:
            win.wm_overrideredirect(True)
            win.wm_attributes("-topmost", True)
        except Exception:
            pass
        bg, fg = _theme_colors()
        tk.Label(
            win,
            text=text,
            background=bg,
            foreground=fg,
            font=_ui_font(0),
            padx=6,
            pady=3,
            relief="flat",
            bd=0,
            justify="left",
        ).pack()
        try:
            win.geometry(f"+{event.x_root + 14}+{event.y_root + 18}")
        except Exception:
            pass
        try:
            state["linger"] = widget.after(HOVER_TIP_LINGER_MS, _hide)
        except Exception:
            pass

    def _show(event: tk.Event) -> None:
        _hide()
        try:
            state["after"] = widget.after(HOVER_TIP_DELAY_MS, lambda: _reveal(event))
        except Exception:
            _reveal(event)

    widget.bind("<Enter>", _show, add="+")
    widget.bind("<Leave>", _hide, add="+")
    widget.bind("<Button>", _hide, add="+")


def _build_chat_menu() -> tk.Menu:
    """The right-click menu shown over the main chat widget."""
    bg, fg = _theme_colors()
    menu = tk.Menu(
        tearoff=0,
        background=bg,
        foreground=fg,
        activebackground=fg,
        activeforeground=bg,
        relief="flat",
        bd=1,
        font=_ui_font(1),
    )
    menu.add_command(label="Pop out window", command=_open_popout)
    menu.add_command(label=_hide_menu_label(), command=_cycle_hide_manual)
    menu.add_command(label="Settings", command=_open_settings)
    return menu


def _on_chat_menu(event: tk.Event) -> str:
    _dismiss_hover_tips()
    menu = _build_chat_menu()
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        try:
            menu.grab_release()
        except Exception:
            pass
    return "break"


# --------------------------------------------------------------------------- #
# Channel mapping
# --------------------------------------------------------------------------- #
def _normalise_channel(raw: str | None) -> str:
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
    if token in (
        "squadleaders",
        "squadron leaders",
        "squadron_leaders",
        "squadronleaders",
    ):
        return "squadleaders"
    if token == "npc":
        return "npc"
    # player / friend / voicechat / direct and anything unknown -> private
    return "private"


def _private_peer(raw: str | None) -> str:
    """Commander name a private message was sent to, or empty when unknown."""
    name = str(raw or "").strip()
    if not name or name.lower() in _NOT_A_COMMANDER:
        return ""
    if _normalise_channel(name) != "private":
        return ""
    return name


def _event_time(entry: dict[str, Any]) -> str:
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
        logger.info(
            "Modern Overlay has no send_overlay_message; notifications unavailable"
        )
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
        send(
            {
                "event": "LegacyOverlay",
                "type": "message",
                "id": overlay_id,
                "text": "",
                "ttl": 0,
                "x": 0,
                "y": 0,
            }
        )
    except Exception:
        pass


def _wrap_overlay_text(text: str, width: int = OVERLAY_WRAP_WIDTH) -> str:
    """Wrap overlay text on word boundaries at about 30-40 characters."""
    cleaned = " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split())
    if not cleaned:
        return ""
    return textwrap.fill(
        cleaned,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _overlay_line_count(text: str) -> int:
    if not text:
        return 1
    return max(1, text.count("\n") + 1)


def _overlay_body(channel: str, sender: str, message: str) -> str:
    sender = sender or ""
    message = message or ""
    if channel == "private" and sender:
        raw = f"From: {sender}: {message}"
    else:
        raw = f"{sender}: {message}"
    return _wrap_overlay_text(raw)


def _entry_line_step(entry: dict[str, Any]) -> int:
    size = entry.get("size") or DEFAULT_OVERLAY_SIZE
    if size not in OVERLAY_SIZES:
        size = DEFAULT_OVERLAY_SIZE
    return OVERLAY_LINE_STEP.get(size, OVERLAY_LINE_STEP[DEFAULT_OVERLAY_SIZE])


def _emit_overlay_stack(send) -> None:
    """Redraw every active notification, stacking wrapped lines without overlap."""
    if not _overlay_active:
        return
    default_x, default_y = _overlay_default_pos()
    base_x = _cfg_int(f"{CONFIG_PREFIX}_overlay_x", default_x)
    base_y = _cfg_int(f"{CONFIG_PREFIX}_overlay_y", default_y)
    now = time.monotonic()
    stack_height = sum(
        max(1, int(entry.get("lines") or 1)) * _entry_line_step(entry)
        for entry in _overlay_active
    )
    # count=1 and step=stack_height asks the clamp to keep the whole column
    # on screen, including extra lines created by word wrap.
    draw_x, draw_y = _clamp_overlay_draw_pos(base_x, base_y, 1, stack_height)
    cursor_y = draw_y
    ys: list[int] = []
    for entry in _overlay_active:
        lines = max(1, int(entry.get("lines") or 1))
        remaining = max(1, round(entry["expire"] - now))
        payload = {
            "event": "LegacyOverlay",
            "type": "message",
            "id": entry["id"],
            "plugin": PLUGIN_DISPLAY_NAME,
            "text": entry["text"],
            "color": entry["color"],
            "size": entry["size"],
            "x": draw_x,
            "y": cursor_y,
            "ttl": remaining,
        }
        ys.append(cursor_y)
        cursor_y += lines * _entry_line_step(entry)
        try:
            send(payload)
        except Exception:
            logger.exception("Failed to send overlay notification")
    logger.debug(
        "Overlay notifications updated: %d active, ys=%s (newest: %s)",
        len(_overlay_active),
        ys,
        _overlay_active[0]["text"],
    )


def _refresh_overlay_entries() -> None:
    """Apply the current channel colours to live toasts."""
    if not _overlay_active:
        return
    for entry in _overlay_active:
        entry["color"] = _channel_color(entry.get("channel") or "")
    send = _overlay_send
    if send is None:
        return
    now = time.monotonic()
    _overlay_active[:] = [entry for entry in _overlay_active if entry["expire"] > now]
    if _overlay_active:
        _emit_overlay_stack(send)


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
    ttl = max(1, _cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL))

    global _overlay_seq
    _overlay_seq += 1
    now = time.monotonic()

    # Drop notifications that have already expired.
    _overlay_active[:] = [e for e in _overlay_active if e["expire"] > now]

    # Enforce the maximum number of simultaneous notifications (evict oldest).
    while len(_overlay_active) >= OVERLAY_MAX_STACK:
        _toast_clear(send, _overlay_active.pop()["id"])

    body = _overlay_body(channel, sender, message)
    # Newest notification goes on top; older ones are pushed down.
    _overlay_active.insert(
        0,
        {
            "id": f"{NOTIFY_ID_PREFIX}{channel}-{_overlay_seq}",
            "channel": channel,
            "sender": sender,
            "message": message or "",
            "text": body,
            "lines": _overlay_line_count(body),
            "color": _channel_color(channel),
            "size": size,
            "expire": now + ttl,
        },
    )
    _emit_overlay_stack(send)


# --------------------------------------------------------------------------- #
# Message store / rendering
# --------------------------------------------------------------------------- #
def _format_prefix(item: dict[str, Any]) -> str:
    """Build the leader shown before the message text.

    Private messages keep the ``[Private]`` origin tag and use a direction:
    ``[Private] Name > Me:`` incoming, ``[Private] Me > Name:`` outgoing.
    Every other channel is unchanged. The local commander is stored as ``Me``.
    """
    label = CHANNEL_LABELS.get(item["channel"], item["channel"])
    sender = str(item.get("from") or "")
    channel = item.get("channel")
    incoming = bool(item.get("incoming"))
    bits: list[str] = []
    if _timestamps_shown():
        bits.append(f"[{item['time']}]")
    if _origins_shown():
        bits.append(f"[{label}]")
    if channel == "private" and incoming and sender:
        bits.append(f"{sender} > Me:")
        return " ".join(bits) + " "
    if channel == "private" and not incoming:
        target = str(item.get("to") or "").strip()
        if target:
            bits.append(f"Me > {target}:")
            return " ".join(bits) + " "
    prefix = (" ".join(bits) + " ") if bits else ""
    return f"{prefix}{sender}: "


def _trim(text: tk.Text) -> None:
    try:
        lines = int(text.index("end-1c").split(".")[0])
        if lines > MAX_MESSAGES:
            text.delete("1.0", f"{lines - MAX_MESSAGES}.0")
    except Exception:
        pass


def _fit_main_text_height() -> None:
    """Shrink the chat box to its content, up to MAIN_TEXT_MAX_LINES.

    An almost empty log would otherwise sit inside a fixed tall box with a
    blank lower gap. The box grows line by line as messages arrive and scrolls
    once it reaches the cap, so no line is clipped and the scrollbar stays.
    """
    text = _main_text
    if text is None or _startup_hint_up:
        return
    try:
        if not text.winfo_exists() or not text.winfo_ismapped():
            return
        if text.winfo_width() <= 1:
            return
        content = int(text.count("1.0", "end", "displaylines")[0]) - 1
    except Exception:
        return
    if content < 0:
        content = 0
    want = max(1, min(content, MAIN_TEXT_MAX_LINES))
    try:
        if int(text.cget("height")) != want:
            text.configure(height=want)
    except Exception:
        pass


def _filtered_messages() -> list[dict[str, Any]]:
    return [item for item in _messages if _channel_shown(item["channel"])]


def _items_for_view(text: tk.Text) -> list[dict[str, Any]]:
    """Messages this widget should show.

    The pop-out keeps the full filtered log. The main EDMC widget keeps only
    the newest MAIN_HISTORY_LIMIT entries. Rendering the main widget also
    records whether older lines exist, so scrolling does not scan the log.
    """
    global _main_history_overflow
    items = _filtered_messages()
    if text is _main_text:
        _main_history_overflow = len(items) > MAIN_HISTORY_LIMIT
        if _main_history_overflow:
            return items[-MAIN_HISTORY_LIMIT:]
    return items


def _insert_item(text: tk.Text, item: dict[str, Any]) -> None:
    text.insert("end", _format_prefix(item), (f"ch_{item['channel']}",))
    text.insert("end", f"{item['message']}\n")


def _append_item(text: tk.Text, item: dict[str, Any]) -> None:
    text.configure(state="normal")
    try:
        _insert_item(text, item)
        _trim(text)
        if not _is_frozen():
            text.see("end")
    finally:
        text.configure(state="disabled")


def _render_all(text: tk.Text) -> None:
    """Replace a view's contents in one edit, then scroll once."""
    items = _items_for_view(text)
    text.configure(state="normal")
    try:
        text.delete("1.0", "end")
        for item in items:
            _insert_item(text, item)
        _trim(text)
        if items and not _is_frozen():
            text.see("end")
    finally:
        text.configure(state="disabled")
    if text is _main_text:
        _update_history_hint()
        _fit_main_text_height()


def _add_message(
    channel: str,
    sender: str,
    message: str,
    incoming: bool,
    entry: dict[str, Any],
    target: str = "",
) -> None:
    # The local commander is always "Me" in the log. Private rows also record
    # who the message was sent to, so the file shows both ends of the exchange.
    if incoming:
        origin = sender or "Unknown"
        destination = "Me" if channel == "private" else ""
    else:
        origin = "Me"
        destination = target if channel == "private" else ""
    item = {
        "time": _event_time(entry),
        "channel": channel,
        "from": origin,
        "to": destination,
        "message": message or "",
        "incoming": incoming,
    }
    _messages.append(item)
    if len(_messages) > MAX_MESSAGES:
        del _messages[: len(_messages) - MAX_MESSAGES]

    if _chat_logging_enabled():
        _write_chat_log(item)

    if _channel_shown(channel):
        for text in list(_views):
            try:
                # Re-render the compact widget so it stays at the last 30
                # messages, including when a message spans more than one line.
                if text is _main_text:
                    _render_all(text)
                else:
                    _append_item(text, item)
            except Exception:
                logger.exception("Failed to append message to a chat view")

    if incoming:
        _notify(channel, sender, item["message"])


def _rerender_views() -> None:
    for text in _views:
        try:
            _render_all(text)
        except Exception:
            logger.exception("Failed to re-render a chat view")


def _install_history_hint(box: tk.Text) -> None:
    """Create the top-of-log note. It stays hidden until the view is at the top."""
    global _history_hint
    bg, fg = _theme_colors()
    label = tk.Label(
        box,
        text=HISTORY_HINT_TEXT,
        background=bg,
        foreground=fg,
        font=_ui_font(0),
        padx=6,
        pady=2,
        relief="flat",
        bd=0,
        justify="center",
        wraplength=220,
        cursor="arrow",
    )
    label.bind("<Button-1>", _on_chat_click)
    label.bind("<Double-Button-1>", _on_chat_double_click)
    label.bind("<Button-3>", _on_chat_menu)
    _attach_hover_tip(label, HOVER_TIP_TEXT)
    _history_hint = label


def _update_history_hint(first: float | None = None) -> None:
    """Show the expand note only at the top of a main log that has older lines.

    The pop-out placeholder is not in ``_views``, so the note stays hidden
    while that window owns the full history.
    """
    label = _history_hint
    text = _main_text
    if label is None or text is None:
        return
    show = False
    try:
        if text in _views and _main_history_overflow:
            if first is None:
                first = float(text.yview()[0])
            show = first <= 0.002
    except Exception:
        show = False
    try:
        placed = label.winfo_manager() == "place"
        if show:
            if not placed:
                bg, fg = _theme_colors()
                label.configure(background=bg, foreground=fg)
                label.place(relx=0.5, rely=0.0, anchor="n")
                label.lift()
        elif placed:
            label.place_forget()
    except Exception:
        pass


def _themed_confirm(parent: tk.Misc, message: str) -> bool:
    """Show a modal Yes/No dialog styled with EDMC's active theme colours."""
    try:
        dlg = tk.Toplevel(_dialog_master(parent))
    except Exception:
        return True

    bg, fg = _theme_colors()
    dlg.title(PLUGIN_DISPLAY_NAME)
    dlg.configure(background=bg)
    dlg.resizable(False, False)

    result = {"value": False}

    label = tk.Label(
        dlg,
        text=message,
        background=bg,
        foreground=fg,
        font=_ui_font(0),
        padx=24,
        pady=18,
        anchor="w",
        justify="left",
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
            btns,
            text=text,
            width=10,
            command=lambda: _choose(value),
            background=bg,
            foreground=fg,
            activebackground=bg,
            activeforeground=fg,
            highlightthickness=0,
            highlightbackground=bg,
            font=_ui_font(0),
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
            py = (
                parent.winfo_rooty() + (parent.winfo_height() - dlg.winfo_height()) // 2
            )
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


def _confirm_parent() -> tk.Misc | None:
    try:
        if _settings_win is not None and _settings_win.winfo_exists():
            return _settings_win
        if _popout is not None and _popout.winfo_exists():
            return _popout
        if _main_frame is not None and _main_frame.winfo_exists():
            return _main_frame.winfo_toplevel()
    except Exception:
        return None
    return None


def _confirm_clear() -> bool:
    """Ask the user to confirm clearing the chat window."""
    return _themed_confirm(_confirm_parent(), "Clear the chat window?")


def _blank_views() -> None:
    """Empty every live chat view and drop the cached history-note flag."""
    global _main_history_overflow
    _main_history_overflow = False
    for text in _views:
        try:
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.configure(state="disabled")
        except Exception:
            pass
    _update_history_hint()


def _clear_messages() -> None:
    if not _confirm_clear():
        return
    _messages.clear()
    _blank_views()


def _confirm_clear_log() -> bool:
    return _themed_confirm(
        _confirm_parent(),
        "Clear the saved chat log?\nThis deletes SaltyChat.log and the messages currently shown.",
    )


def _clear_chat_log() -> None:
    """Delete the on-disk chat log after confirmation, and clear the window."""
    if not _confirm_clear_log():
        return
    path = _chat_log_path()
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        logger.exception("Failed to delete the Salty chat log")
        return
    _history_pending.clear()
    _messages.clear()
    _blank_views()


def _open_log_folder() -> None:
    """Open the folder that holds SaltyChat.log so it can be copied as a backup."""
    path = _chat_log_dir()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        logger.exception("Failed to prepare the Salty log folder")
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        logger.exception("Failed to open the Salty log folder")


# --------------------------------------------------------------------------- #
# UI construction
# --------------------------------------------------------------------------- #
def _tag_text(text: tk.Text) -> None:
    for channel in CHANNELS:
        text.tag_configure(f"ch_{channel}", foreground=_channel_color(channel))


def _apply_channel_colors() -> None:
    """Push the configured channel colours into every chat view and live toast."""
    seen: list[tk.Text] = []
    for text in list(_views):
        seen.append(text)
        try:
            _tag_text(text)
        except Exception:
            pass
    if _main_text is not None and _main_text not in seen:
        try:
            _tag_text(_main_text)
        except Exception:
            pass
    _refresh_overlay_entries()


def _set_channel_color(channel: str, color: str) -> None:
    if channel not in COLOR_CHANNELS or not _valid_color(color):
        return
    try:
        config.set(_color_key(channel), color)
    except Exception:
        logger.exception("Failed to persist colour for %s", channel)
        return
    _apply_channel_colors()


def _walk(widget: tk.Widget):
    """Yield a widget and all of its descendants."""
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield from _walk(child)


def scrollbar_thumb_box(
    first: float, last: float, height: int, min_thumb: int
) -> tuple[int, int] | None:
    """Return ``(top, bottom)`` for the thumb, or None when the content fits.

    The old placement grew the thumb only downward from ``first * height``.
    On the short main-window track, a log pinned to the end left a couple of
    pixels and the thumb looked like an underscore. The span is chosen first,
    then slid along the track, so the bottom of the log still shows a full
    indicator with a little trough left visible.
    """
    if height <= 1:
        return None
    visible = last - first
    if visible >= 0.999:
        return None
    span = min(height, max(int(min_thumb), int(visible * height)))
    if height > 8:
        span = min(span, height - 4)
    span = max(1, span)
    travel = max(0, height - span)
    if last >= 0.999:
        top = travel
    elif first <= 0.001:
        top = 0
    else:
        top = int((first / max(0.001, 1.0 - visible)) * travel)
        top = max(0, min(travel, top))
    return top, top + span


class ThemedScrollbar(tk.Canvas):
    """
    A Canvas-drawn scrollbar that can follow EDMC's theme colours.

    A classic ``tk.Scrollbar`` keeps its native (light) thumb on Windows and
    cannot be recoloured reliably, so we draw the trough and thumb ourselves on
    a ``tk.Canvas`` (which is fully colourable).
    """

    def __init__(
        self,
        master,
        command=None,
        background="grey4",
        foreground="#ff8000",
        width=14,
        min_thumb=8,
        **kw,
    ):
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
        self._min_thumb = max(4, int(min_thumb))
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
        box = scrollbar_thumb_box(self._first, self._last, h, self._min_thumb)
        if box is None:
            self._top = 0
            self._bottom = h
            return
        top, bottom = box
        self._top = top
        self._bottom = bottom
        color = self._thumb_active if self._drag else self._thumb
        self.create_rectangle(
            2, top + 1, w - 2, bottom - 1, fill=color, outline="", tags="thumb"
        )

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
        span = max(1, self._bottom - self._top)
        travel = max(1, height - span)
        frac = max(0.0, min(1.0, top / travel))
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
            hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark)
        )
        bg, fg = _theme_colors()
        if bg:
            value = ctypes.c_uint(_colorref(window, bg))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(value), ctypes.sizeof(value)
            )
        if fg:
            value = ctypes.c_uint(_colorref(window, fg))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(value), ctypes.sizeof(value)
            )
    except Exception:
        pass


def _set_always_on_top(window: tk.Widget, enabled: bool) -> None:
    """Pin a Salty window above other windows so the game cannot cover it."""
    try:
        window.wm_attributes("-topmost", bool(enabled))
    except Exception:
        pass


def _apply_stay_on_top(window: tk.Toplevel | None) -> None:
    """Apply the saved stay-on-top preference to a Salty toplevel."""
    if window is None:
        return
    try:
        if not window.winfo_exists():
            return
    except Exception:
        return
    _set_always_on_top(window, _stay_on_top_enabled())


def _toggle_stay_on_top() -> None:
    try:
        value = bool(_topmost_var.get()) if _topmost_var is not None else False
    except Exception:
        value = False
    try:
        config.set(_stay_on_top_key(), value)
    except Exception:
        logger.exception("Failed to persist the stay-on-top setting")
    _apply_stay_on_top(_popout)
    _apply_stay_on_top(_settings_win)


# --------------------------------------------------------------------------- #
# Hide from mouse (Windows click-through)
# --------------------------------------------------------------------------- #
_HIDE_MODES = ("auto", "hidden", "shown")
_HIDE_LABELS = {"auto": "Detect", "hidden": "Hidden", "shown": "Off"}
_CT_GWL_EXSTYLE = -20
_CT_WS_EX_TRANSPARENT = 0x00000020
_CT_WS_EX_LAYERED = 0x00080000
_CT_LWA_ALPHA = 1
_CT_GA_ROOT = 2
# Tk winfo_id -> click-through active, remembered so <Map> can re-apply it.
# Keyed by the Tk handle because GetAncestor can resolve differently before
# and after the window is mapped; every write resolves the root fresh.
_ct_state: dict[int, bool] = {}


def _ct_root(hwnd: int) -> int:
    import ctypes

    user32 = ctypes.windll.user32
    root = user32.GetAncestor(int(hwnd), _CT_GA_ROOT)
    return int(root or 0)


def _ct_write(hwnd: int, enabled: bool) -> bool:
    """Apply click-through to the input window and its root (they can differ).

    Click-through needs WS_EX_TRANSPARENT plus a valid layered setup on the
    root: WS_EX_LAYERED with initialized attributes (alpha 255) when the
    window is not already layered by Tk's -alpha, never a bare
    WS_EX_LAYERED, which would render an empty white box. Tk-managed
    layering (non-zero alpha) is left untouched so configured opacity is
    preserved; stray un-owned layering is stripped again on disable.
    """
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
    except Exception:
        logger.exception("ctypes unavailable for click-through")
        return False

    def attrs_alpha(target: int):
        col = wintypes.COLORREF(0)
        pct = wintypes.BYTE(0)
        flags = wintypes.DWORD(0)
        try:
            user32.GetLayeredWindowAttributes.argtypes = [
                wintypes.HWND, ctypes.POINTER(wintypes.COLORREF),
                ctypes.POINTER(wintypes.BYTE), ctypes.POINTER(wintypes.DWORD)]
            user32.GetLayeredWindowAttributes.restype = wintypes.BOOL
            ok = user32.GetLayeredWindowAttributes(
                int(target), ctypes.byref(col), ctypes.byref(pct), ctypes.byref(flags))
            return int(pct.value) if ok else None
        except Exception:
            return None

    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
    user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    try:
        root = _ct_root(hwnd)
    except Exception:
        root = 0
    targets: list[tuple[int, bool]] = [(root or int(hwnd), True)]
    if int(hwnd) not in [t for t, _ in targets]:
        targets.append((int(hwnd), False))
    ok = False
    for target, is_root in targets:
        try:
            style = user32.GetWindowLongW(target, _CT_GWL_EXSTYLE) & 0xFFFFFFFF
            alpha = attrs_alpha(target)
            if enabled:
                style |= _CT_WS_EX_TRANSPARENT
                if is_root:
                    # A layered root with initialized attrs renders normally;
                    # a bare WS_EX_LAYERED would show a white box.
                    style |= _CT_WS_EX_LAYERED
                elif not alpha:
                    style &= ~_CT_WS_EX_LAYERED
                user32.SetWindowLongW(target, _CT_GWL_EXSTYLE, style)
                if is_root and not alpha:
                    user32.SetLayeredWindowAttributes(
                        target, 0, 255, _CT_LWA_ALPHA)
            else:
                style &= ~_CT_WS_EX_TRANSPARENT
                if not alpha:
                    style &= ~_CT_WS_EX_LAYERED
                user32.SetWindowLongW(target, _CT_GWL_EXSTYLE, style)
            ok = True
        except Exception:
            logger.exception(
                "Failed to set click-through=%s for hwnd %s", enabled, target
            )
    return ok


def _ct_set(hwnd: int, enabled: bool) -> bool:
    """Enable or disable click-through for a Tk window (Windows only)."""
    if sys.platform != "win32" or not hwnd:
        return False
    _ct_state[int(hwnd)] = bool(enabled)
    ok = _ct_write(hwnd, enabled)
    logger.info(
        "Click-through %s for hwnd %s (root resolve %s)",
        "enabled" if enabled else "disabled",
        hwnd,
        "ok" if ok else "deferred",
    )
    return ok


def _ct_reapply(hwnd) -> None:
    """Re-apply the remembered click-through state (bind to <Map>).

    Windows can reset the extended style after redraws or reparents.
    """
    if sys.platform != "win32" or not hwnd:
        return
    enabled = _ct_state.get(int(hwnd))
    if enabled is None:
        return
    _ct_write(hwnd, enabled)


def _ct_forget(hwnd) -> None:
    """Drop remembered state for a window that is being destroyed."""
    if sys.platform != "win32" or not hwnd:
        return
    _ct_state.pop(int(hwnd), None)


def _set_on_foot(value: bool) -> None:
    """Called from journal_entry whenever EDMC's state changes."""
    global _hide_on_foot, _hide_on_foot_seeded
    value = bool(value)
    _hide_on_foot_seeded = True
    if value == _hide_on_foot:
        return
    _hide_on_foot = value
    _refresh_clickthrough()


def _current_on_foot() -> bool:
    # Seed once from EDMC's live monitor state so the correct value is known
    # even before the first journal line after startup.
    global _hide_on_foot, _hide_on_foot_seeded
    if not _hide_on_foot_seeded:
        _hide_on_foot_seeded = True
        try:
            from monitor import monitor

            _hide_on_foot = bool(monitor.state.get("OnFoot"))
        except Exception:
            pass
    return _hide_on_foot


def _hide_active() -> bool:
    if _hide_manual == "hidden":
        return True
    if _hide_manual == "shown":
        return False
    if not _cfg_bool(_hide_on_foot_key(), False):
        return False
    return _current_on_foot()


def _refresh_clickthrough() -> None:
    """Apply the effective click-through state to the pop-out window."""
    active = _hide_active()
    if _popout is None:
        return
    try:
        if not _popout.winfo_exists():
            return
        _ct_set(_popout.winfo_id(), active)
        _popout.title(
            PLUGIN_DISPLAY_NAME + (" (hidden from mouse)" if active else "")
        )
    except Exception:
        logger.exception("Failed to refresh click-through state")


def _apply_popout_opacity(val: int) -> None:
    """Set the pop-out opacity and re-assert click-through.

    Tk's -alpha write can rebuild the extended style and drop the
    click-through bits set with SetWindowLong (observed at alpha 1.0),
    so refresh after every opacity change.
    """
    try:
        _popout.wm_attributes("-alpha", val / 100.0)
        config.set(_popout_opacity_key(), val)
    except Exception:
        pass
    _refresh_clickthrough()


def _hide_menu_label() -> str:
    return "Hide from mouse: %s" % _HIDE_LABELS.get(_hide_manual, "Detect")


def _cycle_hide_manual() -> None:
    """Right-click menu control: auto -> hidden -> shown -> auto."""
    global _hide_manual
    try:
        idx = _HIDE_MODES.index(_hide_manual)
    except ValueError:
        idx = 0
    _hide_manual = _HIDE_MODES[(idx + 1) % len(_HIDE_MODES)]
    _refresh_clickthrough()


def _reset_hide_to_auto() -> None:
    """Settings checkbox: hand control back to the auto rule."""
    global _hide_manual
    _hide_manual = "auto"
    _refresh_clickthrough()


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
                if getattr(widget, "_salty_color_swatch", False):
                    continue
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
                widget.configure(
                    background=bg,
                    foreground=fg,
                    insertbackground=fg,
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    highlightbackground=bg,
                    highlightcolor=bg,
                    cursor="arrow",
                )
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

    for text in _views:
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


def _set_popout_active(active: bool) -> None:
    """Swap the main widget between the live log and a one-line placeholder.

    While the pop-out window is open it owns the full chat log, so the compact
    main-window widget is reduced to a single line saying so.
    """
    text = _main_text
    if text is None:
        return
    try:
        if not text.winfo_exists():
            return
    except Exception:
        return
    try:
        if active:
            _unregister_view(text)
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("end", POPOUT_ACTIVE_TEXT)
            text.configure(state="disabled")
            text.yview_moveto(0)
        else:
            if text not in _views:
                _views.append(text)
            _render_all(text)
        _update_history_hint()
    except Exception:
        logger.exception("Failed to update the main chat widget")


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


def _make_toggle_checks(
    parent: tk.Widget,
    include_timestamp: bool,
    include_origin: bool,
    font_delta: int,
) -> list[tk.Checkbutton]:
    """Create the channel (and optional timestamp/origin) checkboxes."""
    _ensure_filter_vars()
    checks: list[tk.Checkbutton] = []
    for channel in CHANNELS:
        checks.append(
            tk.Checkbutton(
                parent,
                text=CHANNEL_LABELS[channel],
                variable=_filter_vars[channel],
                command=_on_filter_change,
                font=_ui_font(font_delta),
                anchor="w",
            )
        )
    if include_timestamp:
        checks.append(
            tk.Checkbutton(
                parent,
                text="Time",
                variable=_timestamp_var,
                command=_on_timestamps_change,
                font=_ui_font(font_delta),
                anchor="w",
            )
        )
    if include_origin:
        checks.append(
            tk.Checkbutton(
                parent,
                text="Origin",
                variable=_origin_var,
                command=_on_origins_change,
                font=_ui_font(font_delta),
                anchor="w",
            )
        )
    return checks


def _build_toggle_grid(
    parent: tk.Widget,
    *,
    include_timestamp: bool = False,
    include_origin: bool = False,
    columns: int = 3,
    font_delta: int = 0,
    padx: int = 6,
    pady: int = 2,
) -> list[tk.Checkbutton]:
    """Lay the checkboxes out in a fixed grid (deterministic size, no reflow)."""
    checks = _make_toggle_checks(
        parent,
        include_timestamp,
        include_origin,
        font_delta,
    )
    for col in range(columns):
        parent.grid_columnconfigure(col, weight=1)
    for index, check in enumerate(checks):
        check.grid(
            row=index // columns,
            column=index % columns,
            sticky="ew",
            padx=padx,
            pady=pady,
        )
    return checks


def _apply_popout_boxes() -> None:
    """Show or hide the pop-out copy of the Show Messages checkboxes."""
    toggles = _popout_toggles
    chat = _popout_chat
    if toggles is None:
        return
    try:
        if not toggles.winfo_exists():
            return
    except Exception:
        return
    try:
        hidden = _boxes_hidden()
        if hidden:
            if toggles.winfo_ismapped():
                toggles.pack_forget()
            return
        if toggles.winfo_ismapped():
            return
        # Pack order is call order. Forget the chat first so the checkbox row
        # is claimed above it, then give the chat the remaining space.
        if chat is not None and chat.winfo_exists() and chat.winfo_ismapped():
            chat.pack_forget()
        toggles.pack(side="bottom", fill="x", padx=4, pady=(0, 2))
        if chat is not None and chat.winfo_exists():
            chat.pack(fill="both", expand=True, padx=4, pady=4)
    except Exception:
        logger.exception("Failed to update Salty pop-out message boxes")


def _set_boxes_hidden(hidden: bool) -> None:
    try:
        config.set(_hide_boxes_key(), bool(hidden))
    except Exception:
        logger.exception("Failed to persist Hide Boxes setting")
    _apply_popout_boxes()


def _save_overlay_settings(overlay_var, x_var, y_var, ttl_var, size_var) -> None:
    try:
        config.set(f"{CONFIG_PREFIX}_overlay", bool(overlay_var.get()))
        config.set(
            f"{CONFIG_PREFIX}_overlay_x", _to_int(x_var.get(), DEFAULT_OVERLAY_X)
        )
        config.set(
            f"{CONFIG_PREFIX}_overlay_y", _to_int(y_var.get(), DEFAULT_OVERLAY_Y)
        )
        config.set(
            f"{CONFIG_PREFIX}_overlay_ttl", _to_int(ttl_var.get(), DEFAULT_OVERLAY_TTL)
        )
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
                _apply_stay_on_top(_settings_win)
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
        dlg = tk.Toplevel(_dialog_master(parent))
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

    tk.Label(
        body, text="Show messages in:", background=bg, foreground=fg, font=_ui_font(0)
    ).pack(anchor="w")
    strip = tk.Frame(body, background=bg)
    strip.pack(fill="x", pady=(2, 8))
    _build_toggle_grid(
        strip,
        include_timestamp=True,
        include_origin=True,
        font_delta=0,
    )

    def _toggle_hide_boxes() -> None:
        hidden = not _boxes_hidden()
        _set_boxes_hidden(hidden)
        hide_boxes_btn.configure(text="Show Boxes" if hidden else "Hide Boxes")

    hide_boxes_btn = tk.Button(
        body,
        text="Show Boxes" if _boxes_hidden() else "Hide Boxes",
        command=_toggle_hide_boxes,
        font=_ui_font(0),
    )
    hide_boxes_btn.pack(anchor="w", pady=(0, 8))

    tk.Label(
        body,
        text="Channel colors (chat log and Modern Overlay):",
        background=bg,
        foreground=fg,
        font=_ui_font(0),
    ).pack(anchor="w")
    color_row = tk.Frame(body, background=bg)
    color_row.pack(fill="x", pady=(2, 8))
    color_buttons: dict[str, tk.Button] = {}

    def _paint_swatch(channel: str, button: tk.Button) -> None:
        color = _channel_color(channel)
        ink = _contrast_on(color)
        button.configure(
            text=CHANNEL_LABELS[channel],
            background=color,
            foreground=ink,
            activebackground=color,
            activeforeground=ink,
        )

    def _pick_color(channel: str) -> None:
        button = color_buttons.get(channel)
        if button is None:
            return
        try:
            chosen = colorchooser.askcolor(
                color=_channel_color(channel),
                title=f"{CHANNEL_LABELS[channel]} color",
                parent=dlg,
            )
        except Exception:
            logger.exception("Could not open the colour picker")
            return
        hex_color = chosen[1] if chosen else None
        if not hex_color:
            return
        _set_channel_color(channel, str(hex_color))
        _paint_swatch(channel, button)

    for index, channel in enumerate(COLOR_CHANNELS):
        button = tk.Button(
            color_row,
            command=lambda channel=channel: _pick_color(channel),
            font=_ui_font(0),
            width=10,
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        button._salty_color_swatch = True  # type: ignore[attr-defined]
        _paint_swatch(channel, button)
        button.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=2)
        color_buttons[channel] = button
    for column in range(3):
        color_row.grid_columnconfigure(column, weight=1)

    log_actions = tk.Frame(body, background=bg)
    log_actions.pack(anchor="w", fill="x", pady=(0, 8))
    tk.Button(
        log_actions,
        text="Clear Chat logs",
        command=_clear_chat_log,
        font=_ui_font(0),
    ).pack(side="left")
    tk.Button(
        log_actions,
        text="Open Log Folder",
        command=_open_log_folder,
        font=_ui_font(0),
    ).pack(side="left", padx=(8, 0))

    overlay_var = tk.BooleanVar(
        value=_cfg_bool(f"{CONFIG_PREFIX}_overlay", DEFAULT_OVERLAY_ENABLED)
    )
    cfg_x, cfg_y = _overlay_pos_from_cfg()
    x_var = tk.StringVar(value=str(cfg_x))
    y_var = tk.StringVar(value=str(cfg_y))
    ttl_var = tk.StringVar(
        value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL))
    )
    size_var = tk.StringVar(
        value=_cfg_str(f"{CONFIG_PREFIX}_overlay_size", DEFAULT_OVERLAY_SIZE)
    )
    if size_var.get() not in OVERLAY_SIZES:
        size_var.set(DEFAULT_OVERLAY_SIZE)

    tk.Checkbutton(
        body,
        text="On-screen notifications (requires Modern Overlay)",
        variable=overlay_var,
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        selectcolor=bg,
        highlightthickness=0,
        bd=0,
        font=_ui_font(0),
        anchor="w",
    ).pack(anchor="w", pady=(0, 8))

    chat_var = tk.BooleanVar(value=_chat_logging_enabled())
    tk.Checkbutton(
        body,
        text="Chat logging (keep the chat history in a log file)",
        variable=chat_var,
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        selectcolor=bg,
        highlightthickness=0,
        bd=0,
        font=_ui_font(0),
        anchor="w",
    ).pack(anchor="w", pady=(0, 8))

    _ensure_filter_vars()
    _topmost_var.set(_cfg_bool(_stay_on_top_key(), DEFAULT_STAY_ON_TOP))
    tk.Checkbutton(
        body,
        text="Stay on top of the game",
        variable=_topmost_var,
        command=_toggle_stay_on_top,
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        selectcolor=bg,
        highlightthickness=0,
        bd=0,
        font=_ui_font(0),
        anchor="w",
    ).pack(anchor="w", pady=(0, 8))

    hide_var = tk.BooleanVar(value=_cfg_bool(_hide_on_foot_key(), False))

    def _toggle_hide_on_foot() -> None:
        try:
            config.set(_hide_on_foot_key(), bool(hide_var.get()))
        except Exception:
            logger.exception("Failed to persist the hide-from-mouse setting")
        _reset_hide_to_auto()

    tk.Checkbutton(
        body,
        text="Hide the pop-out from mouse when on foot",
        variable=hide_var,
        command=_toggle_hide_on_foot,
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        selectcolor=bg,
        highlightthickness=0,
        bd=0,
        font=_ui_font(0),
        anchor="w",
    ).pack(anchor="w", pady=(0, 8))
    tk.Label(
        body,
        text="Windows only: clicks pass through the pop-out while your commander\nis on foot. Right-click the chat and pick Hide from mouse to override.",
        background=bg,
        foreground=fg,
        font=_ui_font(0),
        justify="left",
        anchor="w",
    ).pack(anchor="w", pady=(0, 8))

    grid = tk.Frame(body, background=bg)
    grid.pack(fill="x")

    def _label(text: str, row: int, col: int) -> None:
        tk.Label(grid, text=text, background=bg, foreground=fg, font=_ui_font(0)).grid(
            row=row, column=col, sticky="w", pady=2
        )

    def _entry(var: tk.StringVar, row: int, col: int) -> None:
        tk.Entry(
            grid,
            textvariable=var,
            width=6,
            justify="right",
            background=bg,
            foreground=fg,
            insertbackground=fg,
            highlightthickness=0,
            bd=1,
        ).grid(row=row, column=col, sticky="w", padx=(4, 14), pady=2)

    _label("Position X:", 0, 0)
    _entry(x_var, 0, 1)
    _label("Y:", 0, 2)
    _entry(y_var, 0, 3)
    _label("Duration (s):", 1, 0)
    _entry(ttl_var, 1, 1)
    _label("Size:", 1, 2)
    size_menu = tk.OptionMenu(grid, size_var, *OVERLAY_SIZES)
    size_menu.configure(
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        highlightthickness=0,
        bd=1,
        width=6,
        anchor="w",
        font=_ui_font(0),
    )
    size_menu["menu"].configure(
        background=bg,
        foreground=fg,
        activebackground=fg,
        activeforeground=bg,
        borderwidth=0,
    )
    size_menu.grid(row=1, column=3, sticky="w", padx=(4, 0), pady=2)

    btns = tk.Frame(body, background=bg)
    btns.pack(fill="x", pady=(12, 0))

    def _close() -> None:
        global _settings_win
        _save_overlay_settings(overlay_var, x_var, y_var, ttl_var, size_var)
        _set_chat_logging(bool(chat_var.get()))
        try:
            dlg.destroy()
        except Exception:
            pass
        _settings_win = None

    tk.Button(
        btns,
        text="Close",
        width=10,
        command=_close,
        background=bg,
        foreground=fg,
        activebackground=bg,
        activeforeground=fg,
        highlightthickness=0,
        font=_ui_font(0),
    ).pack(side="right")

    dlg.protocol("WM_DELETE_WINDOW", _close)
    dlg.bind("<Escape>", lambda _e: _close())

    if theme is not None:
        try:
            theme.update(dlg)
        except Exception:
            pass
    _style_tree(dlg, bg, fg)
    for channel, button in color_buttons.items():
        _paint_swatch(channel, button)
    _theme_titlebar(dlg)
    _apply_stay_on_top(dlg)

    def _retheme(_event=None) -> None:
        # Re-apply once the window is mapped; DWM title-bar attributes are only
        # honoured reliably after the frame exists, and EDMC may re-theme on map.
        try:
            new_bg, new_fg = _theme_colors()
            _style_tree(dlg, new_bg, new_fg)
            for channel, button in color_buttons.items():
                _paint_swatch(channel, button)
            _theme_titlebar(dlg)
            _apply_stay_on_top(dlg)
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
    global _popout, _popout_toggles, _popout_chat

    _dismiss_hover_tips()
    if _popout is not None:
        try:
            if _popout.winfo_exists():
                _popout.deiconify()
                _popout.lift()
                _popout.focus_force()
                _apply_stay_on_top(_popout)
                _refresh_clickthrough()
                return
        except Exception:
            pass

    parent = _main_frame if _main_frame is not None else None
    if parent is None:
        return

    try:
        _popout = tk.Toplevel(_dialog_master(parent))
    except Exception:
        logger.exception("Could not create Salty pop-out window")
        _popout = None
        return

    popout_x = _cfg_int(f"{CONFIG_PREFIX}_popout_x", DEFAULT_POPOUT_X)
    popout_y = _cfg_int(f"{CONFIG_PREFIX}_popout_y", DEFAULT_POPOUT_Y)
    popout_w = _cfg_int(f"{CONFIG_PREFIX}_popout_width", DEFAULT_POPOUT_WIDTH)
    popout_h = _cfg_int(f"{CONFIG_PREFIX}_popout_height", DEFAULT_POPOUT_HEIGHT)

    _popout.title(PLUGIN_DISPLAY_NAME)
    _popout.geometry(f"{popout_w}x{popout_h}+{popout_x}+{popout_y}")
    _popout.minsize(320, 200)

    try:
        _popout.wm_attributes("-alpha", _popout_opacity() / 100.0)
    except Exception:
        pass

    def _popout_map(_event=None) -> None:
        # Windows can reset the extended style after redraws, so make sure
        # the click-through state survives every re-map.
        if _popout is None:
            return
        try:
            if _popout.winfo_exists():
                _ct_reapply(_popout.winfo_id())
        except Exception:
            pass

    try:
        _popout.bind("<Map>", _popout_map, add="+")
    except Exception:
        pass
    _refresh_clickthrough()

    # Pack the bottom controls first (from the bottom edge) so that shrinking the
    # window never clips the Clear button / Pause Chat / Stay on top controls; the
    # chat area absorbs whatever space is left.
    bottom = tk.Frame(_popout)
    bottom.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
    tk.Button(bottom, text="Clear", command=_clear_messages, font=_ui_font(1)).pack(
        side="left"
    )
    tk.Button(bottom, text="Options", command=_open_settings, font=_ui_font(1)).pack(
        side="left", padx=(8, 0)
    )
    freeze = tk.Checkbutton(
        bottom, text="Pause Chat", variable=_freeze_var, font=_ui_font(1)
    )
    freeze.pack(side="left", padx=(8, 0))
    _ensure_filter_vars()
    _topmost_var.set(_cfg_bool(_stay_on_top_key(), DEFAULT_STAY_ON_TOP))
    topmost = tk.Checkbutton(
        bottom,
        text="Stay on top",
        variable=_topmost_var,
        command=_toggle_stay_on_top,
        font=_ui_font(1),
    )
    topmost.pack(side="left", padx=(8, 0))

    opacity = _popout_opacity()
    opacity_var = tk.IntVar(value=opacity)
    _bg, _fg = _theme_colors()
    tk.Label(bottom, text="Opacity:", font=_ui_font(1), background=_bg, foreground=_fg).pack(side="right", padx=(0, 4))
    opacity_slider = tk.Scale(
        bottom,
        from_=10,
        to=100,
        orient=tk.HORIZONTAL,
        variable=opacity_var,
        showvalue=False,
        length=100,
        background=_bg,
        foreground=_fg,
        activebackground=_bg,
        highlightthickness=0,
        troughcolor=_bg,
        relief="flat",
    )
    opacity_slider.pack(side="right")

    def _on_opacity_change(*_args) -> None:
        _apply_popout_opacity(opacity_var.get())

    opacity_var.trace_add("write", _on_opacity_change)

    # Channel + timestamp toggles, tucked just above the bottom controls so they
    # are always reachable (packed bottom-up, after the controls row).
    # Hide Boxes removes this row from the pop-out only; the settings window
    # keeps the same checkboxes so the filters can still be changed.
    toggles = tk.Frame(_popout)
    _popout_toggles = toggles
    _build_toggle_grid(
        toggles, include_timestamp=True, include_origin=True, columns=3, font_delta=1
    )
    if not _boxes_hidden():
        toggles.pack(side="bottom", fill="x", padx=4, pady=(0, 2))

    container = tk.Frame(_popout)
    _popout_chat = container
    container.pack(fill="both", expand=True, padx=4, pady=4)

    bg, fg = _theme_colors()
    # Pack the scrollbar BEFORE the text so it always keeps its parcel: when
    # the text requests more width than fits (wide UI fonts), the packer
    # squeezes later-packed widgets, which used to collapse the scrollbar.
    # The canvas-drawn scrollbar follows the EDMC theme exactly (trough in the
    # theme background, thumb in the theme accent); a classic native scrollbar
    # keeps its light thumb on Windows and cannot be recoloured reliably.
    text = tk.Text(
        container,
        wrap="word",
        state="disabled",
        height=16,
        width=64,
        spacing1=0,
        spacing2=0,
        spacing3=10,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        cursor="arrow",
    )
    scroll = ThemedScrollbar(
        container, command=text.yview, background=bg, foreground=fg
    )
    scroll.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.configure(yscrollcommand=scroll.set)
    _tag_text(text)

    def _on_close() -> None:
        global _popout, _popout_toggles, _popout_chat
        _unregister_view(text)
        try:
            config.set(f"{CONFIG_PREFIX}_popout_x", _popout.winfo_x())
            config.set(f"{CONFIG_PREFIX}_popout_y", _popout.winfo_y())
            config.set(f"{CONFIG_PREFIX}_popout_width", _popout.winfo_width())
            config.set(f"{CONFIG_PREFIX}_popout_height", _popout.winfo_height())
        except Exception:
            pass
        try:
            _ct_forget(_popout.winfo_id())
        except Exception:
            pass
        try:
            _popout.destroy()
        except Exception:
            pass
        _popout = None
        _popout_toggles = None
        _popout_chat = None
        _set_popout_active(False)

    _popout.protocol("WM_DELETE_WINDOW", _on_close)

    _popout_geom_after_id = None
    def _on_configure(_event=None):
        nonlocal _popout_geom_after_id
        try:
            if _popout is None or not _popout.winfo_exists():
                return
            if _popout_geom_after_id is not None:
                _popout.after_cancel(_popout_geom_after_id)
            _popout_geom_after_id = _popout.after(300, _save_popout_geometry)
        except Exception:
            pass

    def _save_popout_geometry():
        nonlocal _popout_geom_after_id
        try:
            if _popout is None or not _popout.winfo_exists():
                return
            config.set(f"{CONFIG_PREFIX}_popout_x", _popout.winfo_x())
            config.set(f"{CONFIG_PREFIX}_popout_y", _popout.winfo_y())
            config.set(f"{CONFIG_PREFIX}_popout_width", _popout.winfo_width())
            config.set(f"{CONFIG_PREFIX}_popout_height", _popout.winfo_height())
        except Exception:
            pass
        _popout_geom_after_id = None

    _popout.bind("<Configure>", _on_configure)

    _register_view(text)
    text.configure(state="normal")
    text.see("end")
    text.configure(state="disabled")
    _set_popout_active(True)

    def _restyle_opacity():
        try:
            s_bg, s_fg = _theme_colors()
            opacity_slider.configure(
                background=s_bg,
                foreground=s_fg,
                activebackground=s_bg,
                troughcolor=s_bg,
            )
            bottom.configure(background=s_bg)
            for child in bottom.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(background=s_bg, foreground=s_fg)
        except Exception:
            pass

    try:
        _popout.after_idle(_style_chat_texts)
        _popout.after(300, _style_chat_texts)
        _popout.after(150, _restyle_opacity)
        _popout.after(500, _restyle_opacity)
        _popout.after(150, lambda: _theme_titlebar(_popout))
        _popout.after_idle(lambda: _apply_stay_on_top(_popout))
        _popout.after(150, lambda: _apply_stay_on_top(_popout))
    except Exception:
        pass


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """Build the Salty widget for the EDMC main window."""
    global _main_frame, _main_text

    _main_frame = tk.Frame(parent)

    _ensure_filter_vars()

    log_frame = tk.Frame(_main_frame)
    log_frame.pack(fill="x", expand=False, padx=2, pady=2)

    # The box never fills the window vertically (the frame above packs it with
    # fill="x"). It starts at the cap and _fit_main_text_height shrinks it to
    # its content, so an almost empty log leaves no tall blank gap later.
    # expand=True lets it grow horizontally as the window is widened.
    text = tk.Text(
        log_frame,
        wrap="word",
        state="disabled",
        height=MAIN_TEXT_MAX_LINES,
        width=34,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        cursor="arrow",
    )
    text.pack(side="left", fill="both", expand=True)
    bg, fg = _theme_colors()
    scroll = ThemedScrollbar(
        log_frame,
        command=text.yview,
        background=bg,
        foreground=fg,
        width=18,
        min_thumb=32,
    )
    scroll.pack(side="right", fill="y")

    def _on_main_scroll(first: str, last: str) -> None:
        scroll.set(first, last)
        try:
            at = float(first)
        except Exception:
            at = None
        _update_history_hint(at)

    text.configure(yscrollcommand=_on_main_scroll)
    _tag_text(text)

    # No button strip: a single click opens the pop-out, a double click opens
    # settings, and a right click offers both from a small menu.
    text.bind("<Button-1>", _on_chat_click)
    text.bind("<Double-Button-1>", _on_chat_double_click)
    text.bind("<Button-3>", _on_chat_menu)
    _attach_hover_tip(text, HOVER_TIP_TEXT)
    # Wrapping changes with the width, so re-fit the number of shown lines
    # whenever the box is resized.
    text.bind("<Configure>", lambda _event: _fit_main_text_height(), add="+")

    _main_text = text
    _install_history_hint(text)
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

    # Explain the new click controls for a few seconds, then show the saved
    # chat log. Live messages still arrive (and display) in the meantime.
    _snapshot_chat_log()
    _show_startup_hint()

    return _main_frame


# --------------------------------------------------------------------------- #
# Settings tab
# --------------------------------------------------------------------------- #
def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> tk.Frame | None:
    global _prefs_vars

    _prefs_vars = {}
    _ensure_filter_vars()
    frame = nb.Frame(parent)

    nb.Label(frame, text=PLUGIN_DISPLAY_NAME).grid(
        row=0, column=0, columnspan=4, sticky="w"
    )
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
    ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 2))
    row += 1

    chat_logging_var = tk.BooleanVar(value=_chat_logging_enabled())
    _prefs_vars["chat_logging"] = chat_logging_var
    nb.Checkbutton(
        frame,
        text="Chat logging (keep the chat history in a log file)",
        variable=chat_logging_var,
    ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
    row += 1

    overlay_var = tk.BooleanVar(
        value=_cfg_bool(f"{CONFIG_PREFIX}_overlay", DEFAULT_OVERLAY_ENABLED)
    )
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
        var = tk.BooleanVar(
            value=_cfg_bool(_notify_key(channel), DEFAULT_NOTIFY.get(channel, True))
        )
        _prefs_vars[f"notify_{channel}"] = var
        nb.Checkbutton(frame, text=CHANNEL_LABELS[channel], variable=var).grid(
            row=row + index // 3, column=index % 3, sticky="w"
        )
    row += (len(CHANNELS) + 2) // 3

    base_row = row + 1

    cfg_x, cfg_y = _overlay_pos_from_cfg()

    nb.Label(frame, text="Overlay position X:").grid(
        row=base_row, column=0, sticky="w", pady=(8, 0)
    )
    x_var = tk.StringVar(value=str(cfg_x))
    _prefs_vars["overlay_x"] = x_var
    nb.EntryMenu(frame, textvariable=x_var, width=6).grid(
        row=base_row, column=1, sticky="w", pady=(8, 0)
    )

    nb.Label(frame, text="Y:").grid(row=base_row, column=2, sticky="e", pady=(8, 0))
    y_var = tk.StringVar(value=str(cfg_y))
    _prefs_vars["overlay_y"] = y_var
    nb.EntryMenu(frame, textvariable=y_var, width=6).grid(
        row=base_row, column=3, sticky="w", pady=(8, 0)
    )

    nb.Label(frame, text="Display duration (s):").grid(
        row=base_row + 1, column=0, sticky="w"
    )
    ttl_var = tk.StringVar(
        value=str(_cfg_int(f"{CONFIG_PREFIX}_overlay_ttl", DEFAULT_OVERLAY_TTL))
    )
    _prefs_vars["overlay_ttl"] = ttl_var
    nb.EntryMenu(frame, textvariable=ttl_var, width=6).grid(
        row=base_row + 1, column=1, sticky="w"
    )

    nb.Label(frame, text="Text size:").grid(row=base_row + 1, column=2, sticky="e")
    size_var = tk.StringVar(
        value=_cfg_str(f"{CONFIG_PREFIX}_overlay_size", DEFAULT_OVERLAY_SIZE)
    )
    if size_var.get() not in OVERLAY_SIZES:
        size_var.set(DEFAULT_OVERLAY_SIZE)
    _prefs_vars["overlay_size"] = size_var
    size_box = ttk.Combobox(
        frame,
        textvariable=size_var,
        values=list(OVERLAY_SIZES),
        width=7,
        state="readonly",
    )
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
        chat_var = _prefs_vars.get("chat_logging")
        if chat_var is not None:
            _set_chat_logging(bool(chat_var.get()))
        for channel in CHANNELS:
            var = _prefs_vars.get(f"notify_{channel}")
            if var is not None:
                config.set(_notify_key(channel), bool(var.get()))
        config.set(
            f"{CONFIG_PREFIX}_overlay_x",
            _to_int(_prefs_vars["overlay_x"].get(), DEFAULT_OVERLAY_X),
        )
        config.set(
            f"{CONFIG_PREFIX}_overlay_y",
            _to_int(_prefs_vars["overlay_y"].get(), DEFAULT_OVERLAY_Y),
        )
        config.set(
            f"{CONFIG_PREFIX}_overlay_ttl",
            _to_int(_prefs_vars["overlay_ttl"].get(), DEFAULT_OVERLAY_TTL),
        )
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
    # Read the saved chat log before any live message can be appended to it.
    _snapshot_chat_log()
    return PLUGIN_INTERNAL_NAME


def plugin_stop() -> None:
    logger.info("%s stopped", PLUGIN_DISPLAY_NAME)


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str | None,
    station: str | None,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> None:
    _set_on_foot(bool(state.get("OnFoot")))
    event = entry.get("event")

    if event in ("SendText", "ReceiveText"):
        logger.debug("journal_entry received %s: %r", event, entry.get("Message"))

    if event == "SendText":
        raw_to = entry.get("To_Localised") or entry.get("To")
        channel = _normalise_channel(raw_to)
        target = _private_peer(raw_to) if channel == "private" else ""
        _add_message(
            channel,
            "Me",
            entry.get("Message", ""),
            incoming=False,
            entry=entry,
            target=target,
        )

    elif event == "ReceiveText":
        channel = _normalise_channel(entry.get("Channel"))
        sender = entry.get("From_Localised") or entry.get("From") or "Unknown"
        message = entry.get("Message_Localised") or entry.get("Message") or ""
        _add_message(channel, sender, message, incoming=True, entry=entry)
