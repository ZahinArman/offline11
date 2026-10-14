"""
Unit tests for OFFLINE 11 Notifications module.
Verifies Windows toast fallback, audio dispatch, and ntfy push notification threading.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from offline11.config import Config
from offline11.notifications import NotificationManager


class TestNotificationManager(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(sound_enabled=True, ntfy_enabled=True, ntfy_topic="test_topic")
        self.mgr = NotificationManager(self.config)

    def test_toast_fallback_when_winrt_unavailable(self) -> None:
        """Verifies that PowerShell fallback is triggered when WindowsToaster fails."""
        self.mgr._toaster = None
        with patch.object(self.mgr, "_send_powershell_toast") as mock_ps:
            mock_ps.return_value = True
            result = self.mgr.send_toast("Title", "Message")
            self.assertTrue(result)
            mock_ps.assert_called_once_with("Title", "Message")

    def test_push_notification_does_not_block_and_dispatches_http(self) -> None:
        """Verifies ntfy push notification sends HTTP POST in background thread without blocking."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            self.mgr.send_push_notification("Curfew Warning", "10 minutes left", priority="high", tags="warning")

            # Allow brief moment for daemon thread to execute
            import time
            time.sleep(0.1)

            self.assertTrue(mock_urlopen.called)
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://ntfy.sh/test_topic")
            self.assertEqual(req.get_method(), "POST")

    def test_audio_sound_dispatch(self) -> None:
        """Verifies audio chime dispatches without raising exceptions."""
        with patch("winsound.MessageBeep") as mock_beep:
            self.mgr.play_sound("warning")
            import time
            time.sleep(0.1)
            self.assertTrue(mock_beep.called)

    def test_notify_unified_dispatch(self) -> None:
        """Verifies notify() invokes send_toast, play_sound, and send_push_notification."""
        with patch.object(self.mgr, "send_toast") as mock_toast, \
             patch.object(self.mgr, "play_sound") as mock_sound, \
             patch.object(self.mgr, "send_push_notification") as mock_push:
            self.mgr.notify("Title", "Message", sound_type="urgent")
            mock_toast.assert_called_once_with("Title", "Message", long_duration=False)
            mock_sound.assert_called_once_with(sound_type="urgent")
            mock_push.assert_called_once_with("Title", "Message", priority="default", tags="clock")


if __name__ == "__main__":
    unittest.main()
