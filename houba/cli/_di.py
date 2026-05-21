"""Composition root. Construit les adapters concrets à partir des Settings.

Volontairement non couvert par les tests unitaires (cf. coverage omit).
"""

from __future__ import annotations

from dataclasses import dataclass

from houba.adapters.buildkit_cli import BuildkitAdapter
from houba.adapters.endoflife_http import EndoflifeHttpAdapter
from houba.adapters.git_cli import GitCliAdapter
from houba.adapters.gitlab_http import GitLabHttpAdapter
from houba.adapters.harbor_http import HarborHttpAdapter
from houba.adapters.skopeo_cli import SkopeoAdapter
from houba.adapters.system_clock import SystemClock
from houba.adapters.teams_webhook import TeamsWebhookAdapter
from houba.config import Settings


@dataclass(frozen=True)
class Container:
    settings: Settings
    harbor: HarborHttpAdapter
    skopeo: SkopeoAdapter
    builder: BuildkitAdapter
    git: GitCliAdapter
    gitlab: GitLabHttpAdapter
    notifier: TeamsWebhookAdapter | None
    eol: EndoflifeHttpAdapter
    clock: SystemClock


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    harbor = HarborHttpAdapter(
        base_url=settings.harbor.url,
        user=settings.harbor.user,
        password=settings.harbor.password.get_secret_value(),
    )
    gitlab = GitLabHttpAdapter(
        base_url=settings.gitlab.url,
        token=settings.gitlab.token.get_secret_value(),
    )
    notifier = None
    if settings.teams_webhook_url is not None:
        notifier = TeamsWebhookAdapter(webhook_url=settings.teams_webhook_url.get_secret_value())
    return Container(
        settings=settings,
        harbor=harbor,
        skopeo=SkopeoAdapter(),
        builder=BuildkitAdapter(),
        git=GitCliAdapter(),
        gitlab=gitlab,
        notifier=notifier,
        eol=EndoflifeHttpAdapter(base_url=settings.endoflife_url),
        clock=SystemClock(),
    )
