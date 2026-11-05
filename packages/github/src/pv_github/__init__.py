"""GitHub gateway."""

from pv_config import Settings
from pv_domain.github import GitHubGateway
from pv_github.gateway import HttpGitHubGateway


def build_gateway(settings: Settings) -> GitHubGateway | None:
    """The real gateway, or None when the operator has not configured an OAuth app."""
    secret = settings.github_client_secret.get_secret_value()
    if not settings.github_client_id or not secret:
        return None
    return HttpGitHubGateway(
        client_id=settings.github_client_id,
        client_secret=secret,
        api_base=settings.github_api_base,
        oauth_base=settings.github_oauth_base,
    )


__all__ = ["HttpGitHubGateway", "build_gateway"]
