"""Pruebas de configuración del Evil Twin con Internet (sin tocar la red real)."""

import ipaddress
import unittest
from unittest import mock

from dragonfly.services.evil_twin_service import EvilTwinService


class InternetHostapdConfigTest(unittest.TestCase):
    def test_internet_config_is_open_and_isolated(self):
        config = EvilTwinService.build_hostapd_config(
            "wlan1", {"essid": "DF_NAT", "ch": 36}, internet_mode=True
        )
        self.assertIn("interface=wlan1", config)
        self.assertIn("ssid=DF_NAT", config)
        self.assertIn("hw_mode=a", config)
        self.assertIn("channel=36", config)
        self.assertIn("wpa=0", config)
        self.assertIn("ap_isolate=1", config)
        self.assertIn("country_code=SV", config)

    def test_portal_config_keeps_previous_shape(self):
        config = EvilTwinService.build_hostapd_config(
            "wlan0", {"essid": "Portal", "ch": 6}
        )
        self.assertIn("hw_mode=g", config)
        self.assertNotIn("ap_isolate=1", config)


class InternetDnsmasqConfigTest(unittest.TestCase):
    def test_internet_forwards_real_dns(self):
        config = EvilTwinService.build_dnsmasq_config(
            "wlan1",
            gateway="10.42.0.1",
            internet_mode=True,
            upstream_dns=["1.1.1.1", "8.8.8.8"],
            lease_file="/tmp/session/dnsmasq.leases",
        )
        self.assertIn("listen-address=10.42.0.1", config)
        self.assertIn("dhcp-range=10.42.0.10,10.42.0.250", config)
        self.assertIn("server=1.1.1.1", config)
        self.assertIn("server=8.8.8.8", config)
        self.assertIn("dhcp-leasefile=/tmp/session/dnsmasq.leases", config)
        self.assertNotIn("address=/#/", config)

    def test_portal_config_remains_captive(self):
        config = EvilTwinService.build_dnsmasq_config("wlan0")
        self.assertIn("address=/#/10.0.0.1", config)
        self.assertIn("dhcp-range=10.0.0.10,10.0.0.250,12h", config)
        self.assertNotIn("server=", config)


class SsidValidationTest(unittest.TestCase):
    def test_valid_ssid(self):
        self.assertEqual(EvilTwinService.validate_ssid("  Mi Red  "), "Mi Red")

    def test_empty_ssid_rejected(self):
        with self.assertRaises(ValueError):
            EvilTwinService.validate_ssid("   ")

    def test_too_long_ssid_rejected(self):
        with self.assertRaises(ValueError):
            EvilTwinService.validate_ssid("x" * 33)


class UpstreamResolutionTest(unittest.TestCase):
    def test_honors_explicit_requested_interface(self):
        service = EvilTwinService()
        requested = {"iface": "wlan1", "ip": "192.168.1.48"}
        with mock.patch(
            "dragonfly.services.evil_twin_service.get_upstream_info_for_iface",
            return_value=requested,
        ), mock.patch(
            "dragonfly.services.evil_twin_service.find_upstream",
        ) as fallback:
            route = service._resolve_upstream("wlan0", "wlan1")
        self.assertEqual(route["iface"], "wlan1")
        fallback.assert_not_called()

    def test_uses_best_route_without_explicit_selection(self):
        service = EvilTwinService()
        with mock.patch(
            "dragonfly.services.evil_twin_service.find_upstream",
            return_value={"iface": "wlan0", "ip": "192.168.1.222"},
        ):
            route = service._resolve_upstream("wlan1", None)
        self.assertEqual(route["iface"], "wlan0")

    def test_falls_back_to_requested_interface_without_default(self):
        service = EvilTwinService()
        interface = ipaddress.IPv4Interface("192.168.50.2/24")
        with mock.patch(
            "dragonfly.services.evil_twin_service.get_upstream_info_for_iface",
            return_value=None,
        ), mock.patch(
            "dragonfly.services.evil_twin_service.get_interface_ipv4",
            return_value=interface,
        ), mock.patch(
            "dragonfly.services.evil_twin_service.get_dns_servers",
            return_value=["1.1.1.1"],
        ):
            route = service._resolve_upstream("wlan1", "wlan2")
        self.assertEqual(route["iface"], "wlan2")
        self.assertEqual(route["ip"], "192.168.50.2")


class CaptureAvailabilityTest(unittest.TestCase):
    def test_capture_available_uses_finder(self):
        with mock.patch.object(
            EvilTwinService, "_find_tcpdump", return_value="/usr/sbin/tcpdump"
        ):
            self.assertTrue(EvilTwinService.capture_available())
        with mock.patch.object(
            EvilTwinService, "_find_tcpdump", return_value=None
        ):
            self.assertFalse(EvilTwinService.capture_available())


if __name__ == "__main__":
    unittest.main()
