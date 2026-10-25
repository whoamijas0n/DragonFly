"""Pruebas de capacidades WiFi para el AP con Internet."""

import ipaddress
import unittest
from unittest import mock

from dragonfly.core import wifi_interfaces


PHY_OUTPUT = """
\tBand 1:
\t\tFrequencies:
\t\t\t* 2412 MHz [1]
\t\t\t* 2437 MHz [6]
\tBand 2:
\t\tFrequencies:
\t\t\t* 5180 MHz [36]
\t\t\t* 5745 MHz [149]
"""


class BandParsingTest(unittest.TestCase):
    def test_parse_both_bands(self):
        bands = wifi_interfaces.parse_supported_bands(PHY_OUTPUT)
        self.assertTrue(bands["2.4"])
        self.assertTrue(bands["5"])

    def test_parse_only_24(self):
        bands = wifi_interfaces.parse_supported_bands(
            "Band 1:\n  * 2412 MHz [1]\n"
        )
        self.assertTrue(bands["2.4"])
        self.assertFalse(bands["5"])

    def test_parse_decimal_frequencies_from_iw(self):
        bands = wifi_interfaces.parse_supported_bands(
            "Band 1:\n  * 2412.0 MHz [1] (20.0 dBm)\n"
            "Band 2:\n  * 5180.0 MHz [36] (17.0 dBm)\n"
        )
        self.assertTrue(bands["2.4"])
        self.assertTrue(bands["5"])

    def test_empty_output_is_conservative(self):
        bands = wifi_interfaces.parse_supported_bands("")
        self.assertFalse(bands["2.4"])
        self.assertFalse(bands["5"])


class InternetCandidatesTest(unittest.TestCase):
    def test_current_hardware_has_no_deauth_candidate(self):
        upstreams = {
            "wlan0": {"iface": "wlan1", "ip": "192.168.1.48", "metric": 601},
            "wlan1": {"iface": "wlan0", "ip": "192.168.1.222", "metric": 600},
        }
        with mock.patch.object(
            wifi_interfaces, "get_ap_interfaces", return_value=["wlan0", "wlan1"]
        ), mock.patch.object(
            wifi_interfaces, "find_upstream",
            side_effect=lambda ap_iface=None: upstreams.get(ap_iface),
        ), mock.patch.object(
            wifi_interfaces, "share_phy", return_value=False
        ), mock.patch.object(
            wifi_interfaces, "get_monitor_interfaces", return_value=["wlan1"]
        ), mock.patch.object(
            wifi_interfaces, "get_supported_bands",
            side_effect=lambda iface: (
                {"2.4": True, "5": True} if iface == "wlan1"
                else {"2.4": True, "5": False}
            ),
        ):
            candidates = wifi_interfaces.get_internet_ap_candidates()
        self.assertEqual(len(candidates), 2)
        self.assertFalse(any(c["single_deauth"] for c in candidates))
        self.assertFalse(any(c["dual_deauth"] for c in candidates))

    def test_ethernet_upstream_enables_single_deauth(self):
        with mock.patch.object(
            wifi_interfaces, "get_ap_interfaces", return_value=["wlan0"]
        ), mock.patch.object(
            wifi_interfaces, "find_upstream",
            return_value={"iface": "eth0", "ip": "192.168.1.10", "metric": 100},
        ), mock.patch.object(
            wifi_interfaces, "share_phy", return_value=False
        ), mock.patch.object(
            wifi_interfaces, "get_monitor_interfaces", return_value=["wlan1"]
        ), mock.patch.object(
            wifi_interfaces, "get_supported_bands",
            return_value={"2.4": True, "5": False},
        ):
            candidates = wifi_interfaces.get_internet_ap_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]["single_deauth"])
        self.assertFalse(candidates[0]["dual_deauth"])


class InternetRoleSelectionTest(unittest.TestCase):
    def test_upstream_options_exclude_ap_and_respect_metric(self):
        routes = [
            {
                "iface": "wlan0", "gateway": "192.168.1.1",
                "metric": 600, "raw": "default dev wlan0",
            },
            {
                "iface": "wlan1", "gateway": "192.168.1.1",
                "metric": 601, "raw": "default dev wlan1",
            },
            {
                "iface": "eth0", "gateway": "10.0.0.1",
                "metric": 100, "raw": "default dev eth0",
            },
        ]
        addresses = {
            "wlan0": ipaddress.IPv4Interface("192.168.1.222/24"),
            "wlan1": ipaddress.IPv4Interface("192.168.1.48/24"),
            "eth0": ipaddress.IPv4Interface("10.0.0.20/24"),
        }
        with mock.patch.object(
            wifi_interfaces, "get_default_routes", return_value=routes
        ), mock.patch.object(
            wifi_interfaces, "get_interface_ipv4",
            side_effect=lambda iface: addresses.get(iface),
        ), mock.patch.object(
            wifi_interfaces, "share_phy", return_value=False
        ), mock.patch.object(
            wifi_interfaces, "get_dns_servers", return_value=["1.1.1.1"]
        ):
            options = wifi_interfaces.get_internet_upstream_options("wlan1")
        self.assertEqual([item["iface"] for item in options], ["eth0", "wlan0"])
        self.assertEqual(options[1]["ip"], "192.168.1.222")

    def test_upstream_options_exclude_same_phy(self):
        routes = [
            {"iface": "wlan0", "metric": 600, "raw": "default dev wlan0"},
            {"iface": "wlan1", "metric": 601, "raw": "default dev wlan1"},
        ]
        with mock.patch.object(
            wifi_interfaces, "get_default_routes", return_value=routes
        ), mock.patch.object(
            wifi_interfaces, "get_interface_ipv4",
            return_value=ipaddress.IPv4Interface("192.168.1.10/24"),
        ), mock.patch.object(
            wifi_interfaces, "share_phy",
            side_effect=lambda first, second: {first, second} == {"wlan0", "wlan1"},
        ), mock.patch.object(
            wifi_interfaces, "get_dns_servers", return_value=["1.1.1.1"]
        ):
            options = wifi_interfaces.get_internet_upstream_options("wlan0")
        self.assertEqual(options, [])

    def test_build_candidate_uses_selected_upstream(self):
        upstream = {"iface": "wlan1", "ip": "192.168.1.48"}
        with mock.patch.object(
            wifi_interfaces, "share_phy", return_value=False
        ), mock.patch.object(
            wifi_interfaces, "get_monitor_interfaces",
            return_value=["wlan1", "wlan2"],
        ), mock.patch.object(
            wifi_interfaces, "get_supported_bands",
            return_value={"2.4": True, "5": True},
        ):
            candidate = wifi_interfaces.build_internet_candidate("wlan0", upstream)
        self.assertEqual(candidate["ap_iface"], "wlan0")
        self.assertEqual(candidate["upstream"]["iface"], "wlan1")
        self.assertEqual(candidate["monitor_ifaces"], ["wlan2"])
        self.assertTrue(candidate["single_deauth"])

    def test_ap_interfaces_only_include_radios_with_upstream(self):
        with mock.patch.object(
            wifi_interfaces, "get_ap_interfaces",
            return_value=["wlan0", "wlan1"],
        ), mock.patch.object(
            wifi_interfaces, "get_internet_upstream_options",
            side_effect=lambda ap: (
                [{"iface": "wlan1"}] if ap == "wlan0" else []
            ),
        ), mock.patch.object(
            wifi_interfaces, "get_supported_bands",
            return_value={"2.4": True, "5": False},
        ):
            interfaces = wifi_interfaces.get_internet_ap_interfaces()
        self.assertEqual([item["ap_iface"] for item in interfaces], ["wlan0"])


class ScanInterfaceTest(unittest.TestCase):
    def test_uses_ap_radio_temporarily(self):
        with mock.patch.object(
            wifi_interfaces, "supports_monitor", return_value=True
        ), mock.patch.object(
            wifi_interfaces, "get_monitor_interfaces", return_value=["wlan1"]
        ):
            iface, temporary = wifi_interfaces.get_internet_scan_interface(
                "wlan1", [], "wlan0"
            )
        self.assertEqual(iface, "wlan1")
        self.assertTrue(temporary)

    def test_prefers_existing_monitor(self):
        iface, temporary = wifi_interfaces.get_internet_scan_interface(
            "wlan0", ["wlan2"], "eth0"
        )
        self.assertEqual(iface, "wlan2")
        self.assertFalse(temporary)


if __name__ == "__main__":
    unittest.main()
