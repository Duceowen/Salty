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
- **Pop-out window** for a larger, resizable chat view, with its own filter toggles.
- **Settings** button (right of **Pause Chat**) opens a themed, resizable window
  with the channel/timestamp toggles and the overlay options.
- **Pause Chat** toggle so the log stops auto-scrolling while you read back.
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

- **Main window** – the compact log lists chat as it happens. The filter toggles
  are deliberately kept off this widget; use **Settings** or the pop-out window
  instead.
- **Settings** – opens the themed Salty settings window (channel filters, timestamp
  toggle and all overlay options). Changes apply immediately. The window is
  resizable; it opens sized and centred over EDMC, with a minimum size that keeps
  every control visible.
- **Window** – opens a larger pop-out copy of the log, with its own channel +
  timestamp toggles along the bottom. Close it any time; the main-window log keeps
  running.
- **Clear** – asks for confirmation, then empties the log.
- **Pause Chat** – when ticked, the view stops jumping to the newest message.

## Settings (File > Settings > Salty)

- **Show messages in** – per-channel show/hide toggles (applied to the whole log
  immediately and saved). The same toggles appear in the pop-out window and in the
  themed settings window.
- **Show timestamps** – prefix each line with the message time (`HH:MM:SS`).
- **Show message origin** – show/hide the channel label (e.g. `[Local]`, `[System]`).
  With it off, lines read `[time] Sender: message`.
- **Show incoming messages on screen** – master switch for Modern Overlay notifications.
- **Notify me on messages in** – per-channel notification toggles (NPC is off by default).
- **Overlay position X / Y** – where the newest notification is drawn. Each new
  notification appears at the top and older ones are pushed down, so a burst of
  messages stacks into a readable column instead of overlapping. Up to 8 are shown
  at once. Notifications are drawn **top-left anchored** at X / Y, so the text grows
  to the right and never runs off the left edge. The default anchor is the **left
  side of the screen, 30% of the way down from the top** (computed from your screen
  size); adjust X / Y if the column appears off-screen. You can also reposition the
  overlay from Modern Overlay's own UI.
- **Display duration** – how many seconds each notification stays on screen.
- **Text size** – `normal`, `large` or `huge`.

## Notes

- On-screen notifications are drawn by Modern Overlay, which positions its overlay
  window by following the Elite Dangerous game window. The plugin only chooses the
  X / Y inside that window; which monitor is used is decided by Modern Overlay (and
  follows the game once it is running).
- Messages are kept in memory only (last 1000); nothing is written to disk.
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
