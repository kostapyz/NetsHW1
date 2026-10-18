"""
Основной цикл:
- берёт текущую страницу задания,
- в зависимости от типа делает GET/POST/upload,
- идёт по цепочке, пока не найдёт финальный 32-символьный ключ.

Использование:
    python find_key.py
    python find_key.py --curl
    python find_key.py --curl -v
"""
import sys
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import parser as P


BASE_URL = "http://hw1.alexbers.com/"
USER = "7ec1277c263a4b99913bc4784d638e5f"

MAX_STEPS = 1000
SLEEP_BETWEEN_STEPS_SEC = 0.1

BASE_HOST = urlparse(BASE_URL).hostname


def make_session(use_curl: bool, verbose: bool):
    if use_curl:
        from curl_request import CurlSession
        return CurlSession(verbose=verbose)
    from python_request import HttpSession
    return HttpSession()


def do_task(session, soup: BeautifulSoup, task_type: str, use_curl: bool) -> str:
    """Выполняет одно задание и возвращает HTML ответа."""
    req = P.parse_request_data(soup)

    cookies = {"user": USER, **req["cookies"]}
    params = req["params"]
    form = req["form"]
    headers = req["headers"]
    headers["Connection"] = "Close"

    if task_type == "link":
        a = soup.find("a", href=True)
        target = urljoin(BASE_URL, a["href"])
        return session.send(
            "GET", target,
            cookies=cookies, params=params, headers=headers,
        )

    if task_type == "post":
        path = P.extract_address_code_after_phrase(soup, r"POST")
        if not path:
            raise RuntimeError("Не нашёл адрес POST-запроса")
        target = urljoin(BASE_URL, path)
        return session.send(
            "POST", target,
            cookies=cookies, params=params, data=form, headers=headers,
        )

    if task_type == "get":
        path = P.extract_address_code_after_phrase(soup, r"GET")
        if not path:
            raise RuntimeError("Не нашёл адрес GET-запроса")
        target = urljoin(BASE_URL, path)
        return session.send(
            "GET", target,
            cookies=cookies, params=params, headers=headers,
        )

    if task_type == "files":
        path = P.extract_address_code_after_phrase(soup, r"Загрузите\s+файлы")
        if not path:
            raise RuntimeError("Не нашёл адрес загрузки файлов")
        target = urljoin(BASE_URL, path)

        table = P.find_files_table(soup)
        items = P.parse_files_table(table)
        if not items:
            raise RuntimeError("Не нашёл таблицу файлов")

        files = {
            name: (name, content.encode("utf-8"),
                   "text/plain; charset=utf-8")
            for name, content in items
        }
        timeout = 300 if use_curl else (10, 300)
        return session.send(
            "POST", target,
            cookies=cookies, params=params, files=files, headers=headers,
            timeout=timeout,
        )

    raise RuntimeError(f"Неизвестный тип задания: {task_type}")


def solve(use_curl: bool = False, verbose: bool = False) -> str:
    session = make_session(use_curl=use_curl, verbose=verbose)

    current_html = session.send("GET", BASE_URL, cookies={"user": USER})

    for step in range(1, MAX_STEPS + 1):
        soup = BeautifulSoup(current_html, "html.parser")
        task_type = P.detect_task_type(soup)

        if task_type is None:
            key = P.extract_secret_key(current_html)
            if not key:
                raise RuntimeError(
                    "Задание закончилось, но ключ не найден.\n"
                    "Последний HTML:\n" + current_html
                )
            return key

        current_html = do_task(session, soup, task_type, use_curl=use_curl)
        time.sleep(SLEEP_BETWEEN_STEPS_SEC)


def main():
    use_curl = "--curl" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    key = solve(use_curl=use_curl, verbose=verbose)
    print(key)


if __name__ == "__main__":
    main()