"""
Отправка HTTP-запросов через requests с ретраями и per-request cookies.
Экспортирует класс HttpSession с методом send(...) -> str (тело ответа).
"""
import time

import requests
from requests.exceptions import ReadTimeout, ConnectionError, ChunkedEncodingError


DEFAULT_TIMEOUT = (5, 120)  # (connect_timeout, read_timeout)


def _coerce_timeout(timeout):
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, (tuple, list)):
        return tuple(timeout)
    return (5, timeout)


def request_retry(sess: requests.Session, method: str, url: str,
                  tries: int = 5, backoff: float = 0.5, **kwargs):
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    last_exc = None
    for i in range(tries):
        try:
            return sess.request(method, url, timeout=timeout, **kwargs)
        except (ReadTimeout, ConnectionError, ChunkedEncodingError) as e:
            last_exc = e
            if i == tries - 1:
                raise
            time.sleep(backoff * (2 ** i))
    raise last_exc


class HttpSession:
    """Обёртка над requests.Session: per-request cookies + retry."""

    def __init__(self):
        self.session = requests.Session()

    def send(self, method: str, url: str,
             cookies: dict | None = None,
             params: dict | None = None,
             data: dict | None = None,
             files: dict | None = None,
             headers: dict | None = None,
             timeout=None) -> str:

        self.session.cookies.clear()
        for k, v in (cookies or {}).items():
            self.session.cookies.set(k, v)

        kwargs = {
            "headers": headers or {},
            "params": params or {},
            "timeout": _coerce_timeout(timeout),
        }
        if method.upper() == "POST":
            if files is not None:
                kwargs["files"] = files
            if data is not None:
                kwargs["data"] = data

        resp = request_retry(self.session, method.upper(), url, **kwargs)
        resp.encoding = resp.encoding or "utf-8"
        text = resp.text
        resp.close()
        return text