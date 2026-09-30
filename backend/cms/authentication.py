# designed by mew
"""Resolve login client addresses behind the site's single local Nginx proxy."""

from ipaddress import ip_address

from django.conf import settings


def _address(value):
    # Reject forwarding chains, ports, scope identifiers and malformed values.
    if not isinstance(value, str) or "%" in value:
        return None
    try:
        return ip_address(value)
    except ValueError:
        return None


def client_ip(request):
    peer = _address(request.META.get("REMOTE_ADDR"))
    if peer is None:
        return None
    if not settings.DEBUG and peer.is_loopback:
        # Nginx overwrites this header with $remote_addr, never appending client input.
        forwarded = _address(request.META.get("HTTP_X_FORWARDED_FOR"))
        if forwarded is not None:
            return str(forwarded)
    return str(peer)
