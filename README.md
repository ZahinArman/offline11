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
4. At the curfew, ShutCap shows the curfew window and a countdown.
5. At the turn-off time, ShutCap runs `shutdown.exe /s /t 60`.
6. Windows gives your apps 60 seconds, then the PC turns off.

ShutCap does not use `/f`. Windows does not force apps to close.

ShutCap has no telemetry, no accounts, and no cloud service.

## Install

Requirements: Windows 10 or Windows 11 with Microsoft Edge WebView2. Windows 11 includes WebView2. You do not need administrator rights.

1. Open the [Releases](https://github.com/ZahinArman/shutcap/releases) page.
2. Download `ShutCap-Setup.exe`.
3. Double-click the file.
4. To use a different folder, click **Change…** and select a folder.
5. Click **Install**.

The setup program does these tasks:

- It installs ShutCap to the folder that you choose. The default is `%LOCALAPPDATA%\Programs\ShutCap`. ShutCap always uses its own `ShutCap` folder. Setup does not install into a folder that has other files in it.
- It adds Start Menu and Desktop shortcuts.
- It adds **Uninstall ShutCap** to the Start Menu.
- It adds ShutCap to Settings > Apps > Installed apps.
- If **Start with Windows** is on, it sets ShutCap to start at sign-in, minimized to the tray.
- It starts ShutCap.

To upgrade, run a newer setup file. The upgrade uses the same folder and keeps your settings.

> **NOTE:** The setup file is not code-signed. Windows SmartScreen can show a warning. Click **More info**, then click **Run anyway**.

## First-time setup

On the first start, ShutCap shows two steps in its window.

**Step 1: Shutdown time.**

1. Drag the dot around the dial to set the time. You can also use the mouse wheel or the arrow keys. Shift+arrow changes the hour.
2. Click **Next**.

**Step 2: Your evening.** Step 2 shows three times. You can edit the first warning and the curfew.

| Event | Default time |
| --- | --- |
| First warning | 45 minutes before turn-off |
| Curfew (curfew window and countdown) | 15 minutes before turn-off |
| Off | Your chosen time |

ShutCap adds the other alerts for you:

| Event | Time |
| --- | --- |
| Last warning | 10 minutes before the curfew |
| Reminder | 10 minutes before turn-off |
| Reminder | 5 minutes before turn-off |
| Last minute | 1 minute before turn-off |

If the gaps are shorter, ShutCap spreads these alerts evenly. You can change all seven times later in Settings.

If a time is out of order, ShutCap marks that row in red and you cannot click **Finish**.

Step 2 also has the **Practice mode** switch. It is on by default. In practice mode, ShutCap shows the warnings but does not turn off the PC.

Click **Finish** to save the schedule. A schedule can cross midnight, for example turn-off at 00:30.

## Daily use

ShutCap runs in the system tray. Click the tray icon to open the window.

The window shows tonight's shutdown time in a ring. The ring fills as the time comes near. Under the ring are the warning, curfew, and off times.

- The clock icon opens **History**.
- The gear icon opens **Settings**.
- The close button hides the window. ShutCap continues to run in the tray. To stop ShutCap, right-click the tray icon and click **Quit ShutCap**.

ShutCap allows only one running copy. If you start it again, the running copy opens its window.

## The curfew

ShutCap has a small number of alerts, and they all look the same:

- **Warnings.** A small card shows at the top-right of the screen. It does not take the keyboard focus. It closes after 30 seconds.
- **Curfew.** A window shows "Time to stop." and the turn-off time. Click **OK**. If you ignore the window, the shutdown continues.
- **Countdown.** After the curfew, a small countdown shows at the top-right. The reminders do not open new windows. They play a sound and send a phone alert. The countdown turns red in the last minute.

To cancel tonight, use one of these methods:

1. **Emergency.** Click **I have an emergency** in the curfew window, or **Emergency** in the countdown. Write a reason. Click **Cancel tonight's shutdown**. ShutCap writes the reason to History.
2. **Cancel.** In the ShutCap window, click **Cancel shutdown**. Confirm. ShutCap runs `shutdown /a` and writes the event to History.

To turn the curfew on again after a cancel, click **Turn back on** in the ShutCap window.

To stop a shutdown by hand:

1. Press Win+R.
2. Type `shutdown /a`.
3. Press Enter.

If Windows refuses the shutdown command, ShutCap shows "The PC did not turn off". Click **Try again**, or save your work and turn off the PC.

## Safety rules

ShutCap follows these rules. The code in `shutcap/scheduler.py` and the test file `tests/test_no_lockout.py` enforce them.

- ShutCap enforces the turn-off at most once each night.
- If the PC starts, restarts, or wakes from sleep after the curfew started, ShutCap does nothing that night. It shows no curfew, no countdown, and no warning.
- ShutCap saves a heartbeat every 10 seconds. If the heartbeat is older than 60 seconds, ShutCap knows that the PC was off or asleep.
- If you restart the app while the PC stays on, the countdown continues.
- ShutCap shows no old pop-ups the next morning.
- An alert never repeats after a restart. If several alerts are late at the same time, ShutCap shows only the most recent alert.
- When the night window ends, ShutCap closes unfinished nights without a message.

## Settings

Open Settings from the gear icon or the tray menu. ShutCap saves each change immediately. There is no Save button.

In Settings you can:

- Change the turn-off time and all warning times. **Reset** sets the default times again.
- Turn sound on or off.
- Set up phone alerts.
- Turn practice mode on or off. Before practice mode goes off, ShutCap asks you to confirm.
- Turn **Start with Windows** on or off.
- Show a test warning or the curfew window. The test does not change tonight.

## Notifications

ShutCap uses these alerts:

- The warning card, the curfew window, and the countdown
- Warning sounds
- Optional phone alerts through [ntfy.sh](https://ntfy.sh)

ShutCap does not also show Windows toast messages for these alerts. You see one alert, not two.

To use phone alerts:

1. Install the ntfy app on your phone.
2. In Settings, turn on **Phone alerts**.
3. Enter a private topic name.
4. In the ntfy app, subscribe to the same topic.

> **NOTE:** Anyone who knows your topic name can read your messages. Use a long topic name that others cannot guess.

### Logs

ShutCap keeps its files in `%LOCALAPPDATA%\ShutCap`:

- `audit.log` records each warning, decision, emergency, abort, and shutdown. Open **History** to read it. Click **Export** to save it as a text file.
- `app.log` is the application log.

## Uninstall

Use one of these methods:

- Open Settings > Apps > Installed apps. Select **ShutCap**. Click **Uninstall**.
- Open the Start Menu. Click **Uninstall ShutCap**.

Click **Remove**. The uninstaller removes these items:

- The program files
- The Start Menu, Desktop, and taskbar-pin shortcuts
- The sign-in startup entry
- The Installed apps entry
- All settings, state files, and logs in `%LOCALAPPDATA%\ShutCap`. To keep them, turn on **Keep my settings and history** before you click **Remove**.

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
2. Watch the warnings, the curfew window, and the countdown.

Test mode plays your own schedule on a fast clock. It always uses dry-run mode. It uses a temporary state folder, so it never changes the real night.

The option `--accelerated 60` also uses a temporary state folder.

## Start at sign-in by hand

The installer sets this up for you. To do it by hand, use one of these methods:

- In Settings, turn on **Start with Windows**.
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

- `webapp.py` opens the windows and connects them to the scheduler.
- `setup_window.py` is the window for the installer and the uninstaller.
- `tray.py` is the tray icon and menu.
- `web/base.css` is the design system. All windows use it.
- `web/app.html` and `web/app.js` are the main window: setup, home, Settings, and History.
- `web/alert.html` and `web/alert.js` are the alerts: warning, curfew, emergency, countdown.
- `web/setup.html` is the installer and uninstaller page.

## Limitations

- ShutCap uses the Windows clock. If you change the clock, the schedule can move.
- An app with unsaved work can delay the shutdown, because ShutCap does not use `/f`.
- ShutCap is a self-discipline tool. It cannot stop the power button. It cannot stop a person who closes the app.
- Group policy can block the shutdown command.

## License

ShutCap uses the MIT license. See the file [LICENSE](LICENSE).
