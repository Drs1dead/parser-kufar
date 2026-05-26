"""Правила отбора объявлений под подписку пользователя."""
import logging
import re

from config import (
    ACCESSORY_HEADLINE_STEMS,
    DEVICE_CATALOG,
    DEFAULT_EXCLUDE_TERMS,
    DEFAULT_MEMORY_VOLUMES,
    FILTER_DEBUG_LOG,
    MEMORY_TIER_512_PLUS_GB,
    MEMORY_VOLUME_OPTIONS,
    NOT_SALE_TERMS,
    PARTS_EXCLUDE_TERMS,
    PHONE_REQUIRED_TERMS,
    WHOLE_PHONE_EXCLUDE_HEADLINE,
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
REJECT_NOT_WHOLE_PHONE = "not_whole_phone"
REJECT_MEMORY_NOT_SELECTED = "memory_not_selected"


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


def ad_headline(ad: dict) -> str:
    title = normalize(ad.get("title") or "")
    summary = normalize(ad.get("summary") or "")
    return f"{title} {summary}".strip()


def ad_matching_text(ad: dict) -> str:
    """Текст для поиска модели: кириллица айфон → iphone, поле phone_model из Kufar."""
    text = ad_full_text(ad)
    text = re.sub(r"\bайфон\b", "iphone", text)
    phone_model = normalize(ad.get("phone_model") or "")
    if phone_model:
        text = f"{text} {phone_model}"
    return text.strip()


def _contains_stem(text: str, stem: str) -> bool:
    stem = normalize(stem).strip()
    if not stem or not text:
        return False
    return stem in text


def is_whole_phone_listing(ad: dict) -> bool:
    """False — аксессуар, запчасть, коробка, клон и т.п."""
    headline = ad_headline(ad)
    if not headline:
        return False
    if any(_contains_stem(headline, stem) for stem in ACCESSORY_HEADLINE_STEMS):
        return False
    if any(_contains_phrase(headline, term) for term in WHOLE_PHONE_EXCLUDE_HEADLINE):
        return False
    full_text = f"{headline} {normalize(ad.get('description') or '')}".strip()
    if any(_contains_phrase(full_text, t) for t in PARTS_EXCLUDE_TERMS):
        return False
    if any(_contains_phrase(headline, t) for t in DEFAULT_EXCLUDE_TERMS):
        return False
    return True


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


def _device_key_from_text(full_text: str) -> str | None:
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


def ad_device_key(ad: dict) -> str | None:
    """
    Нормализованный ключ устройства из каталога.
    Важно: ищем самое длинное совпадение, чтобы 'iphone 12 pro max'
    не превращался в 'iphone 12'.
    """
    return _device_key_from_text(ad_matching_text(ad))


def parse_memory_gb_text(text: str) -> int | None:
    """Извлекает объём памяти в GB из строки Kufar (128 Гб, 256GB, 1 ТБ)."""
    t = normalize(text or "").replace(",", " ")
    if not t:
        return None
    if re.search(r"\b1\s*(?:тб|tb)\b", t):
        return 1024
    for gb in (1024, 512, 256, 128, 64):
        if re.search(rf"(?<![0-9]){gb}\s*(?:gb|гб|гиг)\b", t):
            return gb
        if re.search(rf"(?<![0-9]){gb}(?![0-9])", t):
            return gb
    return None


def ad_memory_gb(ad: dict) -> int | None:
    cached = ad.get("memory_gb")
    if isinstance(cached, int) and cached > 0:
        return cached
    for field in ("phone_memory", "summary", "title", "description"):
        gb = parse_memory_gb_text(str(ad.get(field) or ""))
        if gb:
            return gb
    return parse_memory_gb_text(ad_full_text(ad))


def _normalize_memory_selection(volumes: list[str] | None) -> set[str]:
    if volumes is None:
        volumes = list(DEFAULT_MEMORY_VOLUMES)
    allowed = set(MEMORY_VOLUME_OPTIONS)
    return {str(v).strip() for v in volumes if str(v).strip() in allowed}


def memory_matches_ad(ad: dict, selected: set[str]) -> bool:
    if not selected:
        return False
    gb = ad_memory_gb(ad)
    if gb is None:
        return True
    if "512+" in selected and gb >= MEMORY_TIER_512_PLUS_GB:
        return True
    return str(gb) in selected


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
    memory_volumes: list[str] | None = None,
    smart_filtering: bool,
    device_filter: bool = True,
    memory_filter: bool = True,
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
        if not is_whole_phone_listing(ad):
            return REJECT_NOT_WHOLE_PHONE
        if not any(_contains_phrase(headline, t) for t in PHONE_REQUIRED_TERMS):
            return REJECT_NOT_PHONE
        if any(_contains_not_sale_term(headline, t) for t in NOT_SALE_TERMS):
            return REJECT_NOT_SALE
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

    if memory_filter and device_filter:
        selected_mem = _normalize_memory_selection(memory_volumes)
        if not selected_mem:
            return REJECT_MEMORY_NOT_SELECTED
        if not memory_matches_ad(ad, selected_mem):
            return REJECT_MEMORY_NOT_SELECTED

    return None


def matches_filters(
    ad: dict,
    max_price: int,
    keywords: list[str] | None,
    *,
    memory_volumes: list[str] | None = None,
    smart_filtering: bool,
    device_filter: bool = True,
    memory_filter: bool = True,
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
            memory_volumes=memory_volumes,
            smart_filtering=smart_filtering,
            device_filter=device_filter,
            memory_filter=memory_filter,
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
        log.debug("filter reject %s link=%s title=%r%s", reason, link, title, extra)


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
