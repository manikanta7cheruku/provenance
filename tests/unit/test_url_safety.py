"""The address rules for "Import from a link": what is refused, and why, before anything is requested."""

import ipaddress

import pytest

from pv_domain.url_safety import (
    PASTE_ONLY_DOMAINS,
    UrlRefused,
    check_import_url,
    check_resolved,
    is_public_address,
)


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "127.0.0.1",
        "127.1.2.3",
        "169.254.169.254",  # the cloud metadata service
        "169.254.0.1",
        "100.64.0.1",  # carrier grade NAT
        "198.18.0.1",
        "0.0.0.0",  # noqa: S104
        "224.0.0.1",
        "240.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "fd12:3456::1",
        "ff02::1",
        "::ffff:127.0.0.1",  # IPv4 inside IPv6
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::7f00:1",  # translation prefix wrapping 127.0.0.1
        "2002:7f00:1::",  # 6to4 wrapping 127.0.0.1
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
    ],
)
def test_private_and_special_addresses_are_not_public(address: str) -> None:
    assert is_public_address(ipaddress.ip_address(address)) is False


@pytest.mark.parametrize(
    "address", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111", "2a00:1450:4001::1"]
)
def test_public_addresses_are_public(address: str) -> None:
    assert is_public_address(ipaddress.ip_address(address)) is True


def test_one_private_address_in_the_answer_refuses_the_name() -> None:
    with pytest.raises(UrlRefused) as refused:
        check_resolved(["93.184.216.34", "10.0.0.5"])
    assert refused.value.code == "private_address"


def test_an_answer_with_only_public_addresses_is_accepted() -> None:
    result = check_resolved(["93.184.216.34", "2606:4700:4700::1111"])
    assert [str(a) for a in result] == ["93.184.216.34", "2606:4700:4700::1111"]


def test_an_empty_answer_is_a_name_that_does_not_exist() -> None:
    with pytest.raises(UrlRefused) as refused:
        check_resolved([])
    assert refused.value.code == "dns"


def test_an_ipv6_zone_suffix_is_not_a_way_around_the_check() -> None:
    with pytest.raises(UrlRefused):
        check_resolved(["fe80::1%eth0"])


def test_a_good_address_is_normalised() -> None:
    safe = check_import_url("  HTTPS://Careers.Example.COM/Jobs/123?utm=x#apply  ")
    assert safe.host == "careers.example.com"
    assert safe.url == "https://careers.example.com/Jobs/123?utm=x"
    assert safe.path_and_query == "/Jobs/123?utm=x"


def test_a_bare_host_gets_a_root_path() -> None:
    assert check_import_url("https://example.org").url == "https://example.org/"


def test_the_standard_port_may_be_written() -> None:
    assert check_import_url("https://example.org:443/x").host == "example.org"


def test_an_international_name_becomes_its_ascii_form() -> None:
    assert check_import_url("https://münchen.de/jobs").host == "xn--mnchen-3ya.de"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "invalid"),
        ("   ", "invalid"),
        ("not a url", "invalid"),
        ("example.com/jobs", "not_https"),
        ("http://example.com/jobs", "not_https"),
        ("ftp://example.com/jobs", "not_https"),
        ("file:///etc/passwd", "not_https"),
        ("javascript:alert(1)", "not_https"),
        ("data:text/html,hello", "not_https"),
        ("gopher://example.com/", "not_https"),
        ("https://user:pass@example.com/", "credentials"),
        ("https://example.com@evil.example/", "credentials"),
        ("https://example.com:8443/", "port"),
        ("https://example.com:22/", "port"),
        ("https://example.com:80/", "port"),
        ("https://localhost/", "internal_host"),
        ("https://LOCALHOST/", "internal_host"),
        ("https://app.localhost/", "internal_host"),
        ("https://printer.local/", "internal_host"),
        ("https://db.internal/", "internal_host"),
        ("https://intranet/", "internal_host"),
        ("https://metadata.google.internal/", "internal_host"),
        ("https://thing.onion/", "internal_host"),
        ("https://127.0.0.1/", "numeric_host"),
        ("https://10.0.0.1/", "numeric_host"),
        ("https://169.254.169.254/latest/meta-data/", "numeric_host"),
        ("https://8.8.8.8/", "numeric_host"),
        ("https://[::1]/", "numeric_host"),
        ("https://[::ffff:127.0.0.1]/", "numeric_host"),
        ("https://[fe80::1]/", "numeric_host"),
        ("https://2130706433/", "internal_host"),  # 127.0.0.1 as one decimal number
        ("https://0x7f000001/", "internal_host"),
        ("https://0x7f.0.0.1/", "numeric_host"),
        ("https://0177.0.0.1/", "numeric_host"),
        ("https://127.1/", "numeric_host"),
        ("https://example.com\\@evil.example/", "invalid"),
        ("https://exa mple.com/", "invalid"),
        ("https://example.com/a\nb", "invalid"),
        ("https://example.com/a\tb", "invalid"),
        ("https://example.com/\x00", "invalid"),
        ("https://" + "a" * 70 + ".com/", "invalid"),
        ("https://-bad.example/", "numeric_host"),
        ("https://exa_mple.example/", "numeric_host"),
        ("https://example.com/" + "a" * 600, "invalid"),
    ],
)
def test_refused_addresses(raw: str, code: str) -> None:
    with pytest.raises(UrlRefused) as refused:
        check_import_url(raw)
    assert refused.value.code == code
    assert refused.value.message  # always a sentence for the person


@pytest.mark.parametrize("domain", PASTE_ONLY_DOMAINS)
def test_sites_that_forbid_automated_reading_are_paste_only(domain: str) -> None:
    for host in (domain, "www." + domain, "uk." + domain):
        with pytest.raises(UrlRefused) as refused:
            check_import_url(f"https://{host}/jobs/view/1")
        assert refused.value.code == "paste_only"
        assert "paste" in refused.value.message.lower()


def test_a_look_alike_name_is_not_treated_as_a_blocked_site() -> None:
    assert check_import_url("https://notlinkedin.com/jobs").host == "notlinkedin.com"
    assert (
        check_import_url("https://linkedin.com.example.org/jobs").host == "linkedin.com.example.org"
    )


def test_the_paste_only_list_covers_every_platform_the_registry_marks_import_only() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    records = json.loads(
        (root / "packages/persistence/src/pv_persistence/registry_data/sources.json").read_text(
            encoding="utf-8"
        )
    )
    import_only = {r["key"] for r in records if r["source_type"] == "user_import_only"}
    # Each import-only platform is named here by its key. If a platform is added to the registry as
    # import only, this list and PASTE_ONLY_DOMAINS must be updated together.
    assert import_only <= {"linkedin", "indeed", "wellfound", "naukri", "glassdoor"}
    for key in import_only & {"linkedin", "indeed", "wellfound"}:
        assert any(key in domain for domain in PASTE_ONLY_DOMAINS)
