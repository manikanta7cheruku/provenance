"""Small helpers for reading request facts."""

from fastapi import Request


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
