"""
Notification manager for OFFLINE 11.
Supports native Windows 10/11 Action Center toasts, audio alerts,
and optional Android push notifications via ntfy.sh.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import urllib.request
from typing import Optional

try:
    import winsound
except ImportError:
    winsound = None

try:
    from windows_toasts import Toast, ToastDuration, WindowsToaster
    HAS_WINDOWS_TOASTS = True
except Exception:
    HAS_WINDOWS_TOASTS = False

from offline11.config import Config


class NotificationManager:
    """Dispatches desktop toasts, audio alerts, and push notifications."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._toaster = None
        if HAS_WINDOWS_TOASTS:
            try:
                self._toaster = WindowsToaster("OFFLINE 11")
            except Exception as e:
                logging.warning(f"Failed to initialize WindowsToaster: {e}")

    def update_config(self, config: Config) -> None:
        self.config = config

    def play_sound(self, sound_type: str = "warning") -> None:
        """Plays a system audio alert if enabled."""
        if not self.config.sound_enabled or winsound is None:
            return

        def _play() -> None:
            try:
                if sound_type == "urgent":
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                elif sound_type == "warning":
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                else:
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception as e:
                logging.debug(f"Audio playback error: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def send_toast(self, title: str, message: str, long_duration: bool = False) -> bool:
        """Sends a Windows Action Center toast notification."""
        # Try native Windows toast via windows-toasts
        if self._toaster is not None:
            try:
                toast = Toast(text_fields=[title, message])
                if long_duration:
                    toast.duration = ToastDuration.Long
                self._toaster.show_toast(toast)
                return True
            except Exception as e:
                logging.warning(f"windows-toasts failed: {e}. Trying PowerShell fallback.")

        # Fallback via PowerShell
        return self._send_powershell_toast(title, message)

    def _send_powershell_toast(self, title: str, message: str) -> bool:
        """Fallback notification via PowerShell script."""
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OFFLINE 11").Show($toast)
        """
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"PowerShell toast fallback failed: {e}")
            return False

    def send_push_notification(self, title: str, message: str, priority: str = "default", tags: str = "clock") -> None:
        """
        Sends an optional push notification to an Android device via ntfy.sh.
        Runs asynchronously in a background thread so network latency never blocks the app.
        """
        if not self.config.ntfy_enabled or not self.config.ntfy_topic.strip():
            return

        topic = self.config.ntfy_topic.strip()
        server = self.config.ntfy_server.rstrip("/")
        url = f"{server}/{topic}"

        def _send() -> None:
            try:
                headers = {
                    "Title": title.encode("utf-8"),
                    "Priority": priority,
                    "Tags": tags,
                }
                req = urllib.request.Request(
                    url,
                    data=message.encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=8) as response:
                    logging.info(f"Push notification delivered to ntfy: status {response.status}")
            except Exception as e:
                logging.warning(f"Push notification failed: {e}")

        threading.Thread(target=_send, daemon=True).start()

    def notify(self, title: str, message: str, sound_type: str = "warning", long_duration: bool = False, push_priority: str = "default", push_tags: str = "clock") -> None:
        """Unified dispatch for toast, sound, and push notification."""
        self.send_toast(title, message, long_duration=long_duration)
        self.play_sound(sound_type=sound_type)
        self.send_push_notification(title, message, priority=push_priority, tags=push_tags)
