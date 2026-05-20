"""Правила отбора объявлений под подписку пользователя."""
import logging
import re

from config import (
    DEVICE_CATALOG,
    DEFAULT_EXCLUDE_TERMS,
    FILTER_DEBUG_LOG,
    NOT_SALE_TERMS,
    PARTS_EXCLUDE_TERMS,
    PHONE_REQUIRED_TERMS,
)

log = logging.getLogger(__name__)

# Объявления именно про обмен (ищем по всему тексту). «Без обмена» и т.п. — отсекаем.
EXCHANGE_NEGATIVE_TERMS: tuple[str, ...] = (
    "без обмена",
    "без обменов",
    "обмен не интересует",
    "обмен не интересен",
    "обмен не нужен",
    "обмен не предлагать",
    "обмен не рассматриваю",
    "обмен не рассматривается",
    "не на обмен",
    "не интересует обмен",
    "не меняю",
    "не меняюсь",
    "менять не буду",
    "менять не предлагать",
    "обмен исключён",
    "обмен невозможен",
    "обмен не вариант",
    "не хочу обмен",
    "обмен не приветствуется",
    "обмен не обсуждается",
)

# «обмен не …» — отсекает отказы («обмен не интересен», «обмен не рассматривается» и т.д.).
EXCHANGE_REFUSAL_RE = re.compile(r"обмен\s+не(?:\s|$)")

EXCHANGE_HINT_TERMS: tuple[str, ...] = (
    "меняю",
    "обменяю",
    "к обмену",
    "готов к обмену",
    "готов обмен",
    "рассмотрю обмен",
    "рассмотрю варианты обмена",
    "возможен обмен",
    "обмен возможен",
    "интересует обмен",
    "ищу обмен",
    "только обмен",
    "swap",
    "trade-in",
    "трейд-ин",
    "поменяю",
    "на обмен",
    "бартер",
    "обменяюсь",
    "обмен интересен",
    "рассмотрю трейд",
)

NEW_PHONE_TERMS: tuple[str, ...] = (
    "новый",
    "новые",
    "новая",
    "new",
    "brand new",
    "запечатан",
    "не активирован",
    "неактивирован",
)

# Причины отклонения (для логов и тестов).
REJECT_PRICE_HIGH = "price_above_max"
REJECT_PRICE_MISSING = "price_missing"
REJECT_NOT_PHONE = "not_phone_headline"
REJECT_NOT_SALE = "not_sale_headline"
REJECT_EXCLUDE_TITLE = "exclude_term_in_title"
REJECT_EXCLUDE_PARTS = "exclude_parts_spares"
REJECT_NEW_PHONE = "new_phone_headline"
REJECT_NO_KEYWORDS = "no_keywords_selected"
REJECT_DEVICE_UNKNOWN = "device_not_in_catalog"
REJECT_DEVICE_NOT_SELECTED = "device_not_in_user_keywords"
REJECT_EXCHANGE_REFUSAL = "exchange_refusal"
REJECT_EXCHANGE_NEGATIVE = "exchange_negative"
REJECT_EXCHANGE_NO_HINT = "exchange_no_positive_hint"


def normalize(text: str) -> str:
    return (text or "").lower().replace("ё", "е")


def normalize_for_exchange_match(text: str) -> str:
    """Как normalize, плюс пунктуация → пробелы (чтобы «интересен.» матчился как «интересен»)."""
    s = normalize(text)
    s = re.sub(r"[.!?,;:…]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ad_full_text(ad: dict) -> str:
    title = normalize(ad.get("title") or "")
    summary = normalize(ad.get("summary") or "")
    description = normalize(ad.get("description") or "")
    return f"{title} {summary} {description}".strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Подстрока; для коротких однословных фраз — границы слова."""
    phrase = normalize(phrase).strip()
    if not phrase or not text:
        return False
    if " " in phrase or len(phrase) >= 6:
        return phrase in text
    pattern = rf"(?<![a-zа-яё0-9]){re.escape(phrase)}(?![a-zа-яё0-9])"
    return re.search(pattern, text) is not None


def _contains_not_sale_term(headline: str, term: str) -> bool:
    """Скупка/выкуп: не ловим «не куплю», «не выкуп» и т.п."""
    term_n = normalize(term).strip()
    if not term_n or term_n not in headline:
        return False
    for m in re.finditer(re.escape(term_n), headline):
        start = m.start()
        window = headline[max(0, start - 8) : start]
        if re.search(r"(?<![a-zа-яё0-9])не\s*$", window):
            continue
        return True
    return False


def is_new_phone_ad(ad: dict) -> bool:
    headline = normalize(f"{ad.get('title') or ''} {ad.get('summary') or ''}")
    return any(_contains_phrase(headline, t) for t in NEW_PHONE_TERMS)


def _catalog_match_terms(device: str) -> tuple[str, ...]:
    key = re.sub(r"\s+", " ", normalize(device).strip())
    terms = {key}
    if key.startswith("samsung galaxy "):
        short = key.removeprefix("samsung galaxy ").strip()
        terms.add(f"galaxy {short}")
        terms.add(f"samsung {short}")
        terms.add(short)
        if short.endswith(" plus"):
            plus_short = short.removesuffix(" plus").strip() + "+"
            terms.add(plus_short)
            terms.add(f"galaxy {plus_short}")
            terms.add(f"samsung galaxy {plus_short}")
            terms.add(f"samsung {plus_short}")
        if short.startswith("z flip"):
            flip_short = short.removeprefix("z ").strip()
            terms.add(flip_short)
            terms.add(f"samsung {flip_short}")
            terms.add(f"galaxy {flip_short}")
            terms.add(short.replace(" ", ""))
            terms.add(flip_short.replace(" ", ""))
        if short.startswith("z fold"):
            fold_short = short.removeprefix("z ").strip()
            terms.add(fold_short)
            terms.add(f"samsung {fold_short}")
            terms.add(f"galaxy {fold_short}")
            terms.add(short.replace(" ", ""))
            terms.add(fold_short.replace(" ", ""))
    return tuple(sorted(terms, key=len, reverse=True))


def _contains_device_term(text: str, term: str) -> bool:
    pattern = rf"(?<![a-zа-я0-9]){re.escape(term)}(?![a-zа-я0-9])"
    return re.search(pattern, text) is not None


def ad_device_key(ad: dict) -> str | None:
    """
    Нормализованный ключ устройства из каталога.
    Важно: ищем самое длинное совпадение, чтобы 'iphone 12 pro max'
    не превращался в 'iphone 12'.
    """
    full_text = ad_full_text(ad)
    matched: list[str] = []
    for device in DEVICE_CATALOG:
        key = re.sub(r"\s+", " ", normalize(device).strip())
        if not key:
            continue
        if any(_contains_device_term(full_text, term) for term in _catalog_match_terms(key)):
            matched.append(key)
    if not matched:
        return None
    matched.sort(key=len, reverse=True)
    return matched[0]


def _keyword_matches_selection(ad_key: str, selected_keys: set[str]) -> bool:
    """Точное совпадение или выбранная «родительская» модель (z flip → z flip 7)."""
    if ad_key in selected_keys:
        return True
    return any(ad_key.startswith(sk + " ") for sk in selected_keys)


def filter_reject_reason(
    ad: dict,
    max_price: int,
    keywords: list[str] | None,
    *,
    smart_filtering: bool,
    device_filter: bool = True,
) -> str | None:
    """
    None — объявление проходит фильтры.
    Иначе — код причины отклонения (для логов).
    """
    price = ad.get("price")
    if max_price > 0:
        if price is None or price > max_price:
            return REJECT_PRICE_HIGH
    else:
        if price is None or price <= 0:
            return REJECT_PRICE_MISSING

    title = normalize(ad.get("title") or "")
    summary = normalize(ad.get("summary") or "")
    description = normalize(ad.get("description") or "")

    headline = f"{title} {summary}".strip()
    full_text = f"{headline} {description}".strip()

    if smart_filtering:
        if not any(_contains_phrase(headline, t) for t in PHONE_REQUIRED_TERMS):
            return REJECT_NOT_PHONE
        if any(_contains_not_sale_term(headline, t) for t in NOT_SALE_TERMS):
            return REJECT_NOT_SALE
        if any(_contains_phrase(full_text, t) for t in PARTS_EXCLUDE_TERMS):
            return REJECT_EXCLUDE_PARTS
        if any(_contains_phrase(title, t) for t in DEFAULT_EXCLUDE_TERMS):
            return REJECT_EXCLUDE_TITLE
        if is_new_phone_ad(ad):
            return REJECT_NEW_PHONE

    if device_filter:
        kw_list = keywords or []
        selected_keys = {
            re.sub(r"\s+", " ", normalize(k).strip())
            for k in kw_list
            if normalize(k).strip()
        }
        if not selected_keys:
            return REJECT_NO_KEYWORDS
        ad_key = ad_device_key(ad)
        if ad_key is None:
            return REJECT_DEVICE_UNKNOWN
        if not _keyword_matches_selection(ad_key, selected_keys):
            return REJECT_DEVICE_NOT_SELECTED

    return None


def matches_filters(
    ad: dict,
    max_price: int,
    keywords: list[str] | None,
    *,
    smart_filtering: bool,
    device_filter: bool = True,
) -> bool:
    """
    Цена — по объявлению целиком.
    Запчасти/платы — в названии, summary и описании; прочие стоп-слова — только в названии.
    Признак телефона и «не продажа» — в названии + summary (параметры Kufar), не в описании.
    Ключевики пользователя — везде (название, summary, описание).
    """
    return (
        filter_reject_reason(
            ad,
            max_price,
            keywords,
            smart_filtering=smart_filtering,
            device_filter=device_filter,
        )
        is None
    )


def log_filter_reject(
    ad: dict,
    reason: str,
    *,
    chat_id: int | None = None,
    feed_mode: str | None = None,
) -> None:
    link = ad.get("link") or ad.get("ad_id") or "?"
    title = (ad.get("title") or "")[:80]
    extra = ""
    if chat_id is not None:
        extra += f" chat_id={chat_id}"
    if feed_mode:
        extra += f" mode={feed_mode}"
    if FILTER_DEBUG_LOG:
        log.info("[FILTER] reject %s link=%s title=%r%s", reason, link, title, extra)


def is_exchange_ad(ad: dict) -> bool:
    """Объявление про обмен устройством (по формулировкам в тексте)."""
    return exchange_reject_reason(ad) is None


def exchange_reject_reason(ad: dict) -> str | None:
    """None если объявление про обмен; иначе код причины отклонения."""
    full_text = normalize_for_exchange_match(ad_full_text(ad))
    if EXCHANGE_REFUSAL_RE.search(full_text):
        return REJECT_EXCHANGE_REFUSAL
    if any(normalize(t) in full_text for t in EXCHANGE_NEGATIVE_TERMS):
        return REJECT_EXCHANGE_NEGATIVE
    if not any(normalize(t) in full_text for t in EXCHANGE_HINT_TERMS):
        return REJECT_EXCHANGE_NO_HINT
    return None
