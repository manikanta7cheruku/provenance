from collections.abc import Callable

from pv_api.mail import LogMailer, SmtpMailer, build_mailer
from pv_config import Settings

Make = Callable[..., Settings]


def test_log_mailer_is_used_without_smtp_host(make_settings: Make) -> None:
    assert isinstance(build_mailer(make_settings()), LogMailer)


def test_smtp_mailer_is_used_with_smtp_host(make_settings: Make) -> None:
    assert isinstance(build_mailer(make_settings(smtp_host="mailpit", smtp_port=1025)), SmtpMailer)
