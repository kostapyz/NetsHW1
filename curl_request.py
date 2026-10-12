# curl_request.py
"""
Аналог python_request.HttpSession, но запросы выполняются через
`curl`, запускаемый из subprocess. Собирает команду (bash-скрипт)
из аргументов и выполняет её.

Экспортирует класс CurlSession с методом send(...) -> str.
"""
import os
import subprocess
import tempfile
import urllib.parse


DEFAULT_TIMEOUT = 120  # секунд


def _normalize_timeout(timeout) -> int:
    if timeout is None:
        return DEFAULT_TIMEOUT
    if isinstance(timeout, (tuple, list)):
        return int(max(timeout))
    return int(timeout)


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def build_curl_command(method: str, url: str,
                       cookies: dict | None = None,
                       params: dict | None = None,
                       data: dict | None = None,
                       files: dict | None = None,
                       headers: dict | None = None,
                       timeout=None):
    """
    Возвращает (cmd_list, tmp_files).
    cmd_list — argv для subprocess; tmp_files — временные файлы,
    которые надо удалить после запроса.
    """
    method = method.upper()
    max_time = _normalize_timeout(timeout)

    cmd = ["curl", "-s", "-S", "-L", "--max-time", str(max_time)]

    if method == "POST":
        cmd += ["-X", "POST"]

    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        cmd += ["-b", cookie_str]

    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]

    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params)

    if data:
        for k, v in data.items():
            cmd += ["--data-urlencode", f"{k}={v}"]

    tmp_files = []
    if files:
        for field_name, spec in files.items():
            # spec: (filename, content[, content_type])
            if isinstance(spec, tuple) and len(spec) == 3:
                filename, content, content_type = spec
            elif isinstance(spec, tuple) and len(spec) == 2:
                filename, content = spec
                content_type = "application/octet-stream"
            else:
                filename, content, content_type = (
                    field_name, spec, "application/octet-stream",
                )

            if isinstance(content, str):
                content = content.encode("utf-8")

            fd, tmp_path = tempfile.mkstemp(prefix="curl_upload_")
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            tmp_files.append(tmp_path)

            mime = (content_type or "").split(";")[0].strip() or \
                   "application/octet-stream"
            cmd += [
                "-F",
                f"{field_name}=@{tmp_path};filename={filename};type={mime}",
            ]

    cmd.append(url)
    return cmd, tmp_files


def command_to_bash(cmd: list) -> str:
    """Человекочитаемая bash-строка для отладки."""
    return " ".join(_shell_quote(a) for a in cmd)


class CurlSession:
    """Аналог HttpSession, но через curl+subprocess."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def send(self, method: str, url: str,
             cookies: dict | None = None,
             params: dict | None = None,
             data: dict | None = None,
             files: dict | None = None,
             headers: dict | None = None,
             timeout=None) -> str:

        cmd, tmp_files = build_curl_command(
            method=method, url=url,
            cookies=cookies, params=params, data=data,
            files=files, headers=headers, timeout=timeout,
        )

        if self.verbose:
            print("[curl]", command_to_bash(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"curl failed (rc={result.returncode}): {result.stderr}"
                )
            return result.stdout
        finally:
            for p in tmp_files:
                try:
                    os.remove(p)
                except OSError:
                    pass