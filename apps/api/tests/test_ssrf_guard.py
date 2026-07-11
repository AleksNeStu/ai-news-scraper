"""Unit tests for ``api.services.ssrf_guard``.

Per ADR-025 §Test matrix and Task #69 ``testStrategy``. Pytest,
parametrized. Mocks ``socket.getaddrinfo`` so the suite never makes
real DNS queries.

Test matrix (mirrors ADR-025 §Test matrix):

1. Blocked CIDRs (parametrize over representative subset of §3).
2. URL encoding tricks (octal, decimal, hex, IPv4-mapped, bracketed,
   nip.io, localhost, ``0``).
3. Scheme allow-list (``file:``, ``gopher:``, ``data:``, ``javascript:``,
   ``ftp:``).
4. DNS-rebinding defense (mock returns ``[public, private]`` → reject).
5. Happy path (mock returns public IP → accept).
6. Bulk path (500 URLs / 100 unique hostnames → resolver called ≤100).
7. Hostname shape checks (empty, whitespace, 4096-char URL).
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from api.exceptions import SSRFError
from api.services import ssrf_guard
from api.services.ssrf_guard import (
    BLOCKED_CIDRS,
    resolve_and_check,
    validate_outbound_url,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache():
    """Drop the per-process DNS cache between tests.

    The cache is process-global state; without this fixture, a host
    resolved in one test would short-circuit the next test's resolver
    mock and silently pass.
    """
    ssrf_guard._cache_clear_for_tests()
    yield
    ssrf_guard._cache_clear_for_tests()


def _mock_getaddrinfo(ips: list[str]):
    """Build a ``socket.getaddrinfo`` stub that returns ``ips`` for any host.

    ``getaddrinfo`` returns one tuple per (family, socktype, proto,
    canonname, sockaddr). We always emit AF_INET-shaped tuples — the
    guard is family-agnostic, and IPv6 literals are covered by the
    IP-literal fast path.
    """

    def _stub(host, *args, **kwargs):  # noqa: ARG001
        result = []
        for ip in ips:
            sockaddr = (ip, 0)
            result.append((socket.AF_INET, socket.SOCK_STREAM, 0, "", sockaddr))
        return result

    return _stub


# ---------------------------------------------------------------------------
# 1. Blocked CIDRs — parametrize over the §3 table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        # Loopback
        "127.0.0.1",
        "127.0.0.53",  # systemd-resolved
        "127.255.255.254",
        # Zero / current-network
        "0.0.0.0",
        "0.1.2.3",
        # RFC1918
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.0.1",
        "192.168.1.254",
        # CGNAT
        "100.64.0.1",
        # Link-local — incl. AWS / GCP / Azure metadata
        "169.254.1.1",
        "169.254.169.254",
        # IETF / TEST-NET
        "192.0.0.1",
        "192.0.2.1",
        "198.18.0.1",
        "198.51.100.1",
        "203.0.113.1",
        # Multicast
        "224.0.0.1",
        "239.255.255.250",
        # Reserved / broadcast
        "240.0.0.1",
        "255.255.255.255",
    ],
)
def test_blocked_ipv4_ip_literal(ip: str):
    """Every blocked IPv4 literal must reject via the IP-literal fast path."""
    with pytest.raises(SSRFError):
        validate_outbound_url(f"http://{ip}/")


@pytest.mark.parametrize(
    "ip",
    [
        "::1",
        "::",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "fc00::1",
        "fd00::1",
        "fe80::1",
        "ff00::1",
        "ff02::1",
        "64:ff9b::",
        "100::1",
        "2001::1",
        "2001:db8::1",
        "2002::1",
    ],
)
def test_blocked_ipv6_ip_literal(ip: str):
    """Every blocked IPv6 literal must reject via the IP-literal fast path."""
    # urlparse requires brackets for IPv6 literals in the host position.
    with pytest.raises(SSRFError):
        validate_outbound_url(f"http://[{ip}]/")


# ---------------------------------------------------------------------------
# 2. URL encoding tricks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        # Octal — Python's ipaddress rejects "0177.0.0.1" so the guard
        # falls through to dns, which our mock will treat as a hostname
        # and the hostname-shape check will reject.
        "http://0177.0.0.1/",
        # Decimal IPv4 — same fate.
        "http://2130706433/",
        # Hex IPv4 — same.
        "http://0x7f000001/",
        # IPv4-mapped IPv6 — caught by ::ffff:0:0/96.
        "http://[::ffff:127.0.0.1]/",
        # Bracketed loopback — urlparse strips brackets, literal rejected.
        "http://[127.0.0.1]/",
        # External resolver that points at loopback — caught at DNS time.
        # We mock getaddrinfo to return 127.0.0.1 for any hostname.
        "http://127.0.0.1.nip.io/",
        "http://localtest.me/",
        # ``localhost`` — most resolvers map this to 127.0.0.1.
        "http://localhost/",
    ],
)
def test_url_encoding_tricks(url: str):
    """Encoding tricks that bypass naive ``urlparse`` checks must reject."""
    # Mock DNS so any hostname that survives the parse stage resolves
    # to 127.0.0.1 — proves the guard rejects AFTER resolution, not
    # just at parse time.
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["127.0.0.1"]),
    ):
        with pytest.raises(SSRFError):
            validate_outbound_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://0/",
        "http://0.0.0.0/",
    ],
)
def test_zero_url_rejected(url: str):
    """``http://0`` and ``http://0.0.0.0`` must both reject."""
    with pytest.raises(SSRFError):
        validate_outbound_url(url)


# ---------------------------------------------------------------------------
# 3. Scheme allow-list
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com/",
        "data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==",
        "javascript:alert(1)",
        "ftp://example.com/rss",
        "dict://example.com/",
        "ldap://example.com/",
    ],
)
def test_non_http_scheme_rejected(url: str):
    """Every non-HTTP(S) scheme must reject."""
    with pytest.raises(SSRFError):
        validate_outbound_url(url)


# ---------------------------------------------------------------------------
# 4. DNS-rebinding defense
# ---------------------------------------------------------------------------


def test_dns_rebinding_returns_private_among_public():
    """If getaddrinfo returns [public, private], reject the host."""
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["93.184.216.34", "127.0.0.1"]),
    ):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://attacker.example/")


def test_dns_rebinding_returns_private_among_public_reverse_order():
    """Order-independent: private-first must also reject."""
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["169.254.169.254", "1.1.1.1"]),
    ):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://attacker.example/")


def test_dns_failure_rejected():
    """DNS failure must surface as SSRFError, not as a generic socket error."""

    def _raise_gaierror(host, *args, **kwargs):  # noqa: ARG001
        raise socket.gaierror(-2, "Name or service not known")

    with patch("socket.getaddrinfo", side_effect=_raise_gaierror):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://no-such-host.invalid/")


# ---------------------------------------------------------------------------
# 5. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_public_ip():
    """Mocked public IP must validate cleanly."""
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["93.184.216.34"]),
    ):
        validate_outbound_url("http://example.com/")


def test_happy_path_public_ipv6():
    """Mocked public IPv6 must validate cleanly."""
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["2606:2800:220:1:248:1893:25c8:1946"]),
    ):
        validate_outbound_url("http://example.com/")


def test_resolve_and_check_returns_ips():
    """``resolve_and_check`` returns the public IPs it found."""
    with patch(
        "socket.getaddrinfo",
        side_effect=_mock_getaddrinfo(["93.184.216.34", "93.184.216.35"]),
    ):
        ips = resolve_and_check("example.com")
        assert sorted(ips) == ["93.184.216.34", "93.184.216.35"]


# ---------------------------------------------------------------------------
# 6. Bulk-path amplification — cache effectiveness
# ---------------------------------------------------------------------------


def test_bulk_path_cache_hit_on_duplicate_hostnames():
    """500 URLs over 100 unique hostnames → getaddrinfo called ≤100 times.

    Per ADR-025 §6. The guard must keep the per-request DNS query
    count bounded even when the bulk endpoint amplifies the URL
    count to 500.
    """
    hosts = [f"host{i}.example" for i in range(100)]
    # Build 500 URLs: 5 copies of each of the 100 hosts.
    urls = [f"http://{host}/" for host in hosts for _ in range(5)]

    call_counter = {"count": 0}

    def _counting_stub(host, *args, **kwargs):  # noqa: ARG001
        call_counter["count"] += 1
        return _mock_getaddrinfo(["93.184.216.34"])(host, *args, **kwargs)

    with patch("socket.getaddrinfo", side_effect=_counting_stub):
        for url in urls:
            validate_outbound_url(url)

    # First call per host = 100. Cached for the other 4 copies each.
    assert call_counter["count"] == 100, (
        f"expected exactly 100 resolver calls (one per unique host), "
        f"got {call_counter['count']}"
    )


def test_cache_ttl_eviction_in_memory_pressure():
    """When the cache is at capacity, oldest insertion is evicted."""
    # Fill cache to the cap.
    for i in range(ssrf_guard.MAX_CACHE_SIZE):
        ssrf_guard._cache_put(f"host{i}.example", ["93.184.216.34"])
    assert len(ssrf_guard._RESOLUTION_CACHE) == ssrf_guard.MAX_CACHE_SIZE

    # Insert one more — should evict host0 (oldest insertion).
    ssrf_guard._cache_put("host-new.example", ["93.184.216.34"])
    assert len(ssrf_guard._RESOLUTION_CACHE) == ssrf_guard.MAX_CACHE_SIZE
    assert "host0.example" not in ssrf_guard._RESOLUTION_CACHE
    assert "host-new.example" in ssrf_guard._RESOLUTION_CACHE


# ---------------------------------------------------------------------------
# 7. Hostname / URL shape checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "",
        " ",
        "   ",
        "\n",
        "\t",
    ],
)
def test_empty_or_whitespace_url_rejected(url: str):
    """Empty / whitespace-only URLs must reject without a DNS query."""
    with patch("socket.getaddrinfo") as mock_dns:
        with pytest.raises(SSRFError):
            validate_outbound_url(url)
        # No DNS query needed for an empty URL.
        mock_dns.assert_not_called()


def test_overlong_url_rejected():
    """URL > 4096 chars must reject (defense against pathological inputs)."""
    huge = "http://example.com/" + ("a" * 5000)
    with pytest.raises(SSRFError):
        validate_outbound_url(huge)


def test_url_without_scheme_rejected():
    """A URL with no scheme must reject (no allow-list match)."""
    with pytest.raises(SSRFError):
        validate_outbound_url("example.com/")


def test_url_with_overlong_hostname_rejected():
    """A URL with hostname > MAX_HOST_LENGTH must reject."""
    long_host = "a" * (ssrf_guard.MAX_HOST_LENGTH + 1) + ".example"
    with pytest.raises(SSRFError):
        validate_outbound_url(f"http://{long_host}/")


def test_url_with_no_host_rejected():
    """A URL with an empty host must reject."""
    with pytest.raises(SSRFError):
        validate_outbound_url("http:///path-only")


# ---------------------------------------------------------------------------
# 8. resolve_and_check direct
# ---------------------------------------------------------------------------


def test_resolve_and_check_empty_host_rejected():
    """``resolve_and_check("")`` must reject without calling DNS."""
    with patch("socket.getaddrinfo") as mock_dns:
        with pytest.raises(SSRFError):
            resolve_and_check("")
        mock_dns.assert_not_called()


def test_resolve_and_check_private_literal_rejected():
    """An IP literal in the block list must reject via the fast path."""
    with patch("socket.getaddrinfo") as mock_dns:
        with pytest.raises(SSRFError):
            resolve_and_check("127.0.0.1")
        mock_dns.assert_not_called()


def test_resolve_and_check_public_literal_accepted():
    """A public IP literal must accept via the fast path."""
    with patch("socket.getaddrinfo") as mock_dns:
        ips = resolve_and_check("8.8.8.8")
        assert ips == ["8.8.8.8"]
        mock_dns.assert_not_called()


def test_resolve_and_check_bracketed_ipv6():
    """Bracketed IPv6 literals work — urlparse strips brackets, fast path engages."""
    with patch("socket.getaddrinfo") as mock_dns:
        with pytest.raises(SSRFError):
            resolve_and_check("::1")
        mock_dns.assert_not_called()


# ---------------------------------------------------------------------------
# 9. Block-list coverage — verify the §3 CIDRs are all in BLOCKED_CIDRS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_cidr",
    [
        # IPv4 — §3 table
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        # IPv6 — §3 table
        "::/128",
        "::1/128",
        "::ffff:0:0/96",
        "64:ff9b::/96",
        "100::/64",
        "2001::/32",
        "2001:db8::/32",
        "2002::/16",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    ],
)
def test_blocked_cidrs_table_complete(expected_cidr: str):
    """Every CIDR in ADR-025 §3 must be present in BLOCKED_CIDRS."""
    expected_net = type(BLOCKED_CIDRS[0])(expected_cidr, strict=False)
    assert any(net == expected_net for net in BLOCKED_CIDRS), (
        f"{expected_cidr} missing from BLOCKED_CIDRS — ADR-025 §3 drift"
    )


# ---------------------------------------------------------------------------
# 10. Generic detail message — no oracle leak
# ---------------------------------------------------------------------------


def test_detail_message_is_generic():
    """The SSRFError ``detail`` must be generic, never echoing the IP/CIDR.

    Per ADR-025 §2: ``detail`` is "URL targets a blocked address range"
    or similar — never echo the blocked IP/CIDR. The exception must not
    become an oracle that lets an attacker enumerate the block list.
    """
    with pytest.raises(SSRFError) as exc_info:
        validate_outbound_url("http://127.0.0.1/")
    msg = str(exc_info.value).lower()
    # Forbidden substrings — anything that would let the attacker
    # learn which rule rejected them.
    assert "127" not in msg
    assert "0.0.0.0" not in msg
    assert "loopback" not in msg
    assert "cidr" not in msg
    # Sanity: the message is still informative.
    assert "blocked" in msg or "address" in msg
