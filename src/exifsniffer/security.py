"""SSRF-oriented URL and DNS checks for outbound HTTP fetches."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
    }
)


def host_suffix_allowed(hostname: str, allowed: frozenset[str] | None, blocked: frozenset[str] | None) -> bool:
    """If *allowed* is set, hostname must end with one of the suffixes. *blocked* always applies."""
    h = hostname.lower().rstrip(".")
    if blocked:
        for suf in blocked:
            if suf and (h == suf.lower() or h.endswith("." + suf.lower())):
                return False
    if allowed is None:
        return True
    for suf in allowed:
        if suf and (h == suf.lower() or h.endswith("." + suf.lower())):
            return True
    return False


def _addrs_for_host(hostname: str) -> list[str]:
    ips: list[str] = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            infos = socket.getaddrinfo(hostname, None, family, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        for info in infos:
            sockaddr = info[4]
            ips.append(sockaddr[0])
    if not ips:
        raise ValueError(f"Could not resolve host: {hostname!r}")
    return ips


def ip_is_forbidden(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        return True
    if ip.version == 4:
        # IPv4 documentation / shared address / unspecified
        if ip in ipaddress.ip_network("0.0.0.0/8"):
            return True
        if ip in ipaddress.ip_network("127.0.0.0/8"):
            return True
        if ip in ipaddress.ip_network("169.254.0.0/16"):
            return True
        if ip in ipaddress.ip_network("192.0.0.0/24"):
            return True
        if ip in ipaddress.ip_network("192.0.2.0/24"):
            return True
        if ip in ipaddress.ip_network("198.51.100.0/24"):
            return True
        if ip in ipaddress.ip_network("203.0.113.0/24"):
            return True
        if ip in ipaddress.ip_network("240.0.0.0/4"):
            return True
    return False


def assert_url_safe_for_fetch(
    url: str,
    *,
    allow_private_hosts: bool,
    allowed_suffixes: frozenset[str] | None,
    blocked_suffixes: frozenset[str] | None,
) -> None:
    """Raise ValueError if *url* must not be fetched (scheme/host/DNS policy)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")
    if host.lower() in BLOCKED_HOSTNAMES:
        raise ValueError(f"Host not allowed: {host}")
    if not host_suffix_allowed(host, allowed_suffixes, blocked_suffixes):
        raise ValueError("Host is not permitted by FETCH_ALLOWED_HOST_SUFFIXES / FETCH_BLOCKED_HOST_SUFFIXES policy")

    # Literal IP in URL
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not allow_private_hosts and ip_is_forbidden(host):
            raise ValueError("Target IP address is not allowed")
        return

    if allow_private_hosts:
        return

    for addr in _addrs_for_host(host):
        if ip_is_forbidden(addr):
            raise ValueError(f"Host resolves to a forbidden address: {addr}")
