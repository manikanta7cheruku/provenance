"""GitHub gateway."""

from pv_config import Settings
from pv_domain.github import GitHubGateway
from pv_github.gateway import HttpGitHubGateway


def oauth_configured(settings: Settings) -> bool:
    """Whether the operator created a GitHub OAuth app. Pasting a link needs none."""
    return bool(settings.github_client_id and settings.github_client_secret.get_secret_value())


def build_gateway(settings: Settings) -> GitHubGateway | None:
    """The real gateway. It always exists: reading public repositories needs no OAuth app. The
    sign-in calls are only used when `oauth_configured` is true."""
    return HttpGitHubGateway(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret.get_secret_value(),
        default_token=settings.github_token.get_secret_value(),
        api_base=settings.github_api_base,
        oauth_base=settings.github_oauth_base,
    )


__all__ = ["HttpGitHubGateway", "build_gateway", "oauth_configured"]
