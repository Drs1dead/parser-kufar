"""Правила отбора объявлений под подписку пользователя."""
import logging
import re
from functools import lru_cache

from config import (
    ACCESSORY_HEADLINE_STEMS,
    DEVICE_CATALOG,
    DEFAULT_EXCLUDE_TERMS,
    DEFAULT_MEMORY_VOLUMES,
    FILTER_DEBUG_LOG,
    IDEAL_ALLOWED_CONDITIONS,
    IDEAL_MIN_BATTERY_PERCENT,
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
REJECT_NEW_PHONE = "new_phone_headline"
REJECT_NO_KEYWORDS = "no_keywords_selected"
REJECT_DEVICE_UNKNOWN = "device_not_in_catalog"
REJECT_DEVICE_NOT_SELECTED = "device_not_in_user_keywords"
REJECT_EXCHANGE_REFUSAL = "exchange_refusal"
REJECT_EXCHANGE_NEGATIVE = "exchange_negative"
REJECT_EXCHANGE_NO_HINT = "exchange_no_positive_hint"
REJECT_NOT_WHOLE_PHONE = "not_whole_phone"
REJECT_MEMORY_NOT_SELECTED = "memory_not_selected"
REJECT_COMPANY_AD = "company_ad"
REJECT_THIN_JUNK = "thin_junk_headline"
REJECT_IDEAL_NO_CONDITION = "ideal_no_condition"
REJECT_IDEAL_BAD_CONDITION = "ideal_bad_condition"
REJECT_IDEAL_BATTERY_UNKNOWN = "ideal_battery_unknown"
REJECT_IDEAL_BATTERY_LOW = "ideal_battery_low"
REJECT_IDEAL_DEFECT_TERM = "ideal_defect_term"
REJECT_IDEAL_NO_DESCRIPTION = "ideal_no_description"
REJECT_IDEAL_EXCHANGE = "ideal_exchange"

# VIP «Идеальные»: без царапин/потёртостей в списке.
IDEAL_REJECT_TERMS: tuple[str, ...] = (
    "разбит",
    "разбитый",
    "трещин",
    "скол",
    "сколот",
    "погнут",
    "не включается",
    "не включ",
    "не работает",
    "не заряжа",
    "битый экран",
    "битый дисплей",
    "разбитый экран",
    "разбитый дисплей",
    "face id не",
    "faceid не",
    "touch не работ",
    "тач не работ",
    "вертикальные полос",
    "пятно на экран",
    "битые пиксел",
    "битый пиксел",
    "подсветк",
    "ghosting",
    "слабая батар",
    "слабый акб",
    "пухлая батар",
    "вздут",
    "держит 2 час",
    "держит час",
    "быстро садится",
    "разряжается",
    "менял дисплей",
    "менял экран",
    "заменен дисплей",
    "заменён дисплей",
    "заменен экран",
    "заменён экран",
    "замена диспле",
    "замена экран",
    "не оригинал",
    "китайский дисплей",
    "китайский экран",
    "aftermarket",
    "рефка",
    "refurb",
    "на запчаст",
    "для запчаст",
    "донор",
    "icloud",
    "айклауд",
    "заблокирован",
    "заблокир",
    "на обмен",
    "к обмену",
    "только обмен",
    "меняю на",
    "обмен на",
)

# Явно плохие состояния Kufar (pre-отсев). «Б/у» — нейтрально, качество в strict.
IDEAL_BAD_CONDITION_MARKERS: tuple[str, ...] = (
    "удовлетворительн",
    "плох",
    "неисправ",
    "требует ремонт",
    "на запчаст",
    "для запчаст",
)

IDEAL_NEUTRAL_CONDITION_MARKERS: tuple[str, ...] = (
    "б/у",
    "бу",
    "used",
)

IDEAL_POSITIVE_CONDITION_HINTS: tuple[str, ...] = (
    "идеальн",
    "отличное состояние",
    "отличн состоян",
    "состояние отличное",
    "как нов",
    "без ремонт",
    "не ремонтир",
)

IDEAL_HEADLINE_REJECT_TERMS: tuple[str, ...] = (
    "разбит",
    "трещин",
    "не включается",
    "битый экран",
    "icloud",
    "заблокирован",
    "на запчаст",
    "донор",
)

_BATTERY_PERCENT_RE = re.compile(
    r"(?:"
    r"(?:акб|аккумулятор|батаре|battery|ёмкост|емкост|health|здоровь|емкост)[^\d]{0,32}(\d{2,3})\s*%?"
    r"|(\d{2,3})\s*%\s*(?:акб|аккумулятор|батаре|battery|ёмкост|емкост|health|емкост)"
    r"|(?:акб|аккумулятор|батаре|battery)\s*(\d{2,3})\b"
    r"|(?:емкост|ёмкост)\s*(?:акб|аккумулятор|батаре)?\s*(\d{2,3})\s*%?"
    r")",
    re.IGNORECASE,
)


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
    if "_whole_phone" in ad:
        return bool(ad["_whole_phone"])
    headline = ad_headline(ad)
    if not headline:
        ad["_whole_phone"] = False
        return False
    if any(_contains_stem(headline, stem) for stem in ACCESSORY_HEADLINE_STEMS):
        ad["_whole_phone"] = False
        return False
    if any(_contains_phrase(headline, term) for term in WHOLE_PHONE_EXCLUDE_HEADLINE):
        ad["_whole_phone"] = False
        return False
    full_text = f"{headline} {normalize(ad.get('description') or '')}".strip()
    if any(_contains_phrase(full_text, t) for t in PARTS_EXCLUDE_TERMS):
        ad["_whole_phone"] = False
        return False
    if any(_contains_phrase(headline, t) for t in DEFAULT_EXCLUDE_TERMS):
        ad["_whole_phone"] = False
        return False
    ad["_whole_phone"] = True
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


@lru_cache(maxsize=256)
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
    if "_device_key" in ad:
        return ad["_device_key"]
    key = _device_key_from_text(ad_matching_text(ad))
    ad["_device_key"] = key
    return key


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
    smart_filtering: bool = False,
    basic_filtering: bool = False,
    device_filter: bool = True,
    memory_filter: bool = True,
    skip_new_phone: bool = False,
    company_filter: bool = False,
    thin_junk: bool = False,
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
    headline = f"{title} {summary}".strip()

    if company_filter and ad.get("company_ad"):
        return REJECT_COMPANY_AD
    if thin_junk:
        if any(_contains_stem(headline, stem) for stem in ACCESSORY_HEADLINE_STEMS):
            return REJECT_THIN_JUNK

    if basic_filtering or smart_filtering:
        if not is_whole_phone_listing(ad):
            return REJECT_NOT_WHOLE_PHONE
    if smart_filtering:
        if not any(_contains_phrase(headline, t) for t in PHONE_REQUIRED_TERMS):
            return REJECT_NOT_PHONE
        if any(_contains_not_sale_term(headline, t) for t in NOT_SALE_TERMS):
            return REJECT_NOT_SALE
        if not skip_new_phone and is_new_phone_ad(ad):
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
    smart_filtering: bool = False,
    basic_filtering: bool = False,
    device_filter: bool = True,
    memory_filter: bool = True,
    skip_new_phone: bool = False,
    company_filter: bool = False,
    thin_junk: bool = False,
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
            basic_filtering=basic_filtering,
            device_filter=device_filter,
            memory_filter=memory_filter,
            skip_new_phone=skip_new_phone,
            company_filter=company_filter,
            thin_junk=thin_junk,
        )
        is None
    )


def parse_battery_percents(text: str) -> list[int]:
    """Извлекает явные проценты ёмкости АКБ из текста объявления."""
    t = normalize(text or "")
    found: list[int] = []
    for m in _BATTERY_PERCENT_RE.finditer(t):
        for g in m.groups():
            if g is None:
                continue
            value = int(g)
            if 1 <= value <= 100:
                found.append(value)
    return found


def _ideal_condition_label(ad: dict) -> str:
    raw = (ad.get("condition_label") or "").strip()
    if raw:
        return normalize(raw)
    summary = normalize(ad.get("summary") or "")
    m = re.search(r"состояние:\s*([^·]+)", summary)
    if m:
        return normalize(m.group(1).strip())
    return ""


def _ideal_label_is_bad(label: str) -> bool:
    return any(marker in label for marker in IDEAL_BAD_CONDITION_MARKERS)


def _ideal_label_is_good(label: str) -> bool:
    allowed = {normalize(c) for c in IDEAL_ALLOWED_CONDITIONS}
    return label in allowed


def _ideal_label_is_neutral(label: str) -> bool:
    if label in IDEAL_NEUTRAL_CONDITION_MARKERS:
        return True
    return any(marker in label for marker in IDEAL_NEUTRAL_CONDITION_MARKERS)


def _ideal_positive_condition_hint(text: str) -> bool:
    t = normalize(text or "")
    return bool(t) and any(_contains_phrase(t, hint) for hint in IDEAL_POSITIVE_CONDITION_HINTS)


def _ideal_condition_ok(ad: dict) -> str | None:
    """
    Kufar чаще отдаёт «Б/у» — пропускаем на pre.
    Явно плохие состояния отсекаем; «Отличное»/«Хорошее» — сразу ок.
    """
    label = _ideal_condition_label(ad)
    if label:
        if _ideal_label_is_bad(label):
            return REJECT_IDEAL_BAD_CONDITION
        if _ideal_label_is_good(label) or _ideal_label_is_neutral(label):
            return None
        if _ideal_positive_condition_hint(label):
            return None
        return REJECT_IDEAL_BAD_CONDITION
    if _ideal_positive_condition_hint(ad_headline(ad)):
        return None
    return REJECT_IDEAL_NO_CONDITION


def _ideal_text_has_term(text: str, terms: tuple[str, ...]) -> str | None:
    t = normalize(text or "")
    if not t:
        return None
    for term in terms:
        if _contains_phrase(t, term):
            return term
    return None


def ideal_reject_reason(ad: dict, *, require_full_text: bool) -> str | None:
    """
    None — лот подходит под поток «Идеальные» на данной стадии.
    require_full_text=False: состояние + заголовок; True: + описание, АКБ, полный текст.
    """
    cond_err = _ideal_condition_ok(ad)
    if cond_err:
        return cond_err

    headline = ad_headline(ad)
    hit = _ideal_text_has_term(headline, IDEAL_HEADLINE_REJECT_TERMS)
    if hit:
        return REJECT_IDEAL_DEFECT_TERM

    if is_exchange_ad(ad):
        return REJECT_IDEAL_EXCHANGE

    if not require_full_text:
        return None

    description = normalize(ad.get("description") or "")
    if not description.strip():
        return REJECT_IDEAL_NO_DESCRIPTION

    full_text = ad_full_text(ad)
    hit = _ideal_text_has_term(full_text, IDEAL_REJECT_TERMS)
    if hit:
        return REJECT_IDEAL_DEFECT_TERM

    percents = parse_battery_percents(full_text)
    if not percents:
        if _ideal_label_is_good(_ideal_condition_label(ad)) and _ideal_positive_condition_hint(
            full_text
        ):
            return None
        return REJECT_IDEAL_BATTERY_UNKNOWN
    if any(p < IDEAL_MIN_BATTERY_PERCENT for p in percents):
        return REJECT_IDEAL_BATTERY_LOW
    return None


def ideal_passes(ad: dict, *, stage: str) -> bool:
    require_full = stage == "strict"
    return ideal_reject_reason(ad, require_full_text=require_full) is None


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
