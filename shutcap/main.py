"""
Main entry point for ShutCap.
Wires together configuration, state persistence, single-instance mutex,
notification dispatch, scheduling engine, UI dashboard, and system tray.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is in sys.path regardless of how script was invoked
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from shutcap import __app_name__, __version__
from shutcap.config import Config, ConfigManager
from shutcap.logger import AuditLogger, setup_app_logging
from shutcap.notifications import NotificationManager
from shutcap.scheduler import Scheduler
from shutcap.shutdown import ShutdownManager
from shutcap.single_instance import SingleInstance
from shutcap.state import CurfewStatus, StateManager
from shutcap.time_provider import RealTimeProvider, TimeProvider, VirtualTimeProvider
from shutcap.ui.main_window import MainWindow
from shutcap.ui.setup_wizard import SetupWizard
from shutcap.ui.tray import SystemTray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ShutCap",
        description="Turns your Windows PC off once per night, at the time you choose.",
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


def make_test_clock(config: Config, now: datetime) -> VirtualTimeProvider:
    """
    Test mode: plays YOUR configured schedule on a fast virtual clock so the whole night
    (first warning -> shutdown) takes about 60 seconds of real time.
    """
    offsets = {key: off for key, _, off in config.milestone_offsets()}
    span_seconds = offsets["shutdown"] * 60
    w1 = config.get_time_obj("warning_1_time")
    factor = max(1.0, span_seconds / 50.0)  # whole schedule plays in ~50 real seconds
    first_warning = datetime.combine(now.date(), w1, tzinfo=now.tzinfo)
    start = first_warning - timedelta(seconds=10 * factor)  # ~10 real seconds of lead-in
    return VirtualTimeProvider(initial_dt=start, acceleration_factor=factor, running=True)


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
                    "ShutCap is already running in the background.\n"
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
        simulated = args.test_mode or args.accelerated > 0
        if args.test_mode:
            config_mgr.config.dry_run = True  # never shut down for real in test mode
            time_provider = make_test_clock(config_mgr.config, datetime.now().astimezone())
            logging.info("SAFE TEST MODE: replaying your schedule in about 60 seconds.")
        elif args.accelerated > 0:
            time_provider = VirtualTimeProvider(acceleration_factor=args.accelerated, running=True)
        else:
            time_provider = RealTimeProvider()

        # 5. Core Services
        # Simulated clocks use a throwaway state/audit folder so they can never affect the real night.
        if simulated:
            sim_dir = Path(tempfile.mkdtemp(prefix="shutcap_sim_"))
            audit_logger = AuditLogger(log_path=sim_dir / "audit.log")
            state_mgr = StateManager(state_file=sim_dir / "state.json")
        else:
            audit_logger = AuditLogger()
            state_mgr = StateManager()
        shutdown_mgr = ShutdownManager(dry_run=config_mgr.config.dry_run)
        notifications = NotificationManager(config_mgr.config)

        # Log startup
        audit_logger.log(
            "STARTUP",
            f"ShutCap v{__version__} started.",
            {"dry_run": config_mgr.config.dry_run, "curfew": config_mgr.config.curfew_time},
            dt=time_provider.now(),
        )

        scheduler = Scheduler(
            config=config_mgr.config,
            state_mgr=state_mgr,
            time_provider=time_provider,
            audit_logger=audit_logger,
            shutdown_mgr=shutdown_mgr,
            detect_resume=not simulated,
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
            audit_logger.log("APP_EXIT", "ShutCap was exited from the tray menu.", dt=time_provider.now())
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

        # 9. Main Periodic Tick Loop (runs every 1000ms)
        def _tick_loop() -> None:
            try:
                scheduler.tick()
                main_window._update_display()
            except Exception as e:
                logging.error(f"Error during scheduler tick: {e}", exc_info=True)
            finally:
                main_window.after(1000, _tick_loop)

        if not config_mgr.config.setup_complete and not simulated:
            # First run: ask for the shutdown time before anything is scheduled.
            main_window.withdraw()

            def _setup_done(new_config: Config) -> None:
                main_window._on_settings_saved(new_config)
                main_window.show_from_tray()
                main_window.after(200, _tick_loop)

            SetupWizard(main_window, config_mgr, on_done=_setup_done)
        else:
            if args.minimized:
                main_window.withdraw()
            main_window.after(200, _tick_loop)

        # Start GUI main loop
        main_window.mainloop()

    finally:
        logging.info("ShutCap shutting down cleanly.")
        if "tray" in locals():
            tray.stop()
        single_instance.release()


if __name__ == "__main__":
    main()
