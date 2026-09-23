import hashlib
from ipaddress import ip_address

from fastapi import Request


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def get_client_ip(request: Request, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for", "").split(",", maxsplit=1)[0]
        forwarded_ip = _valid_ip(forwarded_for)
        if forwarded_ip:
            return forwarded_ip

        real_ip = _valid_ip(request.headers.get("x-real-ip"))
        if real_ip:
            return real_ip

    if request.client:
        direct_ip = _valid_ip(request.client.host)
        if direct_ip:
            return direct_ip

    return "unavailable"


def hash_client_ip(client_ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{client_ip}".encode("utf-8")).hexdigest()

