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
from shutcap.single_instance import SingleInstance, listen_for_show, signal_running_instance
from shutcap.state import CurfewStatus, StateManager
from shutcap.time_provider import RealTimeProvider, TimeProvider, VirtualTimeProvider
from shutcap.ui.tray import SystemTray
from shutcap.ui.webapp import Core, WebUI


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
    # Test mode and fast clocks run beside the real app, so they use their own lock.
    simulated = args.test_mode or args.accelerated > 0
    single_instance = SingleInstance("Local\\ShutCap_App_SingleInstance_Mutex_Sim") if simulated else SingleInstance()
    if simulated:
        single_instance.lock_file = single_instance.lock_file.with_name("app-sim.pid")
    if not single_instance.check_or_acquire():
        # No pop-up: the running copy opens its window instead.
        logging.info("ShutCap is already running. Asking it to show its window.")
        if not args.minimized and not simulated:
            signal_running_instance()
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

        # 6. User interface (pywebview) and tray
        core = Core(config_mgr, state_mgr, scheduler, audit_logger, time_provider, notifications, simulated)

        def _status_text() -> str:
            cfg = config_mgr.config
            status = scheduler.tonight_status(time_provider.now())
            if status in (CurfewStatus.EMERGENCY_EXCEPTION, CurfewStatus.SHUTDOWN_CANCELLED,
                          CurfewStatus.SKIPPED, CurfewStatus.MISSED):
                return "Off tonight"
            text = f"Off at {cfg.shutdown_time}"
            return f"{text} · Practice" if cfg.dry_run else text

        def _quit() -> None:
            audit_logger.log("APP_EXIT", "ShutCap was closed from the tray menu.", dt=time_provider.now())
            ui.quit()

        tray = SystemTray(
            status_text=_status_text,
            on_open=lambda: ui.show_main(),
            on_settings=lambda: ui.show_main("settings"),
            on_history=lambda: ui.show_main("history"),
            on_quit=_quit,
        )
        ui = WebUI(core, start_hidden=args.minimized, on_quit=lambda: None)
        if not simulated:
            listen_for_show(lambda: ui.show_main())
        tray.start()
        ui.run()

    finally:
        logging.info("ShutCap shutting down cleanly.")
        if "tray" in locals():
            tray.stop()
        single_instance.release()


if __name__ == "__main__":
    main()
