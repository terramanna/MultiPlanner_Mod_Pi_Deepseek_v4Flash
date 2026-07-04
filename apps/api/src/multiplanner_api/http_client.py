from __future__ import annotations

from typing import Any
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning


def get_with_ssl_fallback(url: str, **kwargs: Any) -> requests.Response:
    return request_with_ssl_fallback("GET", url, **kwargs)


def post_with_ssl_fallback(url: str, **kwargs: Any) -> requests.Response:
    return request_with_ssl_fallback("POST", url, **kwargs)


def request_with_ssl_fallback(method: str, url: str, **kwargs: Any) -> requests.Response:
    try:
        return _request(method, url, verify=True, **kwargs)
    except requests.exceptions.SSLError:
        warnings.warn(
            f"SSL verification failed for {url}; retrying without certificate verification.",
            stacklevel=2,
        )
        return _request(method, url, verify=False, **kwargs)


def _request(method: str, url: str, *, verify: bool, **kwargs: Any) -> requests.Response:
    with warnings.catch_warnings():
        if not verify:
            warnings.simplefilter("ignore", InsecureRequestWarning)
        with requests.Session() as session:
            session.trust_env = False
            return session.request(method, url, verify=verify, **kwargs)
