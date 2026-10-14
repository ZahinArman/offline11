"""
Main entry point for OFFLINE 11.
Wires together configuration, state persistence, single-instance mutex,
notification dispatch, scheduling engine, UI dashboard, and system tray.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is in sys.path regardless of how script was invoked
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from offline11 import __app_name__, __version__
from offline11.config import Config, ConfigManager
from offline11.logger import AuditLogger, setup_app_logging
from offline11.notifications import NotificationManager
from offline11.scheduler import Scheduler
from offline11.shutdown import ShutdownManager
from offline11.single_instance import SingleInstance
from offline11.state import CurfewStatus, StateManager
from offline11.time_provider import RealTimeProvider, TimeProvider, VirtualTimeProvider
from offline11.ui.main_window import MainWindow
from offline11.ui.tray import SystemTray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="OFFLINE 11",
        description="A Strict PC Curfew Utility for Windows.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force safe dry-run mode (simulates shutdown without turning off PC).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force live enforcement mode (executes real shutdown commands at curfew).",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized directly to the system tray.",
    )
    parser.add_argument(
        "--accelerated",
        type=float,
        default=0.0,
        metavar="FACTOR",
        help="Run with an accelerated virtual clock (e.g. 60.0 for 1s = 1min).",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Set up an accelerated 60-second test schedule to safely verify the full curfew workflow.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable detailed debug logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{__app_name__} v{__version__}",
    )
    return parser.parse_args()


def configure_test_mode(config: Config, now: datetime) -> Config:
    """Configures a compressed schedule starting immediately for safe end-to-end testing."""
    config.dry_run = True  # Always dry-run during test mode
    # Timeline relative to current time:
    # +10s: Warning 1
    # +20s: Warning 2
    # +30s: Curfew Begins
    # +35s: Reminder 1
    # +40s: Reminder 2
    # +45s: Final warning
    # +50s: Shutdown
    t1 = (now + timedelta(seconds=10)).time()
    t2 = (now + timedelta(seconds=20)).time()
    tc = (now + timedelta(seconds=30)).time()
    tr1 = (now + timedelta(seconds=35)).time()
    tr2 = (now + timedelta(seconds=40)).time()
    tf = (now + timedelta(seconds=45)).time()
    ts = (now + timedelta(seconds=50)).time()

    config.warning_1_time = t1.strftime("%H:%M")
    config.warning_2_time = t2.strftime("%H:%M")
    config.curfew_time = tc.strftime("%H:%M")
    config.grace_reminder_1_time = tr1.strftime("%H:%M")
    config.grace_reminder_2_time = tr2.strftime("%H:%M")
    config.final_warning_time = tf.strftime("%H:%M")
    config.shutdown_time = ts.strftime("%H:%M")
    return config


def main() -> None:
    args = parse_args()

    # 1. Setup logging
    setup_app_logging(debug=args.debug)
    logging.info(f"Starting {__app_name__} v{__version__}")

    # 2. Enforce single instance
    single_instance = SingleInstance()
    if not single_instance.check_or_acquire():
        logging.warning("Duplicate instance detected. Exiting.")
        # If run interactively, show quick message box
        if not args.minimized:
            try:
                root = tk.Tk()
                root.withdraw()
                from tkinter import messagebox
                messagebox.showwarning(
                    "Already Running",
                    "OFFLINE 11 is already running in the background.\n"
                    "Check the system tray icon near your taskbar clock.",
                )
                root.destroy()
            except Exception:
                pass
        sys.exit(0)

    try:
        # 3. Load Configuration
        config_mgr = ConfigManager()
        if args.dry_run:
            config_mgr.config.dry_run = True
        elif args.live:
            config_mgr.config.dry_run = False

        # 4. Clock and Time Provider
        time_provider: TimeProvider
        if args.accelerated > 0:
            time_provider = VirtualTimeProvider(acceleration_factor=args.accelerated)
        else:
            time_provider = RealTimeProvider()

        if args.test_mode:
            now_dt = time_provider.now()
            config_mgr.config = configure_test_mode(config_mgr.config, now_dt)
            logging.info("SAFE TEST MODE activated with 60-second compressed schedule.")

        # 5. Core Services
        audit_logger = AuditLogger()
        state_mgr = StateManager()
        shutdown_mgr = ShutdownManager(dry_run=config_mgr.config.dry_run)
        notifications = NotificationManager(config_mgr.config)

        # Log startup
        audit_logger.log(
            "STARTUP",
            f"OFFLINE 11 v{__version__} started.",
            {"dry_run": config_mgr.config.dry_run, "curfew": config_mgr.config.curfew_time},
            dt=time_provider.now(),
        )

        scheduler = Scheduler(
            config=config_mgr.config,
            state_mgr=state_mgr,
            time_provider=time_provider,
            audit_logger=audit_logger,
            shutdown_mgr=shutdown_mgr,
        )

        # 6. Build GUI Dashboard (wires scheduler milestones, popups, and notification alerts)
        main_window = MainWindow(
            config_mgr=config_mgr,
            state_mgr=state_mgr,
            scheduler=scheduler,
            audit_logger=audit_logger,
            time_provider=time_provider,
            notifications=notifications,
        )

        # 8. Setup System Tray
        def _show_gui() -> None:
            main_window.after(0, main_window.show_from_tray)

        def _open_settings() -> None:
            main_window.after(0, lambda: (main_window.show_from_tray(), main_window._open_settings()))

        def _open_audit() -> None:
            main_window.after(0, lambda: (main_window.show_from_tray(), main_window._open_audit()))

        def _exit_app() -> None:
            main_window.after(0, main_window.destroy)

        tray = SystemTray(
            config_mgr=config_mgr,
            state_mgr=state_mgr,
            on_show_window=_show_gui,
            on_open_settings=_open_settings,
            on_open_audit=_open_audit,
            on_exit_app=_exit_app,
        )
        tray.start()

        # Connect window hide callback to tray
        main_window.on_hide_to_tray = lambda: None

        # Start minimized if requested
        if args.minimized:
            main_window.withdraw()

        # 9. Main Periodic Tick Loop (runs every 1000ms)
        def _tick_loop() -> None:
            try:
                scheduler.tick()
                main_window._update_display()
            except Exception as e:
                logging.error(f"Error during scheduler tick: {e}", exc_info=True)
            finally:
                main_window.after(1000, _tick_loop)

        # Schedule initial tick
        main_window.after(200, _tick_loop)

        # Start GUI main loop
        main_window.mainloop()

    finally:
        logging.info("OFFLINE 11 shutting down cleanly.")
        if "tray" in locals():
            tray.stop()
        single_instance.release()


if __name__ == "__main__":
    main()
