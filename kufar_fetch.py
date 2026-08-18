"""Загрузка и нормализация объявлений с API Kufar."""

import asyncio
import json
import logging
import re
from typing import Any, Optional

import aiohttp

from config import (
    KUFAR_FETCH_RETRIES,
    KUFAR_FETCH_RETRY_DELAY,
    KUFAR_MAX_PAGES,
    KUFAR_QUERIES,
    KUFAR_REGION,
    KUFAR_SIZE,
)
from filters import parse_memory_gb_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.kufar.by/search-api/v2/search/rendered-paginated"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.kufar.by/",
    "Origin": "https://www.kufar.by",
}
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>',
    re.DOTALL,
)


def _param(params: list[dict], name: str) -> Optional[dict]:
    for p in params or []:
        if p.get("p") == name:
            return p
    return None


def _param_label(params: list[dict], name: str) -> str:
    p = _param(params, name)
    if not p:
        return ""
    vl = p.get("vl")
    if isinstance(vl, str) and vl:
        return vl
    v = p.get("v")
    return str(v) if v is not None else ""


def _build_location(ad_params: list[dict]) -> str:
    region = _param_label(ad_params, "region")
    area = _param_label(ad_params, "area")
    if region and area:
        return f"{region}, {area}"
    return region or area or ""


def _build_summary(ad_params: list[dict]) -> str:
    bits: list[str] = []
    for key, prefix in (
        ("condition", "Состояние"),
        ("phone_model", "Модель"),
        ("phone_memory", "Память"),
        ("phone_color", "Цвет"),
    ):
        label = _param_label(ad_params, key)
        if label:
            bits.append(f"{prefix}: {label}")
    return " · ".join(bits)


def _price_from_cents(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value) // 100
    except (TypeError, ValueError):
        return None


def _photo_urls(raw: dict) -> list[str]:
    out: list[str] = []
    for image in raw.get("images") or []:
        if not isinstance(image, dict):
            continue
        path = str(image.get("path") or "").strip().lstrip("/")
        if path:
            out.append(f"https://rms.kufar.by/v1/gallery/{path}")
    return list(dict.fromkeys(out))


def normalize_listing(raw: dict) -> Optional[dict]:
    ad_id = raw.get("ad_id")
    link = raw.get("ad_link") or (f"https://www.kufar.by/item/{ad_id}" if ad_id else None)
    if not link:
        return None

    subject = (raw.get("subject") or "").strip()
    if not subject:
        return None

    ad_params = raw.get("ad_parameters") or []
    phone_model = _param_label(ad_params, "phone_model").strip()
    phone_memory = _param_label(ad_params, "phone_memory").strip()
    summary = _build_summary(ad_params)
    condition_label = _param_label(ad_params, "condition").strip()
    memory_gb = parse_memory_gb_text(phone_memory) or parse_memory_gb_text(summary)
    return {
        "ad_id": ad_id,
        "title": subject,
        "price": _price_from_cents(raw.get("price_byn")),
        "price_usd": _price_from_cents(raw.get("price_usd")),
        "location": _build_location(ad_params),
        "summary": summary,
        "condition_label": condition_label,
        "phone_model": phone_model,
        "phone_memory": phone_memory,
        "memory_gb": memory_gb,
        "description": "",
        "link": link.split("?")[0],
        "list_time": raw.get("list_time"),
        "photo_urls": _photo_urls(raw),
    }


def _next_page_cursor(data: dict) -> str | None:
    pages = (data.get("pagination") or {}).get("pages") or []
    for page in pages:
        if page.get("label") == "next":
            token = page.get("token")
            if isinstance(token, str) and token.strip():
                return token.strip()
    return None


async def _fetch_search_page(
    session: aiohttp.ClientSession,
    query: str,
    *,
    cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    """Одна страница листинга: объявления и cursor следующей страницы."""
    params = {
        "lang": "ru",
        "size": str(KUFAR_SIZE),
        "sort": "lst.d",
        "rgn": str(KUFAR_REGION),
        "cur": "BYR",
        "query": query,
    }
    if cursor:
        params["cursor"] = cursor
    last_err: str | None = None
    for attempt in range(1, KUFAR_FETCH_RETRIES + 1):
        try:
            async with session.get(
                SEARCH_URL, params=params, timeout=aiohttp.ClientTimeout(total=25)
            ) as r:
                if r.status >= 500 or r.status == 429:
                    body = (await r.text())[:200]
                    last_err = f"status={r.status} {body}"
                    log.warning(
                        "kufar search retry query=%r %s attempt=%s/%s",
                        query,
                        last_err,
                        attempt,
                        KUFAR_FETCH_RETRIES,
                    )
                    if r.status == 429 and attempt < KUFAR_FETCH_RETRIES:
                        retry_after = r.headers.get("Retry-After")
                        if retry_after:
                            try:
                                await asyncio.sleep(float(retry_after))
                            except ValueError:
                                pass
                elif r.status != 200:
                    log.error(
                        "kufar search failed query=%r status=%s",
                        query,
                        r.status,
                    )
                    return [], None
                else:
                    data = await r.json()
                    return data.get("ads") or [], _next_page_cursor(data)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_err = repr(e)
            log.warning(
                "kufar search network query=%r %s attempt=%s/%s",
                query,
                last_err,
                attempt,
                KUFAR_FETCH_RETRIES,
            )
        if attempt < KUFAR_FETCH_RETRIES:
            await asyncio.sleep(KUFAR_FETCH_RETRY_DELAY * attempt)
    if last_err:
        log.error(
            "kufar search exhausted query=%r attempts=%s err=%s",
            query,
            KUFAR_FETCH_RETRIES,
            last_err,
        )
    return [], None


async def _fetch_search(session: aiohttp.ClientSession, query: str) -> list[dict]:
    """До KUFAR_MAX_PAGES страниц листинга по одному поисковому запросу."""
    all_raw: list[dict] = []
    cursor: str | None = None
    for page_num in range(1, KUFAR_MAX_PAGES + 1):
        batch, next_cursor = await _fetch_search_page(
            session, query, cursor=cursor
        )
        if batch:
            all_raw.extend(batch)
        if not next_cursor or page_num >= KUFAR_MAX_PAGES:
            break
        cursor = next_cursor
    if KUFAR_MAX_PAGES > 1 and len(all_raw) > KUFAR_SIZE:
        log.debug(
            "kufar paginated query=%r pages=%s raw=%d",
            query,
            page_num,
            len(all_raw),
        )
    return all_raw


async def _fetch_description(session: aiohttp.ClientSession, link: str) -> str:
    try:
        async with session.get(link, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return ""
            html = await r.text()
    except Exception as e:
        log.debug("[KUFAR] не удалось открыть %s: %s", link, e)
        return ""

    m = NEXT_DATA_RE.search(html)
    if not m:
        return ""
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return ""

    ad_view = (
        data.get("props", {})
        .get("initialState", {})
        .get("adView", {})
        .get("data", {})
    )
    body = (ad_view.get("body") or "").strip()
    if len(body) > 500:
        body = body[:500].rstrip() + "..."
    return body


async def _enrich_description(
    session: aiohttp.ClientSession, ad: dict, sem: asyncio.Semaphore
) -> None:
    async with sem:
        ad["description"] = await _fetch_description(session, ad["link"])


async def enrich_ads_descriptions(ads: list[dict], *, concurrency: int = 5) -> None:
    """Параллельно подгружает описания для списка объявлений."""
    need = [a for a in ads if not (a.get("description") or "").strip() and a.get("link")]
    if not need:
        return
    connector = aiohttp.TCPConnector(limit=8)
    async with aiohttp.ClientSession(
        headers=DEFAULT_HEADERS, connector=connector
    ) as session:
        sem = asyncio.Semaphore(max(1, concurrency))
        await asyncio.gather(*(_enrich_description(session, ad, sem) for ad in need))


async def fetch_ads(*, with_description: bool = False) -> list[dict]:
    """
    Объявления с листинга. Поля: ad_id, title, price, price_usd, location,
    summary, description, link, list_time, photo_urls.
    """
    raw_ads: list[dict] = []
    ads: list[dict] = []
    connector = aiohttp.TCPConnector(limit=8)
    async with aiohttp.ClientSession(
        headers=DEFAULT_HEADERS, connector=connector
    ) as session:
        seen_ids: set[str] = set()
        for query in KUFAR_QUERIES:
            for raw in await _fetch_search(session, query):
                raw_id = str(raw.get("ad_id") or raw.get("ad_link") or "")
                if raw_id and raw_id in seen_ids:
                    continue
                if raw_id:
                    seen_ids.add(raw_id)
                raw_ads.append(raw)
        for raw in raw_ads:
            item = normalize_listing(raw)
            if item is not None:
                ads.append(item)

        if with_description and ads:
            await enrich_ads_descriptions(ads)

    log.debug(
        "kufar listings raw=%d normalized=%d pages_per_query=%s",
        len(raw_ads),
        len(ads),
        KUFAR_MAX_PAGES,
    )
    return ads
