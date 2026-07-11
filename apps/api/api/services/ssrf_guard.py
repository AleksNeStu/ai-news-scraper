"""Outbound SSRF guard for feed / scrape URLs.

Per ADR-025 (``.agent/adr/025-ssrf-guard.md``, Task #69).

Two public functions:

* :func:`validate_outbound_url` — end-to-end check for an outbound URL.
  Used at the call boundary of every service that fetches user-supplied
  URLs (feed_parser, scraper).
* :func:`resolve_and_check` — hostname → public-IP resolution with
  block-list enforcement. Reused by ``validate_outbound_url`` and
  callable directly when the URL has already been parsed.

The implementation uses only stdlib primitives (``ipaddress``,
``socket.getaddrinfo``, ``urllib.parse``, ``threading``). No new
runtime dependencies.

Cache
----
Per-process DNS cache keyed on hostname with a 60-second TTL. The
bulk-import path (``POST /feeds/bulk``, ``POST /scrape/batch``) accepts
up to 500 URLs per request; without the cache, each URL would trigger a
fresh ``getaddrinfo`` call — a real attacker-controlled DNS-amplification
vector (see ADR-025 §6). The cache is intentionally per-process:
multi-worker deployments see N × DNS queries per cache key, but the
goal is to bound per-request amplification, not deduplicate across
workers.

The cache is bounded by ``MAX_CACHE_SIZE`` entries; oldest insertion is
evicted when the cap is exceeded. This is in addition to the TTL — both
mechanisms bound memory pressure. ``functools.lru_cache`` is not used
because (a) it has no TTL support and (b) the helper would need a
``time.monotonic()`` arg anyway, which ``lru_cache`` hashes awkwardly.

Threat model
------------
OWASP A10:2021 / CWE-918 — Server-Side Request Forgery. An authenticated
user can otherwise submit ``http://169.254.169.254/latest/meta-data/``
(AWS / GCP / Azure instance metadata) or ``http://127.0.0.1:6379``
(loopback services) and probe internal infrastructure. The block list
below covers every range recommended by the OWASP SSRF cheatsheet plus
the IPv6 ranges required to defeat IPv4-mapped and NAT64 bypasses.

Residual risks accepted in v1 (out of scope; see ADR-025 §7):
    * DNS-rebinding TOCTOU window between ``validate_outbound_url`` and
      the actual socket ``connect()``. Sub-millisecond on localhost,
      tens of milliseconds cross-region.
    * Per-redirect re-validation (httpx has no native hook; requires a
      custom Transport).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from urllib.parse import urlparse

from api.exceptions import SSRFError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants — exposed for tests + documentation
# ---------------------------------------------------------------------------

#: HTTP(S) only. ``file:``, ``gopher:``, ``ftp:``, ``data:``, ``javascript:``,
#: ``dict:``, ``ldap:``, ``imap:``, ``smtp:`` are all rejected.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: Max hostname length per RFC 1035 (253 octets). DNS resolvers and
#: urlparse both tolerate slightly longer strings, but anything beyond
#: this is a probe attempt.
MAX_HOST_LENGTH: int = 253

#: 60s TTL per ADR-025 §6. Bounds both per-request DNS amplification
#: and stale-resolution risk.
CACHE_TTL_SECONDS: float = 60.0

#: LRU cap on the per-process resolution cache. Memory pressure is
#: bounded by both TTL and this cap.
MAX_CACHE_SIZE: int = 4096


# ---------------------------------------------------------------------------
# Block list — every entry has a comment so the rationale is auditable.
# ---------------------------------------------------------------------------

_BLOCKED_IPV4_CIDRS: tuple[str, ...] = (
    "0.0.0.0/8",  # "This host on this network" — RFC 1122
    "10.0.0.0/8",  # RFC 1918 private
    "100.64.0.0/10",  # CGNAT shared address space — RFC 6598
    "127.0.0.0/8",  # Loopback
    "169.254.0.0/16",  # Link-local — incl. AWS/GCP/Azure metadata at 169.254.169.254
    "172.16.0.0/12",  # RFC 1918 private
    "192.0.0.0/24",  # IETF protocol assignments
    "192.0.2.0/24",  # TEST-NET-1
    "192.168.0.0/16",  # RFC 1918 private
    "198.18.0.0/15",  # Benchmark testing
    "198.51.100.0/24",  # TEST-NET-2
    "203.0.113.0/24",  # TEST-NET-3
    "224.0.0.0/4",  # Multicast
    "240.0.0.0/4",  # Reserved (includes 255.255.255.255 broadcast)
)

_BLOCKED_IPV6_CIDRS: tuple[str, ...] = (
    "::/128",  # Unspecified
    "::1/128",  # Loopback
    "::ffff:0:0/96",  # IPv4-mapped — catches ::ffff:127.0.0.1
    "64:ff9b::/96",  # IPv4-IPv6 translation (RFC 6052 / NAT64)
    "100::/64",  # Discard prefix (RFC 6666)
    "2001::/32",  # Teredo tunneling
    "2001:db8::/32",  # Documentation
    "2002::/16",  # 6to4 (RFC 3056) — wraps IPv4 in IPv6 to bypass IPv4 blocks
    "fc00::/7",  # Unique local address (ULA)
    "fe80::/10",  # Link-local
    "ff00::/8",  # Multicast
)


def _build_blocked_cidrs() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse every CIDR string in the block list into network objects.

    Done once at module import. ``strict=False`` so 169.254.0.0/16 with
    a host bit set still parses (some entries like 169.254.169.254/32
    are intentionally tight).
    """
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in _BLOCKED_IPV4_CIDRS + _BLOCKED_IPV6_CIDRS:
        nets.append(ipaddress.ip_network(cidr, strict=False))
    return tuple(nets)


#: Frozen tuple of every blocked network. Walked once per resolved IP;
#: ~25 entries, so the linear scan is fine.
BLOCKED_CIDRS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    _build_blocked_cidrs()
)


# ---------------------------------------------------------------------------
# DNS resolution cache — bounded, TTL-aware, thread-safe
# ---------------------------------------------------------------------------

#: ``host -> (inserted_at_monotonic, [public_ip_str, ...])``. ``public_ip_str``
#: is the list of IPs the host resolved to that PASSED the block-list check.
#: If the host resolved but every IP was blocked, we still cache the
#: decision (empty list) so a probing retry doesn't cause more DNS traffic.
_RESOLUTION_CACHE: dict[str, tuple[float, list[str]]] = {}
_CACHE_LOCK = threading.Lock()


def _is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if ``ip`` falls in any block-list network."""
    for net in BLOCKED_CIDRS:
        if ip.version != net.version:
            # ``ipaddress.ip_network`` is family-specific. Skip mismatches
            # rather than letting IPv4 leak into an IPv6 CIDR.
            continue
        if ip in net:
            return True
    return False


def _resolve_unchecked(host: str) -> list[str]:
    """Call ``socket.getaddrinfo`` and return a flat list of IP strings.

    Uses ``SOCK_STREAM`` so we get the addresses the OS would actually
    use for an HTTP(S) connection. Does NOT consult the cache and does
    NOT validate — pure DNS plumbing.
    """
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise _GaierrorWrapped(str(exc)) from exc
    # ``getaddrinfo`` returns one tuple per (family, socktype, proto, canonname, sockaddr).
    # We only care about the IP part of ``sockaddr``.
    out: list[str] = []
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        out.append(ip_str)
    return out


class _GaierrorWrapped(Exception):
    """Internal wrapper so the public API only surfaces ``SSRFError``."""


def _cache_get(host: str) -> list[str] | None:
    """Return cached IPs for ``host`` if fresh, else None. Acquires lock."""
    with _CACHE_LOCK:
        entry = _RESOLUTION_CACHE.get(host)
        if entry is None:
            return None
        inserted_at, ips = entry
        if (time.monotonic() - inserted_at) >= CACHE_TTL_SECONDS:
            return None
        # Return a copy so the caller can't mutate the cached value.
        return list(ips)


def _cache_put(host: str, ips: list[str]) -> None:
    """Insert into cache. Evicts oldest entry if at capacity. Acquires lock."""
    with _CACHE_LOCK:
        # Evict when at capacity and the key is new. If the key is already
        # cached we just refresh the timestamp.
        if host not in _RESOLUTION_CACHE and len(_RESOLUTION_CACHE) >= MAX_CACHE_SIZE:
            # Pop the oldest insertion (insertion-ordered dict since 3.7).
            oldest_host = next(iter(_RESOLUTION_CACHE))
            _RESOLUTION_CACHE.pop(oldest_host, None)
        _RESOLUTION_CACHE[host] = (time.monotonic(), list(ips))


def _cache_clear_for_tests() -> None:
    """Drop the entire cache. Test-only helper."""
    with _CACHE_LOCK:
        _RESOLUTION_CACHE.clear()


# ---------------------------------------------------------------------------
# IP-literal fast path
# ---------------------------------------------------------------------------


def _check_ip_literal(host: str) -> list[str] | None:
    """If ``host`` parses as an IP literal, validate it.

    Returns:
        ``["ip_str"]`` if the literal is public (caller can proceed).
        ``[]`` if the literal is blocked (caller must reject).
        ``None`` if ``host`` is not an IP literal (caller must resolve).

    Bracketed literals (e.g. ``[::1]``) are accepted; the brackets are
    stripped by ``urlparse`` before this is called.
    """
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    if _is_blocked(ip):
        return []
    return [host]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_and_check(host: str) -> list[str]:
    """Resolve ``host`` and verify every returned IP is public.

    Args:
        host: A hostname or IP literal. Bracketed IPv6 literals
            (``[::1]``) must have their brackets stripped by the caller
            (``urlparse`` does this automatically).

    Returns:
        A list of public IP strings the host resolved to. The list may
        be empty if every returned IP was blocked (still a cache hit
        so the decision is stable for 60s).

    Raises:
        SSRFError: if ``host`` is empty, if DNS resolution fails, or if
            any returned IP is in the block list.
    """
    if not host:
        raise SSRFError("URL targets a blocked address range")

    # IP literal — skip the DNS round-trip entirely.
    literal_result = _check_ip_literal(host)
    if literal_result is not None:
        if not literal_result:
            raise SSRFError("URL targets a blocked address range")
        return literal_result

    # Hostname — consult the cache first.
    cached = _cache_get(host)
    if cached is not None:
        if not cached:
            raise SSRFError("URL targets a blocked address range")
        return cached

    # Cold resolve.
    try:
        ips = _resolve_unchecked(host)
    except _GaierrorWrapped as exc:
        # Treat DNS failure as a guard failure — never expose the
        # resolver error verbatim to the client. Log for ops.
        logger.warning("DNS resolution failed for host=%s: %s", host, exc)
        raise SSRFError("URL targets a blocked address range") from exc

    if not ips:
        # getaddrinfo returned an empty list — defensive; shouldn't happen.
        logger.warning("DNS resolution returned no addresses for host=%s", host)
        raise SSRFError("URL targets a blocked address range")

    # Validate every IP. If any is blocked, reject the whole host.
    public_ips: list[str] = []
    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Shouldn't happen — getaddrinfo returns parseable IPs.
            logger.warning(
                "getaddrinfo returned unparseable IP for host=%s: %r",
                host,
                ip_str,
            )
            raise SSRFError("URL targets a blocked address range")
        if _is_blocked(ip):
            _cache_put(host, [])
            raise SSRFError("URL targets a blocked address range")
        public_ips.append(ip_str)

    _cache_put(host, public_ips)
    return public_ips


def validate_outbound_url(url: str) -> None:
    """Validate that ``url`` is safe to fetch outbound.

    Performs four checks, in order:

    1. **Shape**: not empty / whitespace-only, and not absurdly long
       (> 4096 chars).
    2. **Scheme**: in ``ALLOWED_SCHEMES``.
    3. **Host parse**: ``urlparse`` produces a non-empty hostname of
       acceptable length.
    4. **Resolution**: every IP the host resolves to is public
       (see :func:`resolve_and_check`).

    Args:
        url: The full outbound URL.

    Raises:
        SSRFError: on any failure. The ``detail`` message is generic
            ("URL targets a blocked address range") so the error cannot
            be used as an oracle to enumerate the block list.
    """
    if not url or not url.strip():
        raise SSRFError("URL targets a blocked address range")
    if len(url) > 4096:
        raise SSRFError("URL targets a blocked address range")

    parsed = urlparse(url)

    # Scheme: allow-list. ``urlparse`` lowercases the scheme, so this
    # comparison is case-insensitive in practice.
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFError("URL targets a blocked address range")

    host = parsed.hostname
    if not host:
        raise SSRFError("URL targets a blocked address range")
    if len(host) > MAX_HOST_LENGTH:
        raise SSRFError("URL targets a blocked address range")

    # Hostname sanity: reject hosts that are entirely digits (decimal IP
    # like ``http://2130706433`` is rejected by ``ipaddress.ip_address``
    # above; this is a belt-and-suspenders check for octal/hex forms
    # that Python's parser doesn't accept).
    if host.isdigit():
        # Pure-digit hostname — try ip_address strict; if it parses, the
        # block-list check below catches it; if it doesn't parse, reject.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise SSRFError("URL targets a blocked address range")

    # Delegate the actual IP check. ``resolve_and_check`` raises SSRFError
    # on any block-list hit, DNS failure, or empty hostname.
    resolve_and_check(host)


# ---------------------------------------------------------------------------
# ``SSRFError`` is imported from ``api.exceptions`` at the top of the
# module. It is a ``ValidationError`` subclass so the existing RFC 7807
# handler matrix picks it up unchanged — the client sees
# ``status=400`` and ``error_code="ssrf_blocked"``.
# ---------------------------------------------------------------------------


__all__ = [
    "ALLOWED_SCHEMES",
    "BLOCKED_CIDRS",
    "CACHE_TTL_SECONDS",
    "MAX_CACHE_SIZE",
    "MAX_HOST_LENGTH",
    "SSRFError",
    "resolve_and_check",
    "validate_outbound_url",
]
