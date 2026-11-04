"""Which web addresses a person may ask us to read, and which network addresses are safe to reach.

A person can type any address into "Import from a link". That makes this the most dangerous input in
the product (server side request forgery): an address that points at our own network, a cloud
metadata service or a database would be read by a machine that sits inside it. The rules here are
the first of three layers. The others are in the fetch module (names are resolved once, the answer
is checked, and the connection is made to the address that was checked, so a name cannot change its
mind between the check and the connection) and in the network the worker runs in.

Pure code, no network. Every refusal has a short code and a sentence for the person.
"""

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

MAX_URL_CHARS = 500  # the same limit the database holds for a stored link

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# Sites whose terms do not allow automated reading. A person can still paste the description.
PASTE_ONLY_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "wellfound.com",
    "angel.co",
    "glassdoor.com",
)

_BLOCKED_NAMES = ("localhost",)
_BLOCKED_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".lan",
    ".home",
    ".corp",
    ".private",
    ".invalid",
    ".example",
    ".test",
    ".onion",
    ".arpa",
)

# Not "global" by the standard library's rules in every Python version, or reachable in ways the
# plain checks miss: translation prefixes that wrap an IPv4 address, 6to4 and Teredo tunnels.
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(net)
    for net in (
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "2002::/16",
        "2001::/32",
        "100.64.0.0/10",
        "198.18.0.0/15",
        "0.0.0.0/8",
        "240.0.0.0/4",
    )
)

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_NUMERIC_LAST = re.compile(r"^(0x[0-9a-f]+|[0-9]+)$")


class UrlRefused(Exception):
    """An address was refused. code is short and stable, message is for the person."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SafeUrl:
    url: str  # normalised: lower case host, no fragment
    host: str  # ASCII (punycode) host name
    path_and_query: str


def is_public_address(address: IPAddress) -> bool:
    """True only for an address on the public internet.

    Anything private, loopback, link local (including the 169.254.169.254 cloud metadata address),
    multicast, reserved or unspecified is refused, and so is an address that wraps one of those
    (an IPv4 address inside an IPv6 one)."""
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return is_public_address(address.ipv4_mapped)
        if address.sixtofour is not None:
            return False
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or not address.is_global
    ):
        return False
    return not any(address in net for net in _EXTRA_BLOCKED if net.version == address.version)


def _host_of(raw: str) -> str:
    try:
        parts = urlsplit(raw)
        host = parts.hostname
    except ValueError as exc:
        raise UrlRefused("invalid", "That does not look like a web address.") from exc
    if not host:
        raise UrlRefused("invalid", "That does not look like a web address.")
    return host


def check_import_url(raw: str) -> SafeUrl:
    """Accept an address a person typed, or raise UrlRefused.

    Only https, only the standard port, no credentials, only a name that can exist on the public
    internet. Addresses written as numbers (an IP, a decimal or hex form) are refused outright: a
    job posting does not live at one, and these forms are how filters get bypassed."""
    value = (raw or "").strip()
    if not value:
        raise UrlRefused("invalid", "Enter the address of the job posting.")
    if len(value) > MAX_URL_CHARS:
        raise UrlRefused("invalid", f"That address is over {MAX_URL_CHARS} characters.")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise UrlRefused("invalid", "That address contains spaces or hidden characters.")
    if "\\" in value:
        raise UrlRefused("invalid", "That does not look like a web address.")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise UrlRefused("invalid", "That does not look like a web address.") from exc
    if parts.scheme.lower() == "http":
        raise UrlRefused("not_https", "Only secure (https) addresses are used.")
    if parts.scheme.lower() != "https":
        raise UrlRefused("not_https", "Enter an address that starts with https://.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UrlRefused("credentials", "Addresses that contain a user name are not used.")
    if port not in (None, 443):
        raise UrlRefused("port", "Only the standard secure port is used.")

    raw_host = _host_of(value).rstrip(".")
    try:
        host = raw_host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UrlRefused("invalid", "That web address could not be read.") from exc
    labels = host.split(".")
    if len(host) > 253 or not all(_LABEL.match(label) for label in labels):
        # An IPv6 address in brackets lands here too: its host contains colons.
        raise UrlRefused(
            "numeric_host", "Addresses made of numbers are not used. Use the site name."
        )
    if len(labels) < 2 or host in _BLOCKED_NAMES or host.endswith(_BLOCKED_SUFFIXES):
        raise UrlRefused("internal_host", "That address is not on the public internet.")
    if _NUMERIC_LAST.match(labels[-1]):
        raise UrlRefused(
            "numeric_host", "Addresses made of numbers are not used. Use the site name."
        )
    for domain in PASTE_ONLY_DOMAINS:
        if host == domain or host.endswith("." + domain):
            raise UrlRefused(
                "paste_only",
                "This site does not allow automated reading. Open the posting yourself, copy the "
                "description and paste it instead.",
            )

    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return SafeUrl(url=f"https://{host}{path}{query}", host=host, path_and_query=path + query)


def check_resolved(addresses: list[str]) -> list[IPAddress]:
    """The addresses a name resolved to, or UrlRefused when any of them is not public.

    One bad address in the answer is enough to refuse: a name that is allowed to resolve to the
    inside of a network once can do it again, and the connection must not be the one that chooses."""
    parsed: list[IPAddress] = []
    for text in addresses:
        try:
            parsed.append(ipaddress.ip_address(text.split("%", 1)[0]))
        except ValueError:
            continue
    if not parsed:
        raise UrlRefused("dns", "That site name could not be found.")
    if not all(is_public_address(a) for a in parsed):
        raise UrlRefused(
            "private_address", "That address leads to a private network, so it is not read."
        )
    return parsed
