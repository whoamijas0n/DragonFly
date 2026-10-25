"""Pruebas de detección de rutas, gateway y DNS del modo Internet."""

import unittest
from unittest import mock

from dragonfly.core import routing


class DefaultRouteParsingTest(unittest.TestCase):
    def test_parse_multiple_routes_and_metrics(self):
        output = (
            "default via 192.168.1.1 dev wlan0 proto dhcp "
            "src 192.168.1.222 metric 600\n"
            "default via 10.0.0.1 dev eth0 metric 100\n"
        )
        routes = routing.parse_default_routes(output)
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[0]["iface"], "wlan0")
        self.assertEqual(routes[0]["gateway"], "192.168.1.1")
        self.assertEqual(routes[0]["metric"], 600)
        self.assertEqual(routes[1]["iface"], "eth0")

    def test_parse_route_without_gateway(self):
        routes = routing.parse_default_routes("default dev usb0 scope link\n")
        self.assertEqual(routes[0]["iface"], "usb0")
        self.assertIsNone(routes[0]["gateway"])

    def test_parse_ipv4_interface(self):
        interface = routing.parse_ipv4_interface(
            "2: wlan0    inet 192.168.1.222/24 brd 192.168.1.255 scope global wlan0"
        )
        self.assertIsNotNone(interface)
        self.assertEqual(str(interface.ip), "192.168.1.222")
        self.assertEqual(str(interface.network), "192.168.1.0/24")


class GatewaySelectionTest(unittest.TestCase):
    def test_avoids_upstream_subnet(self):
        with mock.patch.object(
            routing, "get_interface_network",
            return_value=routing.ipaddress.IPv4Network("10.42.0.0/24"),
        ):
            info = routing.choose_gateway("wlan0")
        self.assertEqual(info["gateway"], "10.13.37.1")
        self.assertEqual(info["network"], "10.13.37.0/24")

    def test_uses_first_candidate_when_free(self):
        with mock.patch.object(
            routing, "get_interface_network",
            return_value=routing.ipaddress.IPv4Network("192.168.1.0/24"),
        ):
            info = routing.choose_gateway("wlan0")
        self.assertEqual(info["gateway"], "10.42.0.1")


class PrimaryUpstreamTest(unittest.TestCase):
    def test_returns_primary_interface(self):
        with mock.patch.object(
            routing, "find_upstream", return_value={"iface": "wlan0"}
        ):
            self.assertEqual(routing.get_primary_upstream_iface(), "wlan0")

    def test_returns_none_without_route(self):
        with mock.patch.object(routing, "find_upstream", return_value=None):
            self.assertIsNone(routing.get_primary_upstream_iface())


class DnsSelectionTest(unittest.TestCase):
    def test_deduplicates_and_falls_back(self):
        with mock.patch.object(
            routing, "_resolvectl_dns", return_value=["1.1.1.1"]
        ), mock.patch.object(
            routing, "_read_nameservers", side_effect=[["1.1.1.1"], ["8.8.8.8"]]
        ):
            servers = routing.get_dns_servers("wlan0")
        self.assertEqual(servers, ["1.1.1.1", "8.8.8.8"])

    def test_public_fallback(self):
        with mock.patch.object(
            routing, "_resolvectl_dns", return_value=[]
        ), mock.patch.object(
            routing, "_read_nameservers", return_value=[]
        ):
            servers = routing.get_dns_servers("wlan0")
        self.assertEqual(servers, ["1.1.1.1", "8.8.8.8"])


if __name__ == "__main__":
    unittest.main()
