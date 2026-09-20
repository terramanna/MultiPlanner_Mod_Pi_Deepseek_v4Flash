from fastapi import FastAPI
from fastapi.testclient import TestClient

from multiplanner_api.rate_limiter import add_rate_limiter


def _build_app(requests_per_minute: int = 2) -> FastAPI:
    app = FastAPI()
    add_rate_limiter(app, requests_per_minute=requests_per_minute)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/subsets/file")
    def subset_file() -> dict:
        return {"ok": True}

    @app.get("/api/v1/tiles/foo/bar/1/2/3.png")
    def tile() -> dict:
        return {"ok": True}

    @app.get("/api/v1/probe/point")
    def limited() -> dict:
        return {"ok": True}

    return app


def test_returns_429_json_after_threshold_is_crossed() -> None:
    client = TestClient(_build_app(requests_per_minute=2))

    assert client.get("/api/v1/probe/point").status_code == 200
    assert client.get("/api/v1/probe/point").status_code == 200

    response = client.get("/api/v1/probe/point")

    # A raised HTTPException from user middleware escapes Starlette's inner
    # ExceptionMiddleware and would surface as a 500; this must be a real
    # 429 response instead.
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded. Try again later."


def test_healthz_is_exempt_from_the_limit() -> None:
    client = TestClient(_build_app(requests_per_minute=2))

    for _ in range(5):
        assert client.get("/healthz").status_code == 200


def test_subset_file_and_tile_routes_are_exempt_from_the_limit() -> None:
    client = TestClient(_build_app(requests_per_minute=2))

    for _ in range(5):
        assert client.get("/api/v1/subsets/file").status_code == 200
        assert client.get("/api/v1/tiles/foo/bar/1/2/3.png").status_code == 200
