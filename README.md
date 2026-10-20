# Salty

A port of the **Communicator** plugin from [Elite Observatory Core](https://github.com/Xjph/ObservatoryCore)
to [EDMarketConnector](https://github.com/EDCD/EDMarketConnector).

It records every in-game chat message (both sent and received), shows them in
the EDMC main window (with an optional larger pop-out window), lets you filter
by channel, and can raise on-screen notifications for incoming messages through
the [Modern Overlay](https://github.com/EDCD/EDMC-Plugin-Registry) plugin.

## Features

- **Chat log** of all sent and received messages with optional timestamp and
  channel-origin label.
- **Channel filters** for Local, System, Private, Wing, Squadron, Officer and NPC, plus
  **timestamp** and **origin** toggles. These live on the plugin's **Settings tab**
  and in the **pop-out window**, so the compact main-window widget stays clean.
  **Hide Boxes** in Salty Settings removes that row from the pop-out.
- **On-screen notifications** for incoming messages, per channel, delivered via Modern Overlay.
- **Pop-out window** for a larger, resizable chat view with the full chat log and
  its own filter toggles. The main window shows the last 30 messages. Scroll
  that log to the top and, when older messages exist, it tells you to click the
  box for the rest.
- **Click controls on the main chat box**: single click opens the pop-out, double
  click opens **Settings**, right click shows both as menu items. A one-time hint
  inside the chat box explains this for the first 6 seconds. Hovering the chat
  box shows the same short tip. The chat box uses the normal arrow cursor and has
  no border.
- **Private messages** keep the **[Private]** origin tag and show direction.
  Incoming lines read `[Private] Name > Me:`. Outgoing lines read
  `[Private] Me > Name:`. Other channels are unchanged. The local commander is
  always **Me**.
- **Channel colors** for Local, System, Private, Wing, Squadron and Officer.
  The same colours are used for Modern Overlay notifications. Overlay text wraps
  at about 36 characters, on word boundaries.
- **Chat logging** (on by default) appends every message to a log file next to
  EDMC's own logs, and the saved history is loaded back in on startup.
- **Pause Chat** toggle (in the pop-out window) so the log stops auto-scrolling
  while you read back.
- **Hide from mouse** (Windows): the pop-out can pass clicks through to the
  game while your commander is on foot, with an Auto / Hidden / Shown override
  in the right-click menu.
- Settings persisted in EDMC's own config, a dedicated tab in EDMC's Settings dialog,
  and the themed settings window.

## Channel mapping

Elite Dangerous uses several channel tokens; these are normalised as follows:

| In-game token            | Salty channel        |
|--------------------------|----------------------|
| `local`                  | Local                |
| `starsystem`, `system`   | System               |
| `wing`                   | Wing                 |
| `squadron`               | Squadron             |
| `squadleaders`           | Officer              |
| `npc`                    | NPC                  |
| everything else          | Private              |

`player`, `friend`, `voicechat` and direct messages all fall into **Private**.

A received private message is shown as `[Private] <commander> > Me:`.
A sent private message is shown as `[Private] Me > <commander>:`.
The log file stores both ends on every private row (`from`, `to`, and `in` or `out`).
Messages you send on any channel are attributed to **Me**, not your commander name.

## Install

1. Close EDMC.
2. Copy the `salty` folder into your EDMC `plugins` directory:
   - Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins`
   - Mac: `~/Library/Application Support/EDMarketConnector/plugins`
   - Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins` (or `~/.local/share/EDMarketConnector/plugins`)
3. Restart EDMC. A "Salty" widget appears in the main window and a
   "Salty" tab appears in **File > Settings**.

> On-screen notifications require the **Modern Overlay** plugin to be installed
> and running. Without it, the chat log still works normally and notifications
> are silently skipped.

## Usage

- **Main window** – the compact log lists the last 30 messages. Older messages
  stay in the chat log file and in the pop-out window. The scrollbar thumb is a
  full indicator, including when the log is sitting on the newest line. Scroll
  to the top and, when there is more history, the box says *"Click the box to
  expand for more history."* Clicking it opens the pop-out. The box is only as
  tall as the lines it is showing (up to four), so an almost empty log does not
  leave a blank lower gap; it grows as messages arrive and scrolls past four.
  The widget itself is a launcher rather than a button strip:

  | Action | Result |
  |--------|--------|
  | Single click | opens the pop-out window |
  | Double click | opens the **Settings** window |
  | Right click | menu with **Pop out window** and **Settings** |

  A hint reading *"Single Click to pop window out Double Click for Options."* is
  shown **inside the chat box** for the first **6 seconds**. Clicking the chat box
  before those 6 seconds are up removes the hint and opens the pop-out. The same
  sentence is shown as a small tip once the pointer has rested on the chat box for
  a second, and the tip hides itself again after six seconds. The
  saved chat log is loaded and displayed once that hint disappears. Live messages
  that arrive during those 6 seconds are displayed straight away. The countdown
  only starts when the chat box is actually on screen, so the hint is never missed
  while EDMC is showing a different tab.

  While the pop-out is open, the main widget is replaced by a single line reading
  **"Chat Pop-out Active"** – the pop-out owns the full chat log. Closing the
  pop-out brings the live log back.

- **Settings** – opens the themed Salty settings window (channel filters,
  timestamp toggle, channel colours, chat logging and all overlay options).
  Changes apply immediately. The window is resizable; it opens sized and
  centred over EDMC, with a minimum size that keeps every control visible.
  **Hide Boxes** removes the Show Messages checkboxes from the pop-out. The button
  then reads **Show Boxes**. The choice is saved, and the checkboxes in Settings
  stay available. **Clear Chat logs** asks for confirmation, then deletes
  `SaltyChat.log` and the messages currently shown. **Open Log Folder** opens the
  folder that contains that file so you can copy a backup.
- **Window** (pop-out) – opens a larger copy of the full chat log, with its own
  channel + timestamp toggles along the bottom unless **Hide Boxes** is on.
  Close it any time; the main-window log keeps running.
- **Options** (pop-out) – opens the same Settings window.
- **Clear** (pop-out) – asks for confirmation, then empties the chat window.
  The saved log file is left in place; use **Clear Chat logs** to delete it.
- **Pause Chat** (pop-out) – when ticked, the view stops jumping to the newest
  message.

## Chat logging

**Chat logging** is enabled by default. Every message is appended to
`SaltyChat.log` in EDMC's own `logs` folder, and the saved history is read back
into the plugin (up to the last 1000 messages) once the in-box click hint has been
shown. Turn it off from the **Settings** window or the Salty tab in
**File > Settings**.

## Settings (File > Settings > Salty)

- **Show messages in** – per-channel show/hide toggles (applied to the whole log
  immediately and saved). The same toggles appear in the pop-out window and in the
  themed settings window. **Hide Boxes**, in the themed settings window, hides
  that pop-out row. Click it again (**Show Boxes**) to bring the row back.
- **Show timestamps** – prefix each line with the message time (`HH:MM:SS`).
- **Show message origin** – show/hide the channel label (e.g. `[Local]`, `[System]`).
  With it off, lines read `[time] Sender: message`.
- **Chat logging** – append every message to `SaltyChat.log` in EDMC's logs folder
  and reload it on startup. On by default.
- **Show incoming messages on screen** – master switch for Modern Overlay notifications.
- **Hide the pop-out from mouse when on foot** – Windows only, off by default.
  While on, the pop-out passes mouse clicks through to whatever is underneath
  whenever your commander is on foot; the title bar then reads
  **Salty (hidden from mouse)**. The right-click menu item
  **Hide from mouse: Detect / Hidden / Off** overrides this for the session,
  and toggling this checkbox returns control to Auto.
- **Notify me on messages in** – per-channel notification toggles (NPC is off by default).
- **Overlay position X / Y** – where the newest notification is drawn. These are
  coordinates on Modern Overlay's fixed **1280x960 canvas**, not screen pixels.
  Each new notification appears at the top and older ones are pushed down, so a
  burst of messages stacks into a readable column instead of overlapping. Up to 8
  are shown at once. Notifications are drawn **top-left anchored** at X / Y, so the
  text grows to the right and never runs off the left edge. The default anchor is
  the **left side, 30% of the way down the visible canvas**. X / Y are stored and
  displayed exactly as you enter them; at draw time the column is nudged back into
  the region Modern Overlay actually shows (its default "fill" scale mode hides
  the overflow on wider-than-4:3 displays), shifting up only if it would otherwise
  run off the edge. So a message always stays on screen even if an out-of-range
  value is entered, and a single message stays exactly where you placed it. You can
  also reposition the overlay from Modern Overlay's own UI.
- **Display duration** – how many seconds each notification stays on screen.
- **Text size** – `normal`, `large` or `huge`.

## Notes

- On-screen notifications are drawn by Modern Overlay, which positions its overlay
  window by following the Elite Dangerous game window. The plugin only chooses the
  X / Y inside that window; which monitor is used is decided by Modern Overlay (and
  follows the game once it is running).
- Messages are held in memory (last 1000) and, when **Chat logging** is on (the
  default), appended to `SaltyChat.log` in EDMC's `logs` folder.
- The plugin follows EDMC's plugin API and performs all UI work on the main thread.
- **Stay on top on Linux:** Salty keeps reapplying the window manager's above
  flag while the pop-out is open. A focused fullscreen or borderless-fullscreen
  game still uses the window manager's fullscreen layer, so it can cover the
  pop-out. On KDE Plasma 6, add a window rule for the Salty pop-out and set
  **Layer** to **Overlay**. On other desktops, use windowed mode or Modern
  Overlay notifications.

## Troubleshooting

- **Notifications appear on more than one monitor.** This means more than one
  Modern Overlay client is running at once, each drawing the same notification on
  its own monitor. It normally happens after EDMC has been force-closed/killed,
  which orphans the overlay client that EDMC had started. Fix it by closing EDMC
  normally, ending any leftover overlay clients, then restarting EDMC (or use
  Modern Overlay's own "Restart overlay" action). To find stray clients on Windows:

  ```powershell
  Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like '*overlay_client.overlay_client*' } |
    Select-Object ProcessId, ParentProcessId
  ```

  There should be a single instance (one launcher process and its child). If there
  are extra pairs whose parent EDMC no longer exists, end those extra processes.
- **Notifications do not appear at all.** Make sure the Modern Overlay plugin is
  installed and running, and that "Show incoming messages on screen" is enabled in
  the Salty settings tab.

## Changelog

### 1.2.2

- **Hide from mouse fix:** Detect mode only hides the pop-out while Elite
  Dangerous is running. Leaving the game on foot and reopening EDMC no longer
  leaves the pop-out click-through; Shutdown and MainMenu clear the state.

### 1.2.1

- **Stay on top on Linux:** Salty keeps reapplying the window manager's above
  flag while the pop-out is open. A focused fullscreen or borderless-fullscreen
  game still uses the window manager's fullscreen layer, so it can cover the
  pop-out. On KDE Plasma 6, add a window rule for the Salty pop-out and set
  **Layer** to **Overlay**. On other desktops, use windowed mode or Modern
  Overlay notifications.

### 1.2.0

- **Hide the pop-out from mouse** (Windows). While active, clicks pass through
  the pop-out window to whatever is underneath. **Hide the pop-out from mouse
  when on foot** in Settings starts off; while it is on, the pop-out becomes
  click-through whenever your commander is on foot. Right-click the chat and
  pick **Hide from mouse: Detect / Hidden / Off** to override for the session,
  and toggling the Settings checkbox returns it to Detect. While clicks pass
  through, the title bar reads **Salty (hidden from mouse)**.

### 1.1.1

- The main-window scrollbar thumb stays a full indicator when the log is at
  the bottom, instead of collapsing into a short dash.
- The main window shows the last 30 messages. The pop-out and `SaltyChat.log`
  keep the full history.
- Scrolling that main log to the top, when older messages exist, tells you to
  click the box to expand for more history.
- Private lines keep the **[Private]** tag and use a direction:
  `[Private] Name > Me:` incoming and `[Private] Me > Name:` outgoing.
  Other channels stay as they are.
- The hover tip closes when the chat box is clicked, including when that click
  opens the pop-out.
- The main window redraws its visible lines in one pass. Scrolling uses a
  cached flag to decide whether the history note should show.

### 1.1.0

- Private messages show **From:** on incoming lines and **To:** plus the
  recipient on outgoing lines. Both labels can be turned off in Settings.
  The local commander is logged as **Me**.
- The chat log file records who a private message is from and who it is to.
- **Options** on the pop-out opens Settings. **Clear Chat logs** and
  **Open Log Folder** are on that page. Clearing the pop-out chat still asks
  first.
- Channel colour pickers for Local, System, Private, Wing, Squadron and Officer.
  Modern Overlay uses the same colours, and wraps notification text at about
  36 characters without splitting words.
- The startup hint lasts 6 seconds, and a click during that time closes it and
  opens the pop-out. The main chat box uses the arrow cursor, has no border,
  and its scrollbar thumb is larger.

### 1.0.2

- **Hide Boxes.** Salty Settings has a Hide Boxes button under Show messages in.
  It removes the channel, Time, and Origin checkboxes from the pop-out window.
  The button then reads Show Boxes, and the choice is saved. The checkboxes in
  Settings stay available, so filters still apply.
- **Quality of life.** The pop-out can stay clear of the filter row while Clear,
  Pause Chat, Stay on top, and Opacity remain. Opening the pop-out again keeps
  the same view.

### 1.0.1

- Opacity slider for the pop-out window, and alignment fixes in Settings.
- Squadron Leaders channel label renamed to Officer.

### 1.0.0

- First release. Chat log, channel filters, pop-out window, stay-on-top,
  on-screen notifications, and chat logging.

## Development

The plugin is a single `load.py` at the repository root, so it can be installed by
dropping it into `plugins/Salty/` (see [Install](#install)).

### EDMC plugin API

`load.py` exposes the standard EDMC plugin entry points. There is no separate HTTP
API: the plugin is driven by EDMC and by Elite Dangerous journal events, so the
"public interface" is the set of callbacks another EDMC plugin or EDMC itself can call.

| Callback | Purpose |
| --- | --- |
| `plugin_start3(plugin_dir)` | Called by EDMC on load; returns the display name `"Salty"`. |
| `plugin_app(parent)` | Builds and returns the widget shown on EDMC's Salty tab. |
| `plugin_prefs(parent, cmdr, is_beta)` | Builds the Salty tab in EDMC's Settings dialog. |
| `prefs_changed(cmdr, is_beta)` | Persists the settings-tab widgets into EDMC's config. |
| `journal_entry(cmdr, is_beta, system, station, entry, state)` | Consumes `ReceiveText` / `SendText` journal events. |
| `plugin_stop()` | Releases resources when EDMC unloads the plugin. |

Example (from another EDMC plugin) — read the settings this plugin persists:

```python
from config import config

# Channel visibility and notification toggles, e.g. 'salty_show_local',
# 'salty_notify_local', plus 'salty_overlay', 'salty_timestamps',
# 'salty_origins', 'salty_chat_logging',
# 'salty_hide_boxes', and 'salty_color_local' (plus the other channel colours).
show_local = config.get_bool("salty_show_local")
```

```javascript
// The same keys are plain entries in EDMC's config, so they can also be read
// outside Python (e.g. to drive an external tooltip or stream overlay).
// config.toml -> salty_show_local = true
```

### Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request. It byte-compiles
`load.py`, checks that `__version__` is strict SemVer, and lints with ruff
(`--select E9,F`).

### Plugin registry listing

`.github/registry/Salty.json` is the entry submitted to the
[EDMC Plugin Registry](https://github.com/EDCD/EDMC-Plugin-Registry), which is what
makes the plugin appear in EDMC's plugin browser. When cutting a new version, bump
`__version__` in `load.py`, update `pluginVer`, `pluginLastUpdate` and
`pluginLastTestedEDMC` here, then open a PR to the registry with the updated file.

## Credits

Ported from **Observatory Communicator** by Vithigar (Elite Observatory Core, MIT).

## License

MIT — see [LICENSE](LICENSE). The original `Copyright (c) 2021 Jonathan Miller`
notice is retained because this is a derivative work of Elite Observatory Core.
