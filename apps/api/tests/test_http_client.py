import requests

from multiplanner_api.http_client import get_with_ssl_fallback, post_with_ssl_fallback


def test_get_retries_without_ssl_verification_after_ssl_error(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("multiplanner_api.http_client.requests.Session", fake_session(calls, fail_first=True))

    response = get_with_ssl_fallback("https://example.invalid/catalog.json", timeout=10)

    assert response.text == "ok"
    assert calls == [("GET", True), ("GET", False)]


def test_post_does_not_retry_non_ssl_request_errors(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("multiplanner_api.http_client.requests.Session", fake_session(calls, fail_connection=True))

    try:
        post_with_ssl_fallback("https://example.invalid/query", data="{}", timeout=10)
    except requests.exceptions.ConnectionError:
        pass
    else:
        raise AssertionError("ConnectionError should not be retried or swallowed")

    assert calls == [("POST", True)]


def fake_session(calls: list[tuple[str, bool]], *, fail_first: bool = False, fail_connection: bool = False):
    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def request(self, method, url, *, verify, **kwargs):
            calls.append((method, verify))
            if fail_connection:
                raise requests.exceptions.ConnectionError("offline")
            if fail_first and verify:
                raise requests.exceptions.SSLError("certificate verify failed")
            return FakeResponse()

    return FakeSession


class FakeResponse:
    text = "ok"
