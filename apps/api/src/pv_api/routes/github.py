"""The GitHub connection. Every route is scoped to the signed-in person.

The sign-in is two calls from the browser, both same-origin and both with the session and the CSRF
token: `start` returns the GitHub address to go to, and `callback` is called by the web app when
GitHub sends the person back, with the code and the state. Nothing sensitive is ever in an address
the API serves, and the access token never leaves the server.
"""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from pv_api.deps import CurrentUser, EngineDep, LimiterDep, SettingsDep, WriterUser, ip_hash_of
from pv_api.schemas import (
    GitHubChooseIn,
    GitHubDisconnectIn,
    GitHubDisconnectOut,
    GitHubFinishIn,
    GitHubFinishOut,
    GitHubLinkIn,
    GitHubOut,
    GitHubStartOut,
)
from pv_api.services import github_service
from pv_domain.github import GitHubGateway
from pv_github import oauth_configured

router = APIRouter(prefix="/github", tags=["github"])


def get_gateway(request: Request) -> GitHubGateway | None:
    gateway: GitHubGateway | None = request.app.state.github
    return gateway


@router.get("", response_model=GitHubOut)
def read(
    request: Request, auth: CurrentUser, engine: EngineDep, settings: SettingsDep
) -> GitHubOut:
    return github_service.status(engine, settings, oauth_configured(settings), auth.user_id)


@router.post("/link", response_model=GitHubFinishOut)
async def link(
    body: GitHubLinkIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> GitHubFinishOut:
    limiter.check("github_start_user", str(auth.user_id))
    return await run_in_threadpool(
        github_service.link,
        engine,
        get_gateway(request),
        auth.user_id,
        body.link,
        ip_hash_of(request, settings),
    )


@router.post("/start", response_model=GitHubStartOut)
def start(
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> GitHubStartOut:
    limiter.check("github_start_user", str(auth.user_id))
    return github_service.start(
        engine, settings, get_gateway(request), auth.user_id, ip_hash_of(request, settings)
    )


@router.post("/callback", response_model=GitHubFinishOut)
async def callback(
    body: GitHubFinishIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> GitHubFinishOut:
    limiter.check("github_callback_user", str(auth.user_id))
    return await run_in_threadpool(
        github_service.finish,
        engine,
        settings,
        get_gateway(request),
        auth.user_id,
        body.code,
        body.state,
        ip_hash_of(request, settings),
    )


@router.post("/sync", status_code=202)
def sync(auth: WriterUser, engine: EngineDep, limiter: LimiterDep) -> None:
    limiter.check("github_sync_user", str(auth.user_id))
    github_service.sync(engine, auth.user_id)


@router.put("/repos", status_code=202)
def choose(
    body: GitHubChooseIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> None:
    limiter.check("github_sync_user", str(auth.user_id))
    github_service.choose(engine, auth.user_id, body.repo_ids, ip_hash_of(request, settings))


@router.post("/disconnect", response_model=GitHubDisconnectOut)
async def disconnect(
    body: GitHubDisconnectIn,
    request: Request,
    auth: WriterUser,
    engine: EngineDep,
    settings: SettingsDep,
    limiter: LimiterDep,
) -> GitHubDisconnectOut:
    limiter.check("github_start_user", str(auth.user_id))
    return await run_in_threadpool(
        github_service.disconnect,
        engine,
        settings,
        get_gateway(request),
        auth.user_id,
        body.keep_entries,
        ip_hash_of(request, settings),
    )
