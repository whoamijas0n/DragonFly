"""
Verifica que WiFiService siga siendo compatible tras adoptar el parser compartido.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dragonfly.services.wifi_service import WiFiService

FIXTURE = Path(__file__).parent / "fixtures" / "airodump_sample.csv"


class FakeProc:
    def __init__(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


class WiFiServiceCompatTests(unittest.TestCase):
    def setUp(self):
        self.service = WiFiService()
        self.commands = []

    def _copy_fixture_for_command(self, command):
        self.commands.append(list(command) if not isinstance(command, str) else command)
        if "-w" in command:
            prefix = command[command.index("-w") + 1]
            shutil.copyfile(FIXTURE, f"{prefix}-01.csv")

    def test_scan_networks_returns_legacy_and_enriched_keys(self):
        def fake_run(command, **kwargs):
            self._copy_fixture_for_command(command)
            return None

        with patch("dragonfly.services.wifi_service.safe_run", side_effect=fake_run):
            redes = self.service.scan_networks("wlan0", duration=10, band="2.4")

        self.assertEqual(len(redes), 6)
        first = redes[0]
        for key in ("bssid", "ch", "essid", "banda"):
            self.assertIn(key, first)
        for key in ("signal_dbm", "signal_quality", "security", "clients_observed",
                    "vendor", "honeypot_score", "honeypot_reasons"):
            self.assertIn(key, first)

        command = self.commands[0]
        self.assertIn("--band", command)
        self.assertIn("bg", command)
        self.assertNotIsInstance(command, str)
        self.assertTrue(any(red["banda"] == "2.4GHz" for red in redes))
        self.assertTrue(any(red["banda"] == "5GHz" for red in redes))

    def test_scan_networks_dual_uses_shared_parser(self):
        def fake_popen(command, **kwargs):
            self._copy_fixture_for_command(command)
            return FakeProc()

        with patch("dragonfly.services.wifi_service.safe_popen", side_effect=fake_popen):
            redes, iface_map = self.service.scan_networks_dual("wlan0mon", "wlan1mon", duration=10)

        self.assertEqual(len(redes), 6)
        self.assertEqual(len(iface_map), 6)
        self.assertEqual(len(self.commands), 2)
        for key in ("bssid", "ch", "essid", "banda", "signal_dbm", "clients_observed"):
            self.assertIn(key, redes[0])

    def test_scan_clients_ignores_unassociated_station(self):
        def fake_run(command, **kwargs):
            self._copy_fixture_for_command(command)
            return None

        with patch("dragonfly.services.wifi_service.safe_run", side_effect=fake_run):
            clientes = self.service.scan_clients("wlan0mon", "F4:F5:D8:11:22:01", "6", duration=5)

        self.assertEqual(len(clientes), 4)
        self.assertNotIn("11:22:33:44:55:AA", clientes)


if __name__ == "__main__":
    unittest.main()
