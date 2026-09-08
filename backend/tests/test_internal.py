"""The scheduler-facing routes: they are off unless a CRON_SECRET is set, and
they refuse every request that does not present it.
"""

from __future__ import annotations

import pytest

from app.api.deps import settings_dep
from app.core.config import get_settings

SECRET = "cron-test-secret"
ROUTES = [
    "/api/v1/internal/submit-pending",
    "/api/v1/internal/purge-expired",
    "/api/v1/internal/migrate",
]


@pytest.fixture
def cron(client):
    """Give the test app a CRON_SECRET without touching the process environment."""
    override = get_settings().model_copy(update={"cron_secret": SECRET})
    client.app.dependency_overrides[settings_dep] = lambda: override
    yield client
    client.app.dependency_overrides.pop(settings_dep, None)


@pytest.mark.parametrize("route", ROUTES)
def test_internal_routes_404_when_no_secret_is_configured(client, route) -> None:
    # The default test settings have no cron_secret.
    assert client.post(route).status_code == 404


@pytest.mark.parametrize("route", ROUTES)
def test_internal_routes_reject_a_missing_or_wrong_token(cron, route) -> None:
    assert cron.post(route).status_code == 401
    assert cron.post(route, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert cron.post(route, headers={"Authorization": SECRET}).status_code == 401  # no "Bearer "


def test_submit_pending_is_a_no_op_on_an_empty_queue(cron) -> None:
    r = cron.post("/api/v1/internal/submit-pending", headers={"Authorization": f"Bearer {SECRET}"})
    assert r.status_code == 200
    assert r.json() == {"found": 0, "submitted": 0}


def test_purge_expired_reports_a_count(cron) -> None:
    r = cron.post("/api/v1/internal/purge-expired", headers={"Authorization": f"Bearer {SECRET}"})
    assert r.status_code == 200
    assert r.json() == {"purged": 0}


def test_a_get_is_accepted_too_because_that_is_what_vercel_cron_sends(cron) -> None:
    r = cron.get("/api/v1/internal/purge-expired", headers={"Authorization": f"Bearer {SECRET}"})
    assert r.status_code == 200
