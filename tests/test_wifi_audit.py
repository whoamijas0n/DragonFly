"""
Tests de WiFi Audit 2.0 v1: parser, enriquecimiento, honeypot y reportes.
Ejecutar desde la raíz del proyecto:
    python3 -m unittest discover -s tests -v
"""

import csv
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from dragonfly.config import BASE_DIR_WIFI_AUDIT
from dragonfly.services.wifi_audit_service import (
    HIDDEN_SSID,
    WiFiAuditService,
    build_summary,
    channel_to_band,
    dbm_to_quality,
    enrich_networks,
    format_network_detail,
    lookup_vendor,
    parse_airodump_csv,
    score_honeypot,
)

FIXTURE = Path(__file__).parent / "fixtures" / "airodump_sample.csv"


class FakeWiFiService:
    def __init__(self):
        self.restored = []

    def enable_monitor_mode(self, iface):
        return f"{iface}mon"

    def disable_monitor_mode(self, mon_iface):
        self.restored.append(mon_iface)


class ConfigTests(unittest.TestCase):
    def test_audit_results_directory(self):
        self.assertEqual(os.path.basename(BASE_DIR_WIFI_AUDIT), "Resultados_Auditoria")


class ParserTests(unittest.TestCase):
    def test_parse_realistic_airodump_csv(self):
        aps, stations = parse_airodump_csv(str(FIXTURE))

        self.assertEqual(len(aps), 6)
        self.assertEqual(len(stations), 5)

        casa = next(ap for ap in aps if ap["bssid"] == "F4:F5:D8:11:22:01")
        self.assertEqual(casa["essid"], "Casa")
        self.assertEqual(casa["channel"], "6")
        self.assertEqual(casa["power"], -45)
        self.assertEqual(casa["beacons"], 120)
        self.assertEqual(casa["iv"], 30)
        self.assertEqual(casa["data"], 30)
        self.assertEqual(casa["band"], "2.4 GHz")

        oficina = next(ap for ap in aps if ap["bssid"] == "3C:5A:37:11:22:02")
        self.assertEqual(oficina["essid"], "Oficina, Piso 2")
        self.assertEqual(oficina["band"], "5 GHz")

        hidden = next(ap for ap in aps if ap["bssid"] == "00:0C:29:11:22:03")
        self.assertEqual(hidden["essid"], HIDDEN_SSID)
        self.assertEqual(hidden["privacy"], "OPN")

        no_signal = next(ap for ap in aps if ap["bssid"] == "00:50:56:11:22:04")
        self.assertEqual(no_signal["power"], -1)

        unassociated = next(st for st in stations if st["station_mac"] == "11:22:33:44:55:AA")
        self.assertEqual(unassociated["bssid"], "")

    def test_missing_file_returns_empty_sections(self):
        aps, stations = parse_airodump_csv("/tmp/no-existe-airodump.csv")
        self.assertEqual(aps, [])
        self.assertEqual(stations, [])

    def test_helpers(self):
        self.assertEqual(channel_to_band("1"), "2.4 GHz")
        self.assertEqual(channel_to_band("36"), "5 GHz")
        self.assertEqual(channel_to_band(""), "Desconocida")
        self.assertEqual(dbm_to_quality(-45), 100)
        self.assertEqual(dbm_to_quality(-65), 70)
        self.assertEqual(dbm_to_quality(-1), None)
        self.assertIn("Cisco", lookup_vendor("00:00:0C:11:22:33"))


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.aps, self.stations = parse_airodump_csv(str(FIXTURE))
        self.networks = enrich_networks(self.aps, self.stations)
        self.by_bssid = {net["bssid"]: net for net in self.networks}

    def test_clients_and_bands(self):
        casa = self.by_bssid["F4:F5:D8:11:22:01"]
        oficina = self.by_bssid["3C:5A:37:11:22:02"]
        hidden = self.by_bssid["00:0C:29:11:22:03"]
        no_signal = self.by_bssid["00:50:56:11:22:04"]

        self.assertEqual(casa["clients_observed"], 2)
        self.assertEqual(oficina["clients_observed"], 1)
        self.assertEqual(hidden["clients_observed"], 0)
        self.assertEqual(casa["band"], "2.4 GHz")
        self.assertEqual(oficina["band"], "5 GHz")
        self.assertEqual(oficina["signal_dbm"], -60)
        self.assertEqual(oficina["signal_quality"], 80)
        self.assertIsNone(no_signal["signal_dbm"])
        self.assertIsNone(no_signal["signal_quality"])

    def test_security_and_vendor(self):
        office = self.by_bssid["3C:5A:37:11:22:02"]
        hidden = self.by_bssid["00:0C:29:11:22:03"]
        cisco = self.by_bssid["00:00:0C:11:22:33"]

        self.assertEqual(office["security"], "WPA3-CCMP-SAE")
        self.assertEqual(hidden["security"], "Abierta")
        self.assertIn("Cisco", cisco["vendor"])

    def test_honeypot_rules(self):
        local = self.by_bssid["02:11:22:33:44:55"]
        self.assertGreaterEqual(local["honeypot_score"], 40)
        self.assertIn("localmente administrada", " ".join(local["honeypot_reasons"]).lower())
        self.assertIn("inusualmente fuerte", " ".join(local["honeypot_reasons"]).lower())

        casa = self.by_bssid["F4:F5:D8:11:22:01"]
        self.assertLess(casa["honeypot_score"], 25)
        self.assertEqual(casa["honeypot_level"], "Bajo")

    def test_detail_format_contains_required_fields(self):
        detail = format_network_detail(self.by_bssid["3C:5A:37:11:22:02"])
        for expected in ("ESSID", "BSSID", "Canal", "Banda", "Señal", "Seguridad",
                         "Beacons", "Data", "IV", "Clientes observados", "Fabricante",
                         "Honeypot", "Motivos"):
            self.assertIn(expected, detail)

    def test_summary_counts(self):
        summary = build_summary(self.networks)
        self.assertEqual(summary["total_redes"], 6)
        self.assertEqual(summary["abiertas"], 1)
        self.assertEqual(summary["wep"], 0)
        self.assertEqual(summary["wpa2"], 4)
        self.assertEqual(summary["wpa3"], 1)
        self.assertEqual(summary["clientes_observados"], 4)
        self.assertEqual(summary["score_alto"], 0)


class HoneypotTests(unittest.TestCase):
    def test_same_ssid_with_different_security_is_flagged(self):
        ap1 = {
            "bssid": "00:11:22:33:44:55", "essid": "Casa", "channel": "6",
            "privacy": "WPA2", "cipher": "CCMP", "auth": "PSK", "power": -55,
        }
        ap2 = {
            "bssid": "00:11:22:33:44:66", "essid": "Casa", "channel": "6",
            "privacy": "", "cipher": "", "auth": "", "power": -60,
        }
        score, reasons = score_honeypot(ap1, [ap1, ap2])
        self.assertGreaterEqual(score, 20)
        self.assertIn("seguridad distintas", " ".join(reasons).lower())

    def test_same_ssid_same_security_dual_band_is_not_flagged(self):
        ap1 = {
            "bssid": "00:11:22:33:44:55", "essid": "Casa", "channel": "6",
            "privacy": "WPA2", "cipher": "CCMP", "auth": "PSK", "power": -55,
        }
        ap2 = {
            "bssid": "00:11:22:33:44:66", "essid": "Casa", "channel": "36",
            "privacy": "WPA2", "cipher": "CCMP", "auth": "PSK", "power": -60,
        }
        score, reasons = score_honeypot(ap1, [ap1, ap2])
        self.assertNotIn("seguridad distintas", " ".join(reasons).lower())

    def test_multicast_bssid_is_flagged(self):
        ap = {
            "bssid": "01:11:22:33:44:55", "essid": "Sospechosa", "channel": "1",
            "privacy": "WPA2", "cipher": "CCMP", "auth": "PSK", "power": -50,
        }
        score, reasons = score_honeypot(ap, [ap])
        self.assertGreaterEqual(score, 30)
        self.assertIn("multicast", " ".join(reasons).lower())


class ServiceFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dragonfly_wifi_audit_test_")
        self.wifi = FakeWiFiService()
        self.service = WiFiAuditService(wifi_service=self.wifi, base_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_airodump(self, mon_iface, duration, band):
        prefix = os.path.join(self.tmp, f"scan_{mon_iface}_{band}")
        shutil.copyfile(FIXTURE, f"{prefix}-01.csv")
        return prefix

    def test_scan_single_parses_saves_and_restores(self):
        logs = []
        with patch.object(self.service, "_run_airodump", side_effect=self._fake_airodump):
            result = self.service.scan_single(
                "wlan0", duration=10, band="2.4", on_output=logs.append,
            )

        self.assertEqual(len(result["networks"]), 6)
        self.assertEqual(result["summary"]["total_redes"], 6)
        self.assertEqual(result["summary"]["clientes_observados"], 4)
        self.assertEqual(self.wifi.restored, ["wlan0mon"])
        self.assertTrue(any("Restaurando" in line for line in logs))

        session_dir = result["session_dir"]
        self.assertTrue(os.path.isfile(os.path.join(session_dir, "redes.json")))
        self.assertTrue(os.path.isfile(os.path.join(session_dir, "redes.csv")))
        self.assertTrue(os.path.isfile(os.path.join(session_dir, "reporte.txt")))

        with open(os.path.join(session_dir, "redes.json"), encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["metadata"]["total_redes"], 6)
        self.assertEqual(len(payload["networks"]), 6)
        self.assertIn("essid", payload["networks"][0])

        with open(os.path.join(session_dir, "redes.csv"), encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 6)
        self.assertTrue(any(row["essid"] == "Oficina, Piso 2" for row in rows))
        self.assertTrue(any(row["security"].startswith("WPA3") for row in rows))
        self.assertTrue(any(row["honeypot_reasons"] for row in rows))

    def test_scan_dual_merges_and_restores_both(self):
        with patch.object(WiFiAuditService, "interfaces_share_phy", return_value=False):
            with patch.object(self.service, "_run_airodump", side_effect=self._fake_airodump):
                result = self.service.scan_dual("wlan0", "wlan1", duration=10)

        self.assertEqual(len(result["networks"]), 6)
        self.assertEqual(result["summary"]["total_redes"], 6)
        self.assertEqual(len(self.wifi.restored), 2)
        self.assertIn("wlan0mon", self.wifi.restored)
        self.assertIn("wlan1mon", self.wifi.restored)
        self.assertTrue(os.path.isfile(os.path.join(result["session_dir"], "redes.json")))

    def test_scan_dual_rejects_same_interface(self):
        with self.assertRaises(ValueError):
            self.service.scan_dual("wlan0", "wlan0", duration=10)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            self.service.scan_single("wlan0", duration=1)
        with self.assertRaises(ValueError):
            self.service.scan_single("wlan 0", duration=10)
        with self.assertRaises(ValueError):
            self.service.scan_single("wlan0", band="6")

    def test_cancel_scan_restores_interface_and_marks_idle(self):
        started = threading.Event()
        release = threading.Event()
        errors = []

        def fake_airodump(mon_iface, duration, band):
            started.set()
            release.wait(2)
            prefix = os.path.join(self.tmp, f"cancel_{mon_iface}_{band}")
            shutil.copyfile(FIXTURE, f"{prefix}-01.csv")
            return prefix

        def run_scan():
            try:
                self.service.scan_single("wlan0", duration=10, band="2.4")
            except Exception as exc:
                errors.append(exc)

        with patch.object(self.service, "_run_airodump", side_effect=fake_airodump):
            worker = threading.Thread(target=run_scan)
            worker.start()
            self.assertTrue(started.wait(2))
            self.service.cancel_scan()
            release.set()
            worker.join(3)

        self.assertFalse(worker.is_alive())
        self.assertTrue(any("cancelado" in str(exc).lower() for exc in errors))
        self.assertEqual(self.wifi.restored, ["wlan0mon"])
        self.assertTrue(self.service.wait_for_idle(timeout=1))

    def test_read_report_is_scoped_to_session(self):
        with patch.object(self.service, "_run_airodump", side_effect=self._fake_airodump):
            result = self.service.scan_single("wlan0", duration=10, band="2.4")
        session_name = os.path.basename(result["session_dir"])
        content = self.service.read_report(session_name)
        self.assertIn("networks", content)
        self.assertIn("Casa", content)


if __name__ == "__main__":
    unittest.main()
