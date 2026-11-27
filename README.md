# OFFLINE 11: A Strict PC Curfew Utility for Windows

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=flat&logo=windows)](https://github.com/ZahinArman/offline11)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python)](https://github.com/ZahinArman/offline11)
[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)](https://github.com/ZahinArman/offline11)

> **"No PC usage after 11:00 PM."**  
> A lightweight, reliable, quiet Windows utility designed to enforce personal sleep discipline without casual bypasses, cloud accounts, or distracting productivity gamification.

---

## 🎯 Purpose and Direction

Modern screen-time and focus tools have a fundamental flaw: **they are too polite.** They pop up easily-dismissed notifications, rely on browser extensions that can be turned off in two clicks, or drown you in colorful productivity dashboards and gamified streak counters that keep you looking at the screen longer.

**OFFLINE 11 is built on the opposite philosophy:**
1. **Absolute Simplicity**: Single mission: power the computer off once per night, at the time *you* choose (11:15 PM by default).
2. **Hard to Casually Bypass**: Prominent topmost modal prompts, persistent floating grace-period countdowns, and real Windows shutdown triggers.
3. **Respect for Sleep & Autonomy**: Distinguishes between mindless procrastination (gaming, late-night browsing) and genuine emergencies (medical, critical server outages). Emergency exceptions require written rationale and accountability confirmation.
4. **A Nudge, Never a Lockout**: The curfew is enforced at most once per night. If you turn the PC back on (or wake it from sleep) after curfew began, OFFLINE 11 assumes you had a good reason and leaves you alone, with no dialog, no countdown and no warning. The next cycle starts at the following evening's first warning.
5. **No Telemetry, No Accounts, No Cloud**: 100% offline, local JSON state, zero tracking.

---

## Table of Contents

1. [Key Features & Design Philosophy](#key-features--design-philosophy)
2. [Schedule & Enforcement Timeline](#schedule--enforcement-timeline)
3. [The Core Rules: Once Per Night, Never a Lockout](#the-core-rules-once-per-night-never-a-lockout)
4. [Architecture & Code Structure](#architecture--code-structure)
5. [Install & Uninstall](#installation--setup)
6. [Running the Application](#running-the-application)
7. [Safe Testing Modes](#safe-testing-modes)
8. [Windows Auto-Startup Setup](#windows-auto-startup-setup)
9. [Optional Android Push Notifications (ntfy.sh)](#optional-android-push-notifications-ntfysh)
10. [Safety & Emergency Recovery Procedure](#safety--emergency-recovery-procedure)
11. [Building the Installer](#building-the-installer)
12. [Automated Verification & Test Suite](#automated-verification--test-suite)
13. [Documented Limitations & Technical Trade-offs](#documented-limitations--technical-trade-offs)

---

## Key Features & Design Philosophy

- **One-File Installer (`OFFLINE11-Setup.exe`)**: Download, double-click, confirm. No admin rights, no zip to extract. Adds Start Menu and Desktop shortcuts, starts at sign-in, and appears in Settings > Apps.
- **Clean Uninstall**: Uninstall from Settings > Apps (or the Start Menu) and every trace is removed: program files, shortcuts, startup entry, settings and logs.
- **Customizable Schedule**: While 11:00 PM is the default curfew, every milestone time (warnings, curfew, reminders, and shutdown) can be freely customized in **Settings** to match your personal sleep schedule.
- **Self-Discipline Engine**: Built for self-restraint, not gamification. No badges, no leveling up, no analytics, no remote telemetry.
- **Dark Monochrome Aesthetic**: Restrained, high-contrast system utility aesthetic (`#121212` charcoal black palette) with zero distracting animations.
- **Topmost Curfew Enforcement**: At 11:00 PM, a prominent, always-visible modal appears requiring explicit confirmation. Ignoring the prompt never cancels curfew.
- **15-Minute Grace Period**: Countdown with reminders at 11:05 PM, 11:10 PM, and 11:14 PM to ensure files are saved cleanly.
- **Standard Windows Shutdown**: Uses native `shutdown.exe /s /t 60` with safe application closure warnings. Never uses `/f` (force-close) blindly.
- **Dry-Run Mode by Default**: Safe testing mode enabled by default so you can test all workflows without turning off your PC.
- **Single-Instance Mutex**: Native Win32 mutex prevents duplicate processes and duplicate timers.
- **Persistent State File**: Atomic JSON state tracking survives unexpected crashes, reboots, and sleep cycles.
- **Android Push Support**: Zero-overhead, privacy-first push notifications through [ntfy.sh](https://ntfy.sh).

---

## Schedule & Enforcement Timeline

> [!TIP]
> **Need a different curfew time?**  
> While the default schedule is set for an **11:00 PM curfew / 11:15 PM shutdown**, all times are completely customizable to fit your routine:
> 1. Click **SETTINGS** in the OFFLINE 11 dashboard.
> 2. Edit any milestone in standard 24-hour `HH:MM` format (e.g., set Curfew to `22:00` for 10:00 PM, or `00:00` for midnight; schedules may cross midnight).
> 3. Click **SAVE SETTINGS**. The app validates that your milestones are in order and applies the new schedule immediately (no restart needed). Warning texts follow your schedule automatically.

The default 24-hour schedule operates as follows:

| Time | Milestone | Action Taken |
| :--- | :--- | :--- |
| **10:30 PM** | First Warning | Desktop toast + optional sound: *"30 minutes until PC curfew. Finish what you're doing and start winding down."* |
| **10:50 PM** | Final Warning | Desktop toast + sound: *"10 minutes until PC curfew. Save your work and close everything."* |
| **11:00 PM** | Curfew Begins | Prominent, topmost modal dialog: *"PC TIME IS OVER. Is there a genuine emergency?"* Options: `NO EMERGENCY` or `GENUINE EMERGENCY`. Grace countdown begins. |
| **11:05 PM** | Grace Reminder 1 | Notification: *"10 minutes until PC shutdown. Save all open files."* |
| **11:10 PM** | Grace Reminder 2 | Notification: *"5 minutes until PC shutdown. Close all open applications."* |
| **11:14 PM** | Final Warning | Urgent toast & sound: *"1 minute until shutdown. Preparing system shutdown."* |
| **11:15 PM** | Scheduled Shutdown | Initiates standard Windows shutdown (`shutdown.exe /s /t 60`). |

---

## The Core Rules: Once Per Night, Never a Lockout

OFFLINE 11 is a small hiccup that tells you to stop, not a jail. These rules are enforced by the scheduler and covered by `tests/test_no_lockout.py`:

1. **Once per night.** A night's cycle (a "session") is keyed by the date of its First Warning. Once it is resolved (shutdown issued, emergency declared, countdown aborted, or skipped) nothing else happens until the next evening's First Warning.
2. **Never locked out.** If the PC is turned on, restarted, or woken from sleep *after curfew began*, that night is skipped silently. This is detected with a small heartbeat in the state file (boot time alone is unreliable because of Windows Fast Startup). A quick app restart while the PC stays on simply resumes the countdown.
3. **No stale popups.** Outside tonight's window nothing is shown. An unfinished night (e.g. you shut the PC down yourself during the grace period) is closed quietly, so there is no leftover countdown the next morning.
4. **No alert replays.** Fired milestones are saved to disk, and if several are overdue at once (app started late) only the most recent one is shown.

### Acceptance scenario
1. At curfew time, the curfew dialog appears.
2. User selects **NO EMERGENCY** (or ignores the dialog).
3. At shutdown time, the computer shuts down.
4. User turns it back on at **12:00 AM**: no dialog, no countdown, no warning.
5. User uses the PC normally all day.
6. The next evening, the cycle starts again at the First Warning.

---

## Architecture & Code Structure

The utility is structured cleanly into independent, modular components:

```
d:\11ofDeath\
├── offline11/
│   ├── __init__.py           # Package version and metadata
│   ├── config.py             # Settings, defaults, JSON serialization & validation
│   ├── state.py              # State machine, session reference tracking, atomic disk persistence
│   ├── time_provider.py      # Real clock vs virtual clock (for accelerated simulation)
│   ├── scheduler.py          # Daily timeline engine, deduplication, sleep/wake handling
│   ├── shutdown.py           # Windows shutdown execution, cancellations, dry-run safety
│   ├── notifications.py      # WinRT Action Center toasts, PowerShell fallback, audio chime, ntfy push
│   ├── single_instance.py    # Win32 named Mutex lock & PID tracker
│   ├── autostart.py          # Windows Registry auto-startup manager
│   ├── logger.py             # Audit log and diagnostic application logs
│   ├── main.py               # CLI parser and application entry point
│   └── ui/
│       ├── __init__.py
│       ├── theme.py          # Dark monochrome palette and typography
│       ├── main_window.py    # Dashboard (state badge, timer, manual abort, settings)
│       ├── curfew_dialog.py  # 11:00 PM topmost modal dialog
│       ├── emergency_dialog.py # Emergency declaration, reason input & explicit confirmation
│       ├── countdown_widget.py # Floating persistent 11:00-11:15 PM countdown banner
│       ├── settings_dialog.py# Settings editor
│       ├── audit_dialog.py   # Audit log viewer and export tool
│       └── tray.py           # System tray icon and context menu
├── tests/
│   ├── test_state.py         # State transitions, date rollover, reboot at 12:00 AM acceptance test
│   ├── test_no_lockout.py    # Once-per-night, no-lockout, no-replay and midnight-crossing rules
│   ├── test_scheduler.py     # Timeline milestones, deduplication, time jumps
│   ├── test_shutdown.py      # Shutdown commands, dry-run, cancellation syntax
│   ├── test_single_instance.py # Win32 Mutex duplicate prevention
│   ├── test_notifications.py # Toast fallback, audio dispatch, push threading
│   └── run_all_tests.py      # Comprehensive test suite runner
├── assets/
│   ├── icon.ico              # Windows application icon
│   └── icon.png              # High-resolution application logo
├── install.py                # Standalone Windows application installer script
├── uninstall.py              # Standalone 1-click uninstaller script
├── build_exe.bat             # Builds dist\OFFLINE11-Setup.exe with PyInstaller
├── run_test_mode.bat         # Safe 60-second accelerated simulation launcher
└── requirements.txt          # Python dependencies
```

---

## Installation & Setup

### Install (recommended)

1. Download **`OFFLINE11-Setup.exe`** from the [GitHub Releases](https://github.com/ZahinArman/offline11/releases) page.
2. Double-click it and click **Yes**.

That's it. OFFLINE 11 is installed for your Windows user (no admin rights needed), starts right away, and starts automatically every time you sign in. You'll find it in the Start Menu, on your Desktop, and as an icon near the clock.

It starts in safe **Dry-Run** mode: everything works except the actual power-off. When you're happy with your schedule, untick Dry-Run in **Settings** to enable real shutdowns.

To update, just run a newer `OFFLINE11-Setup.exe`. Your settings and history are kept.

> Windows SmartScreen may warn about an unrecognized app because the installer isn't code-signed. Click **More info → Run anyway**.

### Uninstall

Use any of these:
- **Settings > Apps > Installed apps** → **OFFLINE 11** → **Uninstall**
- Start Menu → **Uninstall OFFLINE 11**

After one confirmation, everything is removed:
- Program files (`%LOCALAPPDATA%\Programs\OFFLINE 11`)
- Start Menu, Desktop and pinned-taskbar shortcuts
- The sign-in startup entry and the Installed apps entry
- All settings, state and logs (`%LOCALAPPDATA%\OFFLINE11`)

---

### Running from Source (Python 3.10+)

```cmd
git clone https://github.com/ZahinArman/offline11.git
cd offline11
pip install -r requirements.txt
python offline11\main.py
```

---

## Running the Application

### 1. Interactive Run (Default GUI Mode)
```cmd
python offline11\main.py
```
This opens the OFFLINE 11 dashboard and places an icon in the Windows system tray.

### 2. Run in Safe Dry-Run Mode
```cmd
python offline11\main.py --dry-run
```
*(Shutdowns are simulated and logged to the audit log; Windows will not power off.)*

### 3. Run in Live Enforcement Mode
```cmd
python offline11\main.py --live
```
*(Warning: issues real Windows shutdown commands when the curfew grace period expires.)*

### 4. Run Minimized in Background (System Tray Only)
```cmd
python offline11\main.py --minimized
```

---

## Safe Testing Modes

### 1. One-Click Safe 60-Second Demo
Run the included batch script:
```cmd
run_test_mode.bat
```
Or via CLI:
```cmd
python offline11\main.py --test-mode --debug
```
This replays **your configured schedule** on a fast virtual clock, so the whole night (first warning to dry-run shutdown) takes about 60 seconds. Test mode always runs in dry-run and uses a throwaway state folder, so it can never affect tonight's real curfew.

The **TEST CURFEW** button on the dashboard only previews the curfew dialog. It never schedules anything.

### 2. Accelerated Virtual Clock
Simulate hours passing in seconds using the `--accelerated` flag:
```cmd
python offline11\main.py --accelerated 60 --dry-run
```
*(At 60x speed, 1 real second = 1 virtual minute. Uses a throwaway state folder.)*

---

## Windows Auto-Startup Setup

To start OFFLINE 11 automatically whenever you log into Windows:

### Method A: Via Application Settings GUI
1. Open OFFLINE 11.
2. Click **SETTINGS**.
3. Check **"Start OFFLINE 11 automatically when Windows boots"**.
4. Click **SAVE SETTINGS**.

### Method B: Manual Windows Registry Entry
OFFLINE 11 uses the standard Windows startup registry key:
- **Registry Key**: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
- **Value Name**: `OFFLINE 11`
- **Value Data**: `"C:\path\to\OFFLINE11.exe" --minimized` (or `"pythonw.exe" "C:\path\to\offline11\main.py" --minimized`)

---

## Optional Android Push Notifications (ntfy.sh)

If you want your phone to alert you alongside your PC:

1. Install the free, open-source **ntfy** app from Google Play or F-Droid on your Android phone.
2. Open the app and tap **Subscribe to topic**.
3. Pick a private, unique topic name (e.g. `offline11_john_8391`).
4. In OFFLINE 11, click **SETTINGS**:
   - Check **Android Push**.
   - Enter your topic name (`offline11_john_8391`).
   - Click **SAVE SETTINGS**.
5. Your phone will receive instant push notifications with alert sounds at:
   - 10:30 PM (Warning 1)
   - 10:50 PM (Final Warning)
   - 11:00 PM (Curfew Alert)
   - 11:15 PM (Shutdown Notice)
   - Emergency Declarations

*No accounts, passwords, or emails required.*

---

## Safety & Emergency Recovery Procedure

### 1. Documented Recovery Command
If a shutdown has been scheduled and you must abort it from Windows command line or the Run prompt:
1. Press `Win + R` on your keyboard.
2. Type:
   ```cmd
   shutdown /a
   ```
3. Press `Enter`. Windows will immediately abort the pending shutdown.

### 2. GUI Emergency Abort Button
During the 11:00 PM – 11:15 PM grace period, the OFFLINE 11 dashboard displays a high-contrast **"ABORT PENDING SHUTDOWN"** button. Clicking it:
- Prompts for confirmation.
- Executes `shutdown /a`.
- Updates the state to `SHUTDOWN_CANCELLED`.
- Permanently logs the manual cancellation with timestamp to `%LOCALAPPDATA%\OFFLINE11\audit.log`.

### 3. Genuine Emergency Exception Dialog
If you click `GENUINE EMERGENCY` on the curfew modal:
- You are prompted to provide a short reason.
- You must check the self-discipline accountability confirmation box.
- Tonight's curfew is permanently cancelled.
- Normal curfew will resume automatically at 10:30 PM tomorrow.

---

## Building the Installer

Requires Python with the packages in `requirements.txt` (includes PyInstaller). Double-click or run:

```cmd
build_exe.bat
```

The result is a single file, **`dist\OFFLINE11-Setup.exe`**, which carries the app and its uninstaller inside it. Upload that one file to a GitHub Release.

---

## Automated Verification & Test Suite

OFFLINE 11 includes a comprehensive test suite covering all scheduling, state persistence, single-instance mutex, and shutdown logic.

Run the test suite with:
```cmd
python tests\run_all_tests.py
```

### Test Coverage Highlights:
- `test_critical_acceptance_requirement_no_reshutdown_after_midnight`: Verifies the mandatory acceptance test (11:00 PM curfew -> 11:15 PM shutdown -> 12:00 AM turn on -> no reshutdown -> normal PC usage all day -> 10:30 PM next session begins).
- `test_app_restart_during_countdown_preserves_remaining_time`: Verifies that a quick app restart (PC still on) resumes the exact remaining time rather than resetting it.
- `tests/test_no_lockout.py`: No popup the morning after, no lockout after turning the PC back on or waking it, no alert replay after restarts, abort survives restarts, settings apply live, midnight-crossing schedules.
- `test_ignored_curfew_dialog_still_shuts_down_at_11_15`: Verifies that ignoring the dialog still enforces the 11:15 PM shutdown.
- `test_emergency_exception_cancels_shutdown`: Verifies emergency declaration cancels shutdown for the night.
- `test_single_instance_acquisition_and_duplicate_rejection`: Verifies duplicate instances are blocked via Win32 named Mutex.
- `test_dry_run_mode_never_executes_system_shutdown`: Verifies safety mode never touches system power.

---

## Documented Limitations & Technical Trade-offs

1. **User Privileges**: Standard users can execute `shutdown.exe /s /t <sec>`. However, running in restricted enterprise domains with strict Group Policies (GPO) disabling shutdown may block execution; OFFLINE 11 detects this and reports `SHUTDOWN_FAILED`.
2. **Blocking Applications**: Some Windows applications (e.g. unsaved Notepad, Word documents, or modal dialogs) may prompt the user during shutdown. Windows gives applications up to the grace period (`/t 60`) to save. OFFLINE 11 deliberately avoids `/f` (force-close) to protect user data from silent loss.
3. **BIOS / CMOS Clock Tampering**: As a userland utility, OFFLINE 11 relies on the Windows local system clock. Changing system time manually in Windows Settings can shift schedule calculations. OFFLINE 11 logs all significant time jumps to the audit trail.
4. **Physical Power Access**: This utility is a software self-discipline tool designed to remove mindless, late-night drifting. It cannot and does not lock the physical hardware power button or prevent hardware-level restarts.
