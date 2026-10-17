"""
Разбор HTML-страниц задания:
- таблицы (ключ, значение)
- адреса endpoint-ов
- таблица файлов для загрузки
- определение типа задания и извлечение ключа
"""
import re

from bs4 import BeautifulSoup


def parse_kv_table(table) -> dict:
    """Парсит таблицу вида (Ключ, Значение), значения в <code>..</code>."""
    if not table:
        return {}
    out = {}
    for tr in table.find_all("tr"):
        codes = tr.find_all("code")
        if len(codes) >= 2:
            k = codes[0].get_text(strip=True)
            v = codes[1].get_text(strip=True)
            out[k] = v
    return out


def find_table_after_text(soup: BeautifulSoup, pattern: str):
    """Первая таблица после текста, матчащего regex pattern (re.I)."""
    anchor = soup.find(string=re.compile(pattern, re.I))
    if not anchor:
        return None
    return anchor.find_next("table")


def extract_address_code_after_phrase(soup: BeautifulSoup, phrase_pattern: str):
    """
    Ищет фразу (напр. 'POST-запрос') и берёт ближайший следующий <code>/path</code>.
    """
    anchor = soup.find(string=re.compile(phrase_pattern, re.I))
    if not anchor:
        return None
    code_tag = anchor.find_next("code")
    if not code_tag:
        return None
    val = code_tag.get_text(strip=True)
    return val if val.startswith("/") else None


def find_files_table(soup: BeautifulSoup):
    """Таблица 'Имя файла / Содержимое' для задания 'Загрузите файлы'."""
    for table in soup.find_all("table"):
        header_text = " ".join(
            th.get_text(" ", strip=True) for th in table.find_all("th")
        )
        if re.search(r"Имя\s+файла", header_text, re.I) and re.search(
            r"Содержим", header_text, re.I
        ):
            return table
    return None


def parse_files_table(table) -> list:
    """Список (filename, content) из таблицы файлов."""
    if not table:
        return []
    files = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 2:
            continue
        name_code = tds[0].find("code")
        content_code = tds[1].find("code")
        if not name_code or not content_code:
            continue
        files.append(
            (name_code.get_text(strip=True), content_code.get_text(strip=True))
        )
    return files


def detect_task_type(soup: BeautifulSoup):
    """
    Возвращает одно из: 'link' | 'post' | 'get' | 'files' | None.
    None означает: ключ найден, задание закончилось.
    """
    page_text = soup.get_text(" ", strip=True)

    is_type1 = bool(soup.find("a", href=True)) and re.search(
        r"Перейдите\s+по", page_text, re.I
    )
    is_type2 = re.search(r"Отправьте\s+POST", page_text, re.I) is not None
    is_type3 = re.search(r"Отправьте\s+GET", page_text, re.I) is not None
    is_type4 = re.search(r"Загрузите\s+файлы", page_text, re.I) is not None

    if is_type1:
        return "link"
    if is_type2:
        return "post"
    if is_type3:
        return "get"
    if is_type4:
        return "files"
    return None


def extract_secret_key(html: str):
    """32-символьный hex в <code>...</code> — финальный ключ."""
    m = re.search(r"<code>\s*([0-9a-f]{32})\s*</code>", html, re.I)
    return m.group(1) if m else None


def parse_request_data(soup: BeautifulSoup) -> dict:
    """Вытаскивает cookies / params / form / headers из текущей страницы."""
    return {
        "cookies": parse_kv_table(find_table_after_text(soup, r"cookie")),
        "params": parse_kv_table(
            find_table_after_text(soup, r"параметры\s+запроса")
        ),
        "form": parse_kv_table(find_table_after_text(soup, r"данные\s+формы")),
        "headers": parse_kv_table(find_table_after_text(soup, r"заголовки")),
    }