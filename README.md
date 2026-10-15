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
- **Channel filters** for Local, System, Private, Wing, Squadron and NPC, plus
  **timestamp** and **origin** toggles. These live on the plugin's **Settings tab**
  and in the **pop-out window**, so the compact main-window widget stays clean.
- **On-screen notifications** for incoming messages, per channel, delivered via Modern Overlay.
- **Pop-out window** for a larger, resizable chat view with the full chat log and
  its own filter toggles.
- **Click controls on the main chat box**: single click opens the pop-out, double
  click opens **Settings**, right click shows both as menu items. A one-time hint
  inside the chat box explains this for the first 10 seconds.
- **Chat logging** (on by default) appends every message to a log file next to
  EDMC's own logs, and the saved history is loaded back in on startup.
- **Pause Chat** toggle (in the pop-out window) so the log stops auto-scrolling
  while you read back.
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
| `npc`                    | NPC                  |
| everything else          | Private              |

`player`, `friend`, `voicechat` and direct messages all fall into **Private**.

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

- **Main window** – the compact log lists chat as it happens. The widget itself is
  a launcher rather than a button strip:

  | Action | Result |
  |--------|--------|
  | Single click | opens the pop-out window |
  | Double click | opens the **Settings** window |
  | Right click | menu with **Pop out window** and **Settings** |

  A hint reading *"Single Click to Open Chat box. Double click for settings."* is
  shown **inside the chat box** for the first **10 seconds**; the saved chat log
  is loaded and displayed once that hint disappears. Live messages that arrive
  during those 10 seconds are displayed straight away. The countdown only starts
  when the chat box is actually on screen, so the hint is never missed while
  EDMC is showing a different tab.

  While the pop-out is open, the main widget is replaced by a single line reading
  **"Chat Pop-out Active"** – the pop-out owns the full chat log. Closing the
  pop-out brings the live log back.

- **Settings** – opens the themed Salty settings window (channel filters, timestamp
  toggle, chat logging and all overlay options). Changes apply immediately. The
  window is resizable; it opens sized and centred over EDMC, with a minimum size
  that keeps every control visible.
- **Window** (pop-out) – opens a larger copy of the full chat log, with its own
  channel + timestamp toggles along the bottom. Close it any time; the main-window
  log keeps running.
- **Clear** (pop-out) – asks for confirmation, then empties the log.
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
  themed settings window.
- **Show timestamps** – prefix each line with the message time (`HH:MM:SS`).
- **Show message origin** – show/hide the channel label (e.g. `[Local]`, `[System]`).
  With it off, lines read `[time] Sender: message`.
- **Chat logging** – append every message to `SaltyChat.log` in EDMC's logs folder
  and reload it on startup. On by default.
- **Show incoming messages on screen** – master switch for Modern Overlay notifications.
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

## Credits

Ported from **Observatory Communicator** by Vithigar (Elite Observatory Core, MIT).
