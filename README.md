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
1. **Absolute Simplicity**: Single mission: guarantee the computer powers off at 11:15 PM every night.
2. **Hard to Casually Bypass**: Prominent topmost modal prompts, persistent floating grace-period countdowns, and real Windows shutdown triggers.
3. **Respect for Sleep & Autonomy**: Distinguishes between mindless procrastination (gaming, late-night browsing) and genuine emergencies (medical, critical server outages). Emergency exceptions require written rationale and accountability confirmation.
4. **Zero Nagging After Curfew**: Once tonight's curfew is resolved (either via shutdown or confirmed emergency), it **never** triggers another shutdown or nags you if you turn the PC back on later that night or at 12:00 AM. It resets strictly at 10:30 PM the following day.
5. **No Telemetry, No Accounts, No Cloud**: 100% offline, local JSON state, zero tracking.

---

## Table of Contents

1. [Key Features & Design Philosophy](#key-features--design-philosophy)
2. [Schedule & Enforcement Timeline](#schedule--enforcement-timeline)
3. [The Critical Requirement: Single Enforcement Per Session Date](#the-critical-requirement-single-enforcement-per-session-date)
4. [Architecture & Code Structure](#architecture--code-structure)
5. [Installation & Requirements](#installation--requirements)
6. [Running the Application](#running-the-application)
7. [Safe Testing Modes](#safe-testing-modes)
8. [Windows Auto-Startup Setup](#windows-auto-startup-setup)
9. [Optional Android Push Notifications (ntfy.sh)](#optional-android-push-notifications-ntfysh)
10. [Safety & Emergency Recovery Procedure](#safety--emergency-recovery-procedure)
11. [Packaging as Windows Standalone Executable](#packaging-as-windows-standalone-executable)
12. [Automated Verification & Test Suite](#automated-verification--test-suite)
13. [Documented Limitations & Technical Trade-offs](#documented-limitations--technical-trade-offs)

---

## Key Features & Design Philosophy

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
> 2. Edit any milestone in standard 24-hour `HH:MM` format (e.g., set Curfew to `22:00` for 10:00 PM, `00:00` for midnight, or any custom target).
> 3. Click **SAVE SETTINGS**. The app automatically validates that your warnings and shutdown are properly sequenced.

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

## The Critical Requirement: Single Enforcement Per Session Date

### The Golden Rule
> **The curfew must be enforced only once per calendar day. A completed shutdown must never trigger another shutdown when turning the computer back on later that night.**

### How OFFLINE 11 Solves This:
1. **Reference Session Date**:
   - The curfew cycle is keyed by the calendar date on which the 10:30 PM warning begins (e.g. `2026-10-14`).
   - Any time between 11:15 PM on day $D$ and 10:30 PM on day $D+1$ belongs to the reference session of day $D$.
2. **Permanent Resolution**:
   - When Windows executes shutdown at 11:15 PM, state transitions to `SHUTDOWN_COMPLETED`.
   - When the PC turns back on at **12:00 AM (midnight)**, the app detects that session `2026-10-14` is **permanently resolved**.
   - **No dialog is shown, no countdown is restarted, and no shutdown is scheduled.**
   - The PC operates normally throughout the morning and afternoon.
3. **Daily Reset**:
   - The state only resets when the next session arrives at **10:30 PM on the following day**.

### Mandatory Acceptance Test Scenario:
1. At **11:00 PM**, curfew dialog appears.
2. User selects **NO EMERGENCY**.
3. At **11:15 PM**, computer shuts down cleanly.
4. User turns it back on at **12:00 AM**.
5. The application starts normally without another curfew dialog or countdown.
6. User continues using PC normally throughout the day.
7. At **10:30 PM the following day**, the next curfew session begins as usual.

*(Verified and covered by unit test `test_critical_acceptance_requirement_no_reshutdown_after_midnight` in `tests/test_state.py`.)*

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
│   ├── test_scheduler.py     # Timeline milestones, deduplication, time jumps
│   ├── test_shutdown.py      # Shutdown commands, dry-run, cancellation syntax
│   ├── test_single_instance.py # Win32 Mutex duplicate prevention
│   ├── test_notifications.py # Toast fallback, audio dispatch, push threading
│   └── run_all_tests.py      # Comprehensive test suite runner
├── assets/
│   ├── icon.ico              # Windows application icon
│   └── icon.png              # High-resolution application logo
├── build_exe.bat             # Compiles standalone Windows executable with PyInstaller
├── build_exe.ps1             # PowerShell script to compile standalone executable
├── install_autostart.bat     # Helper script to enable auto-startup on Windows boot
├── run_test_mode.bat         # Safe 60-second accelerated simulation launcher
└── requirements.txt          # Python dependencies
```

---

## Installation & Requirements

### System Requirements
- **OS**: Windows 10 or Windows 11 (64-bit recommended)
- **Python**: Python 3.10 or later

### Setup Instructions
1. Clone or copy the project repository to your desired folder:
   ```cmd
   cd d:\11ofDeath
   ```
2. Install Python dependencies:
   ```cmd
   pip install -r requirements.txt
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
This compresses the entire curfew sequence into a safe **60-second cycle**:
- **+10s**: 30-minute warning toast
- **+20s**: 10-minute warning toast
- **+30s**: 11:00 PM Curfew modal appears (`NO EMERGENCY` vs `GENUINE EMERGENCY`)
- **+35s**: Grace reminder 1
- **+40s**: Grace reminder 2
- **+45s**: Final 1-minute warning
- **+50s**: Dry-run simulated shutdown (PC remains on)

### 2. Accelerated Virtual Clock
Simulate hours passing in seconds using the `--accelerated` flag:
```cmd
python offline11\main.py --accelerated 60 --dry-run
```
*(At 60x speed, 1 real second = 1 virtual minute).*

---

## Windows Auto-Startup Setup

To start OFFLINE 11 automatically whenever you log into Windows:

### Method A: Via Application Settings GUI
1. Open OFFLINE 11.
2. Click **SETTINGS**.
3. Check **"Start OFFLINE 11 automatically when Windows boots"**.
4. Click **SAVE SETTINGS**.

### Method B: Via Helper Script
Double-click:
```cmd
install_autostart.bat
```

### Method C: Manual Windows Registry Entry
OFFLINE 11 uses the standard Windows startup registry key:
- **Registry Key**: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`
- **Value Name**: `OFFLINE 11`
- **Value Data**: `"C:\path\to\OFFLINE11.exe"` (or `"pythonw.exe" "d:\11ofDeath\offline11\main.py"`)

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

## Packaging as Windows Standalone Executable

To compile OFFLINE 11 into a standalone `.exe` that does not require Python to run:

### Batch Script:
Double-click:
```cmd
build_exe.bat
```

### PowerShell:
```powershell
.\build_exe.ps1
```

The resulting executable and bundled runtime files will be generated in:
```
dist\OFFLINE11\OFFLINE11.exe
```

---

## Automated Verification & Test Suite

OFFLINE 11 includes a comprehensive test suite covering all scheduling, state persistence, single-instance mutex, and shutdown logic.

Run the test suite with:
```cmd
python tests\run_all_tests.py
```

### Test Coverage Highlights:
- `test_critical_acceptance_requirement_no_reshutdown_after_midnight`: Verifies the mandatory acceptance test (11:00 PM curfew -> 11:15 PM shutdown -> 12:00 AM turn on -> no reshutdown -> normal PC usage all day -> 10:30 PM next session begins).
- `test_app_restart_during_countdown_preserves_remaining_time`: Verifies that closing or restarting the app mid-countdown resumes the exact remaining time rather than resetting to 15 minutes.
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
