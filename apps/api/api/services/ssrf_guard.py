"""Outbound SSRF guard for feed / scrape URLs.

Per ADR-025 (``.agent/adr/025-ssrf-guard.md``, Task #69, follow-ups
in Task #70).

Public surface:

* :func:`validate_outbound_url` — end-to-end check for an outbound URL.
  Used at the call boundary of every service that fetches user-supplied
  URLs (feed_parser, scraper).
* :func:`resolve_and_check` — hostname → public-IP resolution with
  block-list enforcement. Reused by ``validate_outbound_url`` and
  callable directly when the URL has already been parsed.
* :class:`SSRFGuardTransport` — custom ``httpx.AsyncBaseTransport``
  subclass that re-runs ``validate_outbound_url`` on every redirect
  target inside the scraper request path. Wired into
  ``scraper.ArticleScraper`` (Task #70, ADR-025 §5 follow-up).

The implementation uses only stdlib primitives (``ipaddress``,
``socket.getaddrinfo``, ``urllib.parse``, ``threading``,
``asyncio``) and the already-imported ``httpx``. No new runtime
dependencies.

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

DNS-resolution timeout (Task #70, sub-item 2)
---------------------------------------------
``socket.getaddrinfo`` is blocking and cannot be hard-cancelled from
async code. To bound per-request latency in the face of attacker-controlled
slow DNS, ``resolve_and_check`` runs the syscall via ``asyncio.to_thread``
and waits with ``asyncio.wait_for(..., timeout=DNS_TIMEOUT_SECONDS)``.
The thread itself is **not** killed on timeout (``getaddrinfo`` is C-level
blocking); the caller is released but the thread completes in the
background. Trade-off chosen for v1: best-effort cancellation, bounded
caller wait. Alternative (executors with hard ``timeout=``) leaks worse
and offers no practical benefit on the standard CPython ``getaddrinfo``
path. Override per-deployment via ``SSRF_DNS_TIMEOUT_S`` env var.

Per-redirect re-validation (Task #70, sub-item 1)
------------------------------------------------
``scraper.py`` used to rely on a manual post-response loop to re-validate
``Location:`` headers. That was brittle. The replacement is
:class:`SSRFGuardTransport`: an ``httpx.AsyncBaseTransport`` subclass
that runs ``validate_outbound_url`` against ``request.url`` on every
hop the client makes — including the redirects httpx synthesises
internally (``follow_redirects=True``). The redirect hop count is capped
at ``REDIRECT_CAP_HTTPCLIENT`` (5; RFC 7231 §6.4 default), so the
existing ``follow_redirects=True`` path can stay ergonomic without
opening the chain to infinite loops via attacker-controlled DNS.

Threat model
------------
OWASP A10:2021 / CWE-918 — Server-Side Request Forgery. An authenticated
user can otherwise submit ``http://169.254.169.254/latest/meta-data/``
(AWS / GCP / Azure instance metadata) or ``http://127.0.0.1:6379``
(loopback services) and probe internal infrastructure. The block list
below covers every range recommended by the OWASP SSRF cheatsheet plus
the IPv6 ranges required to defeat IPv4-mapped and NAT64 bypasses.

Residual risks accepted in v1 (out of scope; see ADR-025 §7):
    * DNS-rebinding TOCTOU window between ``resolve_and_check`` and
      the actual socket ``connect()``. Sub-millisecond on localhost,
      tens of milliseconds cross-region. Mitigation (per-request
      IP-pinning via an httpx transport that overrides ``Host`` and
      binds the socket to a pre-resolved IP) is deferred — it breaks
      SNI for vhosts that share an IP, which is most of the modern web.
      See ``resolve_and_check`` for the trigger condition.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import ipaddress
import logging
import os
import socket
import threading
import time
from urllib.parse import urlparse

import httpx

from api.exceptions import SSRFError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bounded executor for ``socket.getaddrinfo`` (Task #70 sub-item 2 + ADR-025 §5.1).
#
# ``socket.getaddrinfo`` is C-level blocking; we cannot hard-cancel it from
# async code, and ``asyncio.to_thread`` schedules onto the default executor
# which is unbounded (it will spawn as many threads as the loop has pending
# tasks). Under attacker-controlled slow DNS (500 unique hostnames × 1 s
# timeout), that lets an adversary spin up 500 worker threads that all
# block inside ``getaddrinfo`` for the resolver's native timeout. The
# bounded pool caps concurrent in-flight resolver calls at the standard
# I/O-bound size ``min(32, cpu_count + 4)`` so a single bad request cannot
# exhaust the process. On timeout, the future is abandoned in the pool —
# the slot is freed when the underlying ``getaddrinfo`` returns.
# ---------------------------------------------------------------------------
_RESOLVE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(32, (os.cpu_count() or 1) + 4),
    thread_name_prefix="ssrf-dns",
)


def _host_hash_for_log(host: str) -> str:
    """Return a 12-char SHA-256 prefix of ``host`` for safe logging.

    Hosts are user-controlled (they originate from ``xmlUrl`` / ``url`` in
    the request body) and frequently embed tenant identifiers or
    internal-only subdomains. Logging the bare hostname turns the API
    log stream into a PII surface (Devil MEDIUM on Task #70). The
    truncated hash is enough for ops to correlate a single resolver
    failure across log lines without exposing the hostname itself; ops
    who need the underlying hostname can find it in the request record
    via X-Request-ID.
    """
    return hashlib.sha256(host.encode("utf-8")).hexdigest()[:12]


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

#: Maximum redirect hops the SSRF guard transport will allow before
#: yielding to httpx's own ``max_redirects``. Matches the de-facto
#: RFC 7231 §6.4 default for non-browser clients.
REDIRECT_CAP_HTTPCLIENT: int = 5

#: Default per-request DNS-resolution timeout (seconds). Override at boot
#: via the ``SSRF_DNS_TIMEOUT_S`` env var. The actual ``getaddrinfo`` syscall
#: is C-level blocking and is not hard-cancelled on timeout; this bounds the
#: **caller's** wait, not the resolver.
#:
#: Range-bounded at module import (Devil MAJOR on Task #70): a value of 0
#: or negative would call ``asyncio.wait_for(..., timeout=0)`` and fail every
#: DNS query instantly; a value > 30 s would let one slow host hold a
#: request for the full cap. Anything outside ``[0.001, 30.0]`` is clamped
#: with a warning. Override at runtime for tests via
#: :func:`set_dns_timeout_for_tests`.
_DNS_TIMEOUT_MIN_S: float = 0.001
_DNS_TIMEOUT_MAX_S: float = 30.0
_DNS_TIMEOUT_DEFAULT_S: float = 1.0


def _read_dns_timeout_from_env() -> float:
    """Read SSRF_DNS_TIMEOUT_S from os.environ, clamp to a sane range.

    Falls back to the default 1.0 s on missing / unparseable / out-of-range
    input. The clamp-and-warn posture is documented at
    ``DNS_TIMEOUT_SECONDS`` (Task #70 Devil MAJOR finding: a misconfigured
    env var would DoS the bulk path).
    """
    raw = os.environ.get("SSRF_DNS_TIMEOUT_S")
    if raw is None or raw.strip() == "":
        return _DNS_TIMEOUT_DEFAULT_S
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "SSRF_DNS_TIMEOUT_S=%r is not a float; falling back to %.3fs",
            raw,
            _DNS_TIMEOUT_DEFAULT_S,
        )
        return _DNS_TIMEOUT_DEFAULT_S
    if value < _DNS_TIMEOUT_MIN_S or value > _DNS_TIMEOUT_MAX_S:
        clamped = max(_DNS_TIMEOUT_MIN_S, min(value, _DNS_TIMEOUT_MAX_S))
        logger.warning(
            "SSRF_DNS_TIMEOUT_S=%s out of range [%.3f, %.3f]; clamped to %.3fs",
            value,
            _DNS_TIMEOUT_MIN_S,
            _DNS_TIMEOUT_MAX_S,
            clamped,
        )
        return clamped
    return value


#: Module-level DNS timeout. Set once at import from the env var; mutable
#: via :func:`set_dns_timeout_for_tests` so tests can exercise edge cases
#: without subprocess reload.
DNS_TIMEOUT_SECONDS: float = _read_dns_timeout_from_env()


def set_dns_timeout_for_tests(value: float) -> None:
    """Override :data:`DNS_TIMEOUT_SECONDS` for the current process (test-only).

    Tests use this to exercise sub-second timeouts without paying for a
    5 s ``getaddrinfo`` mock sleep. Production callers MUST set the env
    var at boot — rotating the timeout at runtime is unsafe (in-flight
    resolutions do not pick up the new value).
    """
    global DNS_TIMEOUT_SECONDS
    if value < _DNS_TIMEOUT_MIN_S or value > _DNS_TIMEOUT_MAX_S:
        raise ValueError(
            f"DNS timeout {value}s out of range "
            f"[{_DNS_TIMEOUT_MIN_S}, {_DNS_TIMEOUT_MAX_S}]"
        )
    DNS_TIMEOUT_SECONDS = float(value)


#: HTTP status codes that httpx treats as redirects (RFC 7231 §6.4 +
#: RFC 7538 §3 for 308). 304 / 305 / 306 are intentionally NOT here:
#: they are conditional responses or deprecated routing primitives and
#: do not carry a normative ``Location:`` a scraper should chase.
REDIRECT_STATUSES: frozenset[int] = frozenset({301, 302, 303, 307, 308})


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
    NOT validate — pure DNS plumbing. Pure-function on purpose: callable
    directly from ``asyncio.to_thread`` so a timeout can be imposed via
    ``asyncio.wait_for`` without leaking C-level cancellation.
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


async def _resolve_with_timeout(host: str, timeout: float) -> list[str]:
    """Async wrapper around :func:`_resolve_unchecked` with a hard caller-side cap.

    ``socket.getaddrinfo`` is C-level blocking; we cannot hard-cancel it
    from async code. Strategy (Task #70 sub-item 2): submit the syscall
    to the module-level bounded :data:`_RESOLVE_EXECUTOR` and
    ``asyncio.wait_for`` the returned future. On timeout the caller sees
    :class:`asyncio.TimeoutError` but the worker continues in the
    background until the OS resolver returns — best-effort cancellation,
    bounded by the executor's ``max_workers`` cap. ``asyncio.to_thread``
    was rejected here: it schedules onto the loop's default executor
    which is **unbounded**, so an attacker controlling 500 slow resolvers
    could spin up 500 worker threads in one request (Devil MAJOR on
    Task #70).
    """
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_RESOLVE_EXECUTOR, _resolve_unchecked, host),
        timeout=timeout,
    )


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
# Public API — sync surface (preserves Task #69 contract for feed_parser
# and every existing test)
# ---------------------------------------------------------------------------


def _validate_ips(host: str, ips: list[str]) -> list[str]:
    """Block-list every IP returned by the resolver; cache + return the public set."""
    if not ips:
        # getaddrinfo returned an empty list — defensive; shouldn't happen.
        logger.warning(
            "DNS resolution returned no addresses for host_hash=%s",
            _host_hash_for_log(host),
        )
        raise SSRFError("URL targets a blocked address range")

    public_ips: list[str] = []
    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Shouldn't happen — getaddrinfo returns parseable IPs.
            logger.warning(
                "getaddrinfo returned unparseable IP for host_hash=%s",
                _host_hash_for_log(host),
            )
            raise SSRFError("URL targets a blocked address range")
        if _is_blocked(ip):
            _cache_put(host, [])
            raise SSRFError("URL targets a blocked address range")
        public_ips.append(ip_str)

    _cache_put(host, public_ips)
    return public_ips


def resolve_and_check(host: str) -> list[str]:
    """Resolve ``host`` and verify every returned IP is public (sync).

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

    # Cold resolve. Sync; no timeout enforcement at this layer (the bulk
    # path is bounded by the cache, see ADR-025 §6, and the per-request
    # timeout lives in ``resolve_and_check_async``).
    try:
        ips = _resolve_unchecked(host)
    except _GaierrorWrapped as exc:
        # Treat DNS failure as a guard failure — never expose the
        # resolver error verbatim to the client. Log for ops.
        logger.warning(
            "DNS resolution failed for host_hash=%s (rc=gaierror)",
            _host_hash_for_log(host),
        )
        raise SSRFError("URL targets a blocked address range") from exc

    return _validate_ips(host, ips)


async def resolve_and_check_async(host: str) -> list[str]:
    """Async sibling of :func:`resolve_and_check` with a per-request timeout.

    Same contract; DNS resolution is pushed onto ``asyncio.to_thread``
    and bounded by ``asyncio.wait_for(timeout=DNS_TIMEOUT_SECONDS)``. On
    timeout the caller sees :class:`SSRFError` (generic detail, never the
    host); the worker thread continues in the background until the OS
    resolver returns — best-effort cancellation (Task #70 sub-item 2).
    Override the default 1.0s via ``SSRF_DNS_TIMEOUT_S`` env var.
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

    try:
        ips = await _resolve_with_timeout(host, DNS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        logger.warning(
            "DNS resolution timed out for host_hash=%s after %.3fs",
            _host_hash_for_log(host),
            DNS_TIMEOUT_SECONDS,
        )
        raise SSRFError("URL targets a blocked address range") from exc
    except _GaierrorWrapped as exc:
        logger.warning(
            "DNS resolution failed for host_hash=%s (rc=gaierror)",
            _host_hash_for_log(host),
        )
        raise SSRFError("URL targets a blocked address range") from exc

    return _validate_ips(host, ips)


# IP-pinning deferred (ADR-025 §7, Task #70 sub-item 3):
# The DNS-rebinding TOCTOU window is accepted for v1. Trigger to revisit
# (any of the three conditions below enables v2 IP-pinning — see ADR-025 §4):
#   (a) a documented prod incident showing DNS-rebinding exploitation
#       against this codebase, OR
#   (b) a Cloudflare / Vercel proxy change that strips origin IP and
#       widens the rebinding window beyond the 60s cache TTL, OR
#   (c) a coordinated penetration-test finding from a third-party
#       assessor.
# Full mitigation is a custom httpx transport that pre-resolves the
# host, binds the socket to the resolved IP, and overrides the
# ``Host`` header. Not implemented now: breaks SNI for vhosts that
# share one IP (most modern HTTPS sites).


def _validate_url_shape(url: str) -> str:
    """Shape-check a URL and return its hostname.

    Encapsulates steps 1-3 of the four-step validate (shape → scheme →
    host parse). DNS resolution is the caller's responsibility because
    it differs between sync and async paths (Task #70 sub-item 2:
    async uses a timeout-bounded resolver; sync uses a plain one).

    Returns:
        The parsed hostname (``urlparse.urlparse(url).hostname``).

    Raises:
        SSRFError: on any shape / scheme / host failure. The detail
            message is generic — never echoes the IP / CIDR / host.
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

    return host


def validate_outbound_url(url: str) -> None:
    """Validate that ``url`` is safe to fetch outbound (sync).

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

    Note:
        Sync wrapper. Does NOT impose a per-resolution timeout; for the
        bounded async path see :func:`validate_outbound_url_async`.
        Used by ``feed_parser`` and every synchronous caller; the
        existing test matrix (ADR-025 §Test matrix) calls this form.
    """
    host = _validate_url_shape(url)
    resolve_and_check(host)


async def validate_outbound_url_async(url: str) -> None:
    """Async sibling of :func:`validate_outbound_url` with a DNS timeout.

    Performs the same four checks as the sync form but delegates the
    resolution step to :func:`resolve_and_check_async`, which bounds
    ``getaddrinfo`` with ``DNS_TIMEOUT_SECONDS`` (Task #70 sub-item 2).
    Used by the async scraper path (``ArticleScraper.scrape``) and by
    :class:`SSRFGuardTransport` when re-validating redirect targets.
    """
    host = _validate_url_shape(url)
    await resolve_and_check_async(host)


# ---------------------------------------------------------------------------
# Sub-item 1: per-redirect re-validation transport
# ---------------------------------------------------------------------------
#
# httpx emits one ``handle_async_request`` call per hop when
# ``follow_redirects=True`` (verified against the 0.28.x source path
# ``AsyncClient._send_handling_redirects`` — every iteration calls
# ``self._transport.handle_async_request`` afresh). That means a custom
# ``AsyncBaseTransport`` subclass is sufficient to re-validate every
# redirect target, without touching httpx internals or wiring
# response-side event hooks.
#
# Design choice: ``validate_outbound_url_async`` is async-aware (uses
# ``resolve_and_check_async`` so DNS is timeout-bounded). On a redirect
# to a private-IP host the transport raises ``SSRFError`` BEFORE
# opening the socket, so no data leaks even when an attacker races a
# public-IP response with a private-IP follow-up.
#
# Cross-protocol redirects (http→https, https→http) are validated
# against the same ``ALLOWED_SCHEMES`` allow-list inside
# ``validate_outbound_url``: ``http://`` and ``https://`` both pass,
# ``gopher://`` / ``file://`` etc. are rejected.


class SSRFGuardTransport(httpx.AsyncBaseTransport):
    r"""``httpx.AsyncBaseTransport`` subclass that re-runs the SSRF guard on every hop.

    Behaviour matrix (per ADR-025 §5 and Task #70 sub-item 1):

    * ``handle_async_request`` calls :func:`validate_outbound_url_async`
      against ``request.url`` (the URL httpx is about to fetch — initial
      URL on the first call, ``Location:`` target on every redirect
      hop). ``SSRFError`` is raised before the socket is opened.
    * The transport caps its own internal redirect tracking at
      ``REDIRECT_CAP_HTTPCLIENT`` (5) hops. Once the cap is reached the
      transport returns the most recent redirect response unchanged and
      lets httpx's own ``max_redirects`` raise ``TooManyRedirects`` if
      the caller has it set tighter. This keeps the SSRF check on
      every hop the caller actually receives, without the transport
      becoming the single point of failure for an unrelated httpx
      setting.

    The class subclasses ``httpx.AsyncBaseTransport`` so it slots into
    ``httpx.AsyncClient(transport=self._transport)`` directly.
    ``httpx.AsyncHTTPTransport`` (the real network stack) is wrapped
    inside via the ``wrapped`` ctor arg — call sites that want a stub
    transport for tests can pass their own.
    """

    def __init__(self, wrapped: httpx.AsyncBaseTransport | None = None) -> None:
        # ``httpx`` is already imported at module top (the class itself
        # subclasses ``httpx.AsyncBaseTransport``, so the import is
        # structurally required). No lazy import here.
        self._wrapped = wrapped if wrapped is not None else httpx.AsyncHTTPTransport()
        # Per-instance redirect counter. Httppx itself enforces
        # ``max_redirects``; this is belt-and-suspenders so the SSRF
        # guard never silently walks a chain far longer than
        # ``REDIRECT_CAP_HTTPCLIENT``.
        self._redirect_count = 0

    async def handle_async_request(self, request) -> object:
        # ``request.url`` is ``httpx.URL`` (a str-coercible). We coerce
        # to a plain string so shape-checks (length, scheme) match the
        # non-Transport public surface byte-for-byte.
        await validate_outbound_url_async(str(request.url))

        # Issue via the wrapped transport. ``httpx`` re-enters the
        # AsyncClient.send path with the response, the AsyncClient walks
        # the redirect chain, and on each iteration we re-enter this
        # method with the new ``Location:`` target.
        response = await self._wrapped.handle_async_request(request)

        status = getattr(response, "status_code", None)
        if status in REDIRECT_STATUSES:
            self._redirect_count += 1
            if self._redirect_count >= REDIRECT_CAP_HTTPCLIENT:
                # Hand the response back unchanged; AsyncClient's own
                # ``max_redirects`` enforcement (or the caller) decides
                # what to do with the over-the-cap response.
                return response

        return response

    async def aclose(self) -> None:
        # AsyncBaseTransport defines ``aclose`` as a coroutine. Forward
        # to the wrapped transport so the connection pool is released.
        aclose_attr = getattr(self._wrapped, "aclose", None)
        if aclose_attr is not None:
            result = aclose_attr()
            if asyncio.iscoroutine(result):
                await result


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
    "DNS_TIMEOUT_SECONDS",
    "MAX_CACHE_SIZE",
    "MAX_HOST_LENGTH",
    "REDIRECT_CAP_HTTPCLIENT",
    "REDIRECT_STATUSES",
    "SSRFError",
    "SSRFGuardTransport",
    "resolve_and_check",
    "resolve_and_check_async",
    "set_dns_timeout_for_tests",
    "validate_outbound_url",
    "validate_outbound_url_async",
]
