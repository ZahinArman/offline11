# ShutCap

![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

ShutCap is a small Windows tray utility that turns the PC off once each night, at a time that you choose.

ShutCap is a gentle nudge, not a lock. It never locks you out of your PC.

## Contents

- [How it works](#how-it-works)
- [Install](#install)
- [First-time setup](#first-time-setup)
- [Daily use](#daily-use)
- [The curfew](#the-curfew)
- [Safety rules](#safety-rules)
- [Settings](#settings)
- [Notifications](#notifications)
- [Uninstall](#uninstall)
- [Run from source](#run-from-source)
- [Test mode](#test-mode)
- [Start at sign-in by hand](#start-at-sign-in-by-hand)
- [Build the installer](#build-the-installer)
- [Tests](#tests)
- [Code layout](#code-layout)
- [Limitations](#limitations)
- [License](#license)

## How it works

1. You choose the time at which the PC turns off.
2. ShutCap calculates the warning times from that time.
3. ShutCap shows two warnings before the curfew starts.
4. At the curfew, ShutCap shows a dialog and a countdown.
5. At the turn-off time, ShutCap runs `shutdown.exe /s /t 60`.
6. Windows gives your apps 60 seconds, then the PC turns off.

ShutCap does not use `/f`. Windows does not force apps to close.

ShutCap has no telemetry, no accounts, and no cloud service.

## Install

Requirements: Windows 10 or Windows 11. You do not need administrator rights.

1. Open the [Releases](https://github.com/ZahinArman/shutcap/releases) page.
2. Download `ShutCap-Setup.exe`.
3. Double-click the file.
4. Click **Yes**.

The setup program does these tasks:

- It installs ShutCap to `%LOCALAPPDATA%\Programs\ShutCap`.
- It adds Start Menu and Desktop shortcuts.
- It adds **Uninstall ShutCap** to the Start Menu.
- It adds ShutCap to Settings > Apps > Installed apps.
- It sets ShutCap to start at sign-in, minimized to the tray.
- It starts ShutCap.

To upgrade, run a newer setup file. The upgrade keeps your settings.

> **NOTE:** The setup file is not code-signed. Windows SmartScreen can show a warning. Click **More info**, then click **Run anyway**.

## First-time setup

On the first start, ShutCap shows a setup window with two steps.

**Step 1.** The window asks: "When should your PC turn off each night?"

1. Enter the hour and the minute. Use the 24-hour format.
2. Click **NEXT**.

**Step 2.** The window shows the other times. ShutCap calculates them from your turn-off time. You can edit each time.

| Event | Default time |
| --- | --- |
| First warning | 45 minutes before turn-off |
| Second warning | 25 minutes before turn-off |
| Curfew starts (dialog and countdown) | 15 minutes before turn-off |
| Reminder | 10 minutes before turn-off |
| Reminder | 5 minutes before turn-off |
| Last-minute warning | 1 minute before turn-off |
| PC turns off | Your chosen time |

Step 2 also has the **Dry-run (practice) mode** check box. This box is on by default. In dry-run mode, ShutCap shows the warnings but does not turn off the PC.

Click **FINISH** to save the schedule. If you close the setup window, ShutCap keeps the default times.

You can change all times later in Settings. A schedule can cross midnight, for example turn-off at 00:30.

## Daily use

ShutCap runs in the system tray. Open the dashboard from the tray icon.

The dashboard shows the status and the schedule for tonight. It has these buttons:

- **TEST CURFEW**: shows the curfew dialog only. It does not start a shutdown.
- **ABORT PENDING SHUTDOWN**: stops a shutdown that is in progress.
- **RE-ARM CURFEW (RESET TO NORMAL)**: turns the schedule on again after an emergency or an abort.

ShutCap allows only one running copy. If you start it again, ShutCap shows a message and does not open a second copy.

## The curfew

At the curfew start, ShutCap shows a topmost dialog. The text is "PC TIME IS OVER. Is there a genuine emergency?" The dialog has two buttons:

- **NO EMERGENCY**
- **GENUINE EMERGENCY**

If you ignore the dialog, the shutdown continues.

A floating countdown window shows the time that remains.

To cancel tonight, use one of these methods:

1. **Emergency.** Click **GENUINE EMERGENCY**. Write a reason. Tick the confirmation box. ShutCap cancels tonight and writes the event to the audit log.
2. **Abort.** Click **ABORT PENDING SHUTDOWN** on the dashboard. Confirm the question. ShutCap runs `shutdown /a` and writes the event to the audit log.

To stop a shutdown by hand:

1. Press Win+R.
2. Type `shutdown /a`.
3. Press Enter.

If Windows refuses the shutdown command, the status changes to `SHUTDOWN_FAILED`. ShutCap shows an error message.

## Safety rules

ShutCap follows these rules. The code in `shutcap/scheduler.py` and the test file `tests/test_no_lockout.py` enforce them.

- ShutCap enforces the turn-off at most once each night.
- If the PC starts, restarts, or wakes from sleep after the curfew started, ShutCap does nothing that night. It shows no dialog, no countdown, and no warning.
- ShutCap saves a heartbeat every 10 seconds. If the heartbeat is older than 60 seconds, ShutCap knows that the PC was off or asleep.
- If you restart the app while the PC stays on, the countdown continues.
- ShutCap shows no old pop-ups the next morning.
- An alert never repeats after a restart. If several alerts are late at the same time, ShutCap shows only the most recent alert.
- When the night window ends, ShutCap closes unfinished nights without a message.

## Settings

Open Settings from the dashboard or the tray icon. ShutCap applies each change immediately.

In Settings you can:

- Change the turn-off time and all warning times.
- Turn dry-run mode on or off.
- Turn **Start ShutCap automatically when Windows boots** on or off.
- Set up Android push notifications.

## Notifications

ShutCap uses these alerts:

- Windows toast messages
- Warning sounds
- Topmost warning pop-up windows
- Optional Android push messages through [ntfy.sh](https://ntfy.sh)

To use Android push messages:

1. Install the ntfy app on your Android phone.
2. In Settings, tick **Android Push (ntfy.sh topic)**.
3. Enter a private topic name.
4. In the ntfy app, subscribe to the same topic.

> **NOTE:** Anyone who knows your topic name can read your messages. Use a long topic name that others cannot guess.

### Logs

ShutCap keeps its files in `%LOCALAPPDATA%\ShutCap`:

- `audit.log` records each warning, decision, emergency, abort, and shutdown. Use the **AUDIT LOG** button to read it and to export it.
- `app.log` is the application log.

## Uninstall

Use one of these methods:

- Open Settings > Apps > Installed apps. Select **ShutCap**. Click **Uninstall**.
- Open the Start Menu. Click **Uninstall ShutCap**.

Click the one confirmation. The uninstaller removes these items:

- The program files
- The Start Menu, Desktop, and taskbar-pin shortcuts
- The sign-in startup entry
- The Installed apps entry
- All settings, state files, and logs in `%LOCALAPPDATA%\ShutCap`

## Run from source

Requirement: Python 3.10 or newer.

1. Clone the repository:

   ```
   git clone https://github.com/ZahinArman/shutcap.git
   ```

2. Install the packages:

   ```
   pip install -r requirements.txt
   ```

3. Start the app:

   ```
   python shutcap\main.py
   ```

Command-line options:

| Option | Effect |
| --- | --- |
| `--dry-run` | Forces dry-run mode. The PC does not turn off. |
| `--live` | Forces live mode. The PC turns off. |
| `--minimized` | Starts the app in the tray. |
| `--accelerated FACTOR` | Runs a fast clock. `--accelerated 60` runs at 60 times speed. |
| `--test-mode` | Runs the test schedule. See [Test mode](#test-mode). |
| `--debug` | Writes detailed log entries. |
| `--version` | Shows the version and exits. |

## Test mode

Test mode lets you see a full night in about 60 seconds.

1. Run `run_test_mode.bat`, or run `python shutcap\main.py --test-mode --debug`.
2. Watch the warnings, the curfew dialog, and the countdown.

Test mode plays your own schedule on a fast clock. It always uses dry-run mode. It uses a temporary state folder, so it never changes the real night.

The option `--accelerated 60` also uses a temporary state folder.

## Start at sign-in by hand

The installer sets this up for you. To do it by hand, use one of these methods:

- In Settings, tick **Start ShutCap automatically when Windows boots**.
- Add a registry value in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

For the registry method, use the value name `ShutCap`. Use this data, with the path to your file:

```
"C:\path\to\ShutCap.exe" --minimized
```

## Build the installer

1. Install the packages from `requirements.txt`. The file includes PyInstaller.
2. Run `build_exe.bat`.

The script creates one file, `dist\ShutCap-Setup.exe`. The file contains the app and the uninstaller.

## Publish a release

Maintainers use one command to publish a release:

```
.\release.ps1 2.1.0 "What changed, in one line"
```

The script does these steps:

1. It stops if the working tree has changes that are not committed.
2. It sets the version in `shutcap\__init__.py` and `install.py`.
3. It makes a build environment in `.venv` and runs the tests.
4. It builds `dist\ShutCap-Setup.exe`.
5. It runs `tools\scan-secrets.ps1`. If the scan finds a key, a token, an email address, or a personal path, the script stops.
6. It commits, tags, and pushes the release.
7. It makes the GitHub release and attaches `ShutCap-Setup.exe`.

The file name is always `ShutCap-Setup.exe`. Thus this download link always gets the newest version:

```
https://github.com/ZahinArman/shutcap/releases/latest/download/ShutCap-Setup.exe
```

The script needs the GitHub CLI (`gh`). You must sign in to it first.

## Tests

Run all tests with this command:

```
python tests\run_all_tests.py
```

The test files are:

- `tests/test_no_lockout.py` checks that ShutCap never locks you out.
- `tests/test_state.py` checks the saved state and the heartbeat.
- `tests/test_scheduler.py` checks the schedule and the alerts.
- `tests/test_shutdown.py` checks the shutdown and abort commands.
- `tests/test_single_instance.py` checks that only one copy runs.
- `tests/test_notifications.py` checks the notifications.

## Code layout

Top-level files:

- `install.py` is the setup program for `ShutCap-Setup.exe`.
- `uninstall.py` is the uninstaller.
- `build_exe.bat` builds the installer.
- `release.ps1` builds and publishes a release.
- `tools/scan-secrets.ps1` checks for keys, tokens, and personal data before a release.
- `run_test_mode.bat` starts test mode.
- `requirements.txt` lists the Python packages.

Application files in `shutcap/`:

- `main.py` parses the options and starts the app.
- `config.py` reads and writes the settings and calculates the times.
- `scheduler.py` decides when each alert and the shutdown occur.
- `state.py` saves the state of the night and the heartbeat.
- `shutdown.py` runs the shutdown and abort commands.
- `notifications.py` sends toast, sound, and push alerts.
- `autostart.py` sets the start at sign-in.
- `single_instance.py` allows only one running copy.
- `time_provider.py` gives the real clock or the fast test clock.
- `logger.py` writes the app log and the audit log.

User interface files in `shutcap/ui/`:

- `main_window.py` is the dashboard.
- `setup_wizard.py` is the two-step first-run window.
- `settings_dialog.py` is the Settings window.
- `curfew_dialog.py` is the emergency question dialog.
- `emergency_dialog.py` collects the emergency reason.
- `countdown_widget.py` is the floating countdown window.
- `warning_dialog.py` is the topmost warning pop-up.
- `audit_dialog.py` is the audit log viewer.
- `tray.py` is the tray icon and menu.
- `theme.py` sets the colors and fonts.

## Limitations

- ShutCap uses the Windows clock. If you change the clock, the schedule can move.
- An app with unsaved work can delay the shutdown, because ShutCap does not use `/f`.
- ShutCap is a self-discipline tool. It cannot stop the power button. It cannot stop a person who closes the app.
- Group policy can block the shutdown command.

## License

ShutCap uses the MIT license. See the file [LICENSE](LICENSE).
