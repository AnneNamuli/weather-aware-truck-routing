from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest import mock

import pytest
from django.test import Client, override_settings

from planner import views
from planner.models import TripPlan
from planner.services.upstream import UpstreamError


def payload(**overrides):
    body = {
        "origin": {"lat": 32.78, "lon": -96.80, "label": "Dallas"},
        "destination": {"lat": 29.76, "lon": -95.37, "label": "Houston"},
        "departure": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "load_lbs": 42000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


def post(path, body):
    return Client().post(path, body, content_type="application/json")


RESULT = {"recommended_route_id": "B", "routes": [{"id": "A"}, {"id": "B"}]}


@pytest.mark.django_db
def test_plan_passes_validated_input_to_planner():
    with mock.patch.object(views, "plan_trip", return_value=RESULT) as plan_trip:
        response = post("/api/plan", payload())
    assert response.status_code == HTTPStatus.OK
    kwargs = plan_trip.call_args.kwargs
    assert kwargs["origin"] == (32.78, -96.80)
    assert kwargs["interval_miles"] == 25
    assert kwargs["departure"].tzinfo is not None


@pytest.mark.django_db
def test_plan_is_saved_and_can_be_reloaded_by_id():
    with mock.patch.object(views, "plan_trip", return_value=RESULT):
        created = post("/api/plan", payload()).json()

    saved = TripPlan.objects.get(pk=created["id"])
    assert saved.origin["label"] == "Dallas"
    assert saved.recommended_route_id == "B"

    reloaded = Client().get(f"/api/plans/{created['id']}").json()
    assert reloaded["routes"] == RESULT["routes"]
    assert reloaded["id"] == created["id"]


@pytest.mark.django_db
def test_unknown_plan_id_is_404():
    assert (
        Client().get("/api/plans/00000000-0000-0000-0000-000000000000").status_code
        == HTTPStatus.NOT_FOUND
    )


def test_plan_rejects_bad_interval_and_past_departure():
    response = post("/api/plan", payload(interval_miles=15))
    assert response.status_code == HTTPStatus.BAD_REQUEST and "interval_miles" in response.json()

    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    response = post("/api/plan", payload(departure=past))
    assert response.status_code == HTTPStatus.BAD_REQUEST and "departure" in response.json()


def test_plan_rejects_identical_origin_and_destination():
    same = {"lat": 32.78, "lon": -96.80}
    assert (
        post("/api/plan", payload(origin=same, destination=same)).status_code
        == HTTPStatus.BAD_REQUEST
    )


@pytest.mark.django_db
def test_upstream_failures_are_reported_with_their_status():
    with mock.patch.object(
        views,
        "plan_trip",
        side_effect=UpstreamError("Weather service rate limit", HTTPStatus.SERVICE_UNAVAILABLE),
    ):
        response = post("/api/plan", payload())
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Weather service rate limit"}


def test_heatmap_validates_corridor():
    body = {"corridor": [[[30, -96]]], "departure": payload()["departure"], "load_lbs": 0}
    assert post("/api/heatmap", body).status_code == HTTPStatus.BAD_REQUEST


def test_geocode_short_query_returns_nothing_without_calling_upstream():
    with mock.patch.object(views.geocoding, "search") as search:
        response = Client().get("/api/geocode", {"q": "a"})
    assert response.json() == {"results": []}
    search.assert_not_called()


def test_http_client_retries_transient_5xx_once():
    from planner.services import upstream

    bad = mock.Mock(status_code=HTTPStatus.BAD_GATEWAY, json=lambda: {"message": "busy"})
    good = mock.Mock(status_code=HTTPStatus.OK, json=lambda: {"ok": True})
    with (
        mock.patch.object(upstream._session, "get", side_effect=[bad, good]) as get,
        mock.patch.object(upstream.time, "sleep"),
    ):
        assert upstream.get_json("https://x") == {"ok": True}
    assert get.call_count == 2


@override_settings(CORS_ALLOWED_ORIGINS=["https://annenamuli.github.io"])
def test_cors_allows_configured_frontend_origin_only():
    allowed = Client().get("/api/health", HTTP_ORIGIN="https://annenamuli.github.io")
    other = Client().get("/api/health", HTTP_ORIGIN="https://evil.example")
    assert allowed["Access-Control-Allow-Origin"] == "https://annenamuli.github.io"
    assert "Access-Control-Allow-Origin" not in other
