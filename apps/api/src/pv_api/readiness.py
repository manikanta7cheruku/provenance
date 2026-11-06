"""Is this deployment safe to put people on? The checks an operator runs before and after a deploy.

`python -m pv_api.cli check-config` prints every check with ok, warning or FAIL and exits 1 when
any is a FAIL. A FAIL is something that makes the deployment unsafe (a placeholder secret, plain
http, an application role that can bypass Row Level Security). A warning is something an owner
should decide (no spend ceiling, no model key). Nothing prints a secret, only whether it is set.

Settings that are invalid cannot be loaded at all, so that is reported as one FAIL with the
reason, and the other checks do not run.
"""

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pv_config import Settings
from pv_persistence.health import check_readiness

OK = "ok"
WARN = "warning"
FAIL = "FAIL"


@dataclass(frozen=True)
class Check:
    name: str
    level: str
    detail: str


def _check(name: str, ok: bool, detail_ok: str, detail_bad: str, bad_level: str = FAIL) -> Check:
    return Check(name, OK if ok else bad_level, detail_ok if ok else detail_bad)


# System tables carry an owner column but belong to no one: the queue is claimed across people
# (ADR-0022). Every other table with an owner column must have Row Level Security enabled and forced.
SYSTEM_TABLES = frozenset({"tasks"})

_DEV_MAIL_HOSTS = ("", "mailpit", "localhost", "127.0.0.1")


def settings_checks(settings: Settings) -> list[Check]:
    production = settings.environment == "production"
    checks = [
        _check(
            "Environment",
            production,
            "ENVIRONMENT is production.",
            f"ENVIRONMENT is {settings.environment!r}. Secure cookies, HSTS and the strict checks below only apply in production.",
        ),
        _check(
            "Public address",
            settings.public_base_url.startswith("https://"),
            "PUBLIC_BASE_URL is https.",
            "PUBLIC_BASE_URL is not https, so cookies and links are not safe.",
        ),
        _check(
            "Allowed origins",
            bool(settings.cors_origin_list)
            and all(o.startswith("https://") for o in settings.cors_origin_list),
            "Every allowed origin is https.",
            "CORS_ORIGINS is empty or has an origin that is not https.",
        ),
        _check(
            "Token encryption keys",
            bool(settings.token_encryption_keys.get_secret_value()),
            "TOKEN_ENCRYPTION_KEYS is set, so connector tokens do not depend on SECRET_KEY.",
            "TOKEN_ENCRYPTION_KEYS is empty. Connector tokens are sealed with a key derived from SECRET_KEY.",
        ),
        _check(
            "Secret key",
            "change-me" not in settings.secret_key.get_secret_value(),
            "SECRET_KEY is not a placeholder.",
            "SECRET_KEY still contains a placeholder.",
        ),
        _check(
            "Mail",
            settings.smtp_host not in _DEV_MAIL_HOSTS,
            "A real mail host is set.",
            "SMTP_HOST is empty or a development mail catcher, so password reset and verification mail will not reach anyone.",
        ),
        _check(
            "Sign-up",
            settings.signup_mode == "invite",
            "Sign-up is by invitation.",
            "Sign-up is open to anyone. That is a decision, not a default.",
            WARN,
        ),
        _check(
            "Model",
            bool(settings.gemini_api_key.get_secret_value() and settings.llm_model),
            "A model key and model name are set.",
            "No model key or name is set, so writing and checking features are off.",
            WARN,
        ),
        _check(
            "Spend ceiling",
            settings.llm_daily_spend_ceiling_usd > 0,
            f"A daily model spend ceiling of ${settings.llm_daily_spend_ceiling_usd:.2f} is set.",
            "No daily model spend ceiling is set, so spend raises no alert.",
            WARN,
        ),
        _check(
            "Verified email",
            settings.email_verification_required,
            "Email verification is required.",
            "Email verification is not required.",
            WARN,
        ),
    ]
    return checks


def storage_checks(settings: Settings) -> list[Check]:
    root = Path(settings.file_storage_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=root, prefix=".check-", delete=True):
            pass
        return [Check("File storage", OK, f"{root} exists and can be written.")]
    except OSError as exc:
        return [Check("File storage", FAIL, f"{root} cannot be written: {type(exc).__name__}.")]


_TENANT_TABLES = text(
    """
    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
      AND EXISTS (
        SELECT 1 FROM information_schema.columns k
        WHERE k.table_schema = 'public' AND k.table_name = c.relname
          AND k.column_name = 'owner_user_id'
      )
    ORDER BY c.relname
    """
)


def database_checks(engine: Engine) -> list[Check]:
    report = check_readiness(engine)
    out = [
        _check(
            "Database", report.database, "The database answers.", "The database does not answer."
        ),
        _check(
            "Migrations",
            report.migrations == "ok",
            "The database matches the code.",
            f"Migrations are {report.migrations}. Run the migration step.",
        ),
    ]
    if not report.database:
        return out
    with engine.connect() as conn:
        super_, bypass = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        tables = conn.execute(_TENANT_TABLES).all()
    out.append(
        _check(
            "Application role",
            not super_ and not bypass,
            "The application role is not a superuser and cannot bypass Row Level Security.",
            "The application role is a superuser or can bypass Row Level Security, so tenant isolation is not enforced.",
        )
    )
    weak = [
        str(name)
        for name, enabled, forced in tables
        if str(name) not in SYSTEM_TABLES and not (enabled and forced)
    ]
    out.append(
        _check(
            "Row Level Security",
            bool(tables) and not weak,
            f"Row Level Security is enabled and forced on all {len(tables) - len(SYSTEM_TABLES)} tables that hold a person's data.",
            "Row Level Security is not enabled and forced on: " + ", ".join(weak)
            if weak
            else "No tenant table was found.",
        )
    )
    return out


def run_checks(
    load_settings: Callable[[], Settings], make_engine: Callable[[Settings], Engine]
) -> list[Check]:
    try:
        settings = load_settings()
    except Exception as exc:  # noqa: BLE001 - invalid settings are reported, not raised
        reason = (
            "; ".join(str(e.get("msg", "")) for e in getattr(exc, "errors", lambda: [])())
            or type(exc).__name__
        )
        return [Check("Settings", FAIL, f"The settings cannot be loaded: {reason}")]
    checks = [Check("Settings", OK, "The settings load and pass their own rules.")]
    checks += settings_checks(settings)
    checks += storage_checks(settings)
    try:
        engine = make_engine(settings)
        checks += database_checks(engine)
    except Exception as exc:  # noqa: BLE001
        checks.append(
            Check("Database", FAIL, f"The database could not be checked: {type(exc).__name__}.")
        )
    return checks


def worst(checks: list[Check]) -> str:
    if any(c.level == FAIL for c in checks):
        return FAIL
    return WARN if any(c.level == WARN for c in checks) else OK
