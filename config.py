import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from product_catalog import DEFAULT_KEYWORDS, DEVICE_CATALOG

load_dotenv()

# Часовой пояс для дат в сообщениях (Минск = UTC+3, как МСК).
_display_tz_name = os.getenv("DISPLAY_TIMEZONE", "Europe/Minsk").strip() or "Europe/Minsk"
try:
    DISPLAY_TZ = ZoneInfo(_display_tz_name)
except Exception:
    # Без пакета tzdata (часто Windows) — UTC; pip install tzdata для Europe/Minsk.
    DISPLAY_TZ = timezone.utc


def format_local_datetime(ts: int | float, *, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Момент времени (Unix UTC) → строка в DISPLAY_TZ."""
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(DISPLAY_TZ)
    return dt.strftime(fmt)

TOKEN = os.getenv("TOKEN", "").strip()

# Путь к SQLite. Пусто = авто (см. db._sqlite_path): data/bot.db локально, /app/data/bot.db на BotHost.
# На BotHost в панели можно явно: DB_PATH=/app/data/bot.db
DB_PATH = os.getenv("DB_PATH", "").strip()

# Ожидание блокировки SQLite, сек. (параметр timeout в sqlite3.connect).
# Жёсткость записи на диск: SQLITE_SYNCHRONOUS = NORMAL | FULL | EXTRA (см. документацию SQLite).
SQLITE_BUSY_TIMEOUT = float(os.getenv("SQLITE_BUSY_TIMEOUT", "30"))
_sqlite_sync = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL").strip().upper()
SQLITE_SYNCHRONOUS = _sqlite_sync if _sqlite_sync in ("OFF", "NORMAL", "FULL", "EXTRA") else "NORMAL"

# Повтор запроса к Kufar при сетевых ошибках / 5xx
KUFAR_FETCH_RETRIES = max(1, int(os.getenv("KUFAR_FETCH_RETRIES", "3")))
KUFAR_FETCH_RETRY_DELAY = float(os.getenv("KUFAR_FETCH_RETRY_DELAY", "2"))

VIP_CHECK_INTERVAL = max(1, int(os.getenv("VIP_CHECK_INTERVAL", "30")))
REGULAR_CHECK_INTERVAL = max(1, int(os.getenv("REGULAR_CHECK_INTERVAL", "420")))
# Тик poller: не длиннее VIP, иначе VIP не попадёт в свой интервал.
_raw_check = int(os.getenv("CHECK_INTERVAL", "10"))
CHECK_INTERVAL = max(1, min(_raw_check, VIP_CHECK_INTERVAL))

FIRST_RUN_LIMIT = int(os.getenv("FIRST_RUN_LIMIT", "3"))
VIP_SUBSCRIPTION_DAYS = int(os.getenv("VIP_SUBSCRIPTION_DAYS", "30"))
VIP_PRICE_USD = int(os.getenv("VIP_PRICE_USD", "2"))
REFERRAL_VIP_DAYS_PER_FRIEND = max(1, int(os.getenv("REFERRAL_VIP_DAYS_PER_FRIEND", "1")))

# Объёмы памяти для фильтра (строки в БД: "64", "128", …, "512+")
MEMORY_VOLUME_OPTIONS: tuple[str, ...] = ("64", "128", "256", "512", "512+")
DEFAULT_MEMORY_VOLUMES: tuple[str, ...] = ("64",)
MEMORY_TIER_512_PLUS_GB = 512
MEMORY_TOKEN_512_PLUS = "512+"


def format_memory_volume(vol: str, *, short: bool = False) -> str:
    """Подпись объёма для UI (в БД по-прежнему токен 512+)."""
    if vol == MEMORY_TOKEN_512_PLUS:
        return "более" if short else "от 512 ГБ"
    return f"{vol} ГБ"


# Белорусский рубль (BYN). Международное обозначение — Br (не ₽).
CURRENCY_SIGN = "Br"


def format_price(amount: int | float | None) -> str:
    """Цена в белорусских рублях для отображения в боте."""
    if amount is None:
        return "не указана"
    n = int(amount)
    return f"{n:,}".replace(",", " ") + f" {CURRENCY_SIGN}"


MARKET_DISCOUNT_THRESHOLD = float(os.getenv("MARKET_DISCOUNT_THRESHOLD", "0.85"))
PRICE_DATA_RETENTION_DAYS = max(
    1, int(os.getenv("PRICE_DATA_RETENTION_DAYS", "14"))
)
SEEN_ADS_RETENTION_DAYS = max(1, int(os.getenv("SEEN_ADS_RETENTION_DAYS", "90")))
KUFAR_MAX_PAGES = max(1, int(os.getenv("KUFAR_MAX_PAGES", "2")))
IDEAL_MIN_BATTERY_PERCENT = max(1, min(100, int(os.getenv("IDEAL_MIN_BATTERY_PERCENT", "75"))))
IDEAL_ALLOWED_CONDITIONS: tuple[str, ...] = tuple(
    normalize_label
    for raw in os.getenv("IDEAL_ALLOWED_CONDITIONS", "Отличное,Хорошее").split(",")
    if (normalize_label := raw.strip().lower().replace("ё", "е"))
) or ("отличное", "хорошее")
FILTER_DEBUG_LOG = os.getenv("FILTER_DEBUG_LOG", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_LEVEL = _log_level if _log_level in ("DEBUG", "INFO", "WARNING", "ERROR") else "INFO"
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

DEFAULT_MAX_PRICE = int(os.getenv("DEFAULT_MAX_PRICE", "500"))

MAX_PRICE_PRESETS: tuple[int, ...] = tuple(
    int(x.strip())
    for x in os.getenv("MAX_PRICE_PRESETS", "300,500,800,1000,1500,2000,3000,5000").split(",")
    if x.strip().isdigit()
) or (300, 500, 800, 1000, 1500, 2000, 3000, 5000)

# Стоп-слова по смыслу объявления: проверяются только в названии (subject),
# чтобы «чехол в подарок» в описании не отсекало продажу телефона.
DEFAULT_EXCLUDE_TERMS: tuple[str, ...] = (
    "адаптер",
    "акб",
    "аккумулятор",
    "бампер",
    "блок питания",
    "для ремонта",
    "дисплей",
    "донор",
    "донорский",
    "дубликат",
    "замена акб",
    "замена аккумулятора",
    "замена батареи",
    "зарядка",
    "заднее стекло",
    "защитное стекло",
    "кабель",
    "камера",
    "камеры",
    "кейс",
    "копия",
    "корпус",
    "макет",
    "матрица",
    "MagSafe",
    "муляж",
    "на запчасти",
    "плата",
    "плёнка",
    "пленка",
    "подделка",
    "ремонт",
    "реплика",
    "стекло",
    "чехол",
    "чехлы",
    "чехлов",
    "шлейф",
    "шлейфы",
    "экран",
    "микрофон",
)

# Запчасти / платы / разбор: в названии + summary + описании (не целый телефон).
PARTS_EXCLUDE_TERMS: tuple[str, ...] = (
    "запчасти",
    "запчасть",
    "запчастей",
    "платы",
    "плата",
    "плату",
    "плат ",
    "платам",
    "материнск",
    "motherboard",
    "logic board",
    "mainboard",
    "заблокирован",
    "заблокир",
    "icloud lock",
    "на icloud",
    "плата на icloud",
    "донор",
    "донорск",
    "donor parts",
    "разбор",
    "разборка",
    "комплектующ",
    "б/у плата",
    "только плата",
    "продаю плату",
    "продам плату",
    "корпуса",
    "корпусов",
    "без экрана",
    "без дисплея",
    "отдельно экран",
    "отдельно дисплей",
    "на запчасти",
    "для запчаст",
)

# В названии или кратких параметрах (summary) должно быть явно про телефон.
PHONE_REQUIRED_TERMS: tuple[str, ...] = (
    "iphone",
    "айфон",
    "samsung s",
    "самсунг s",
    "galaxy s",
    "z flip",
    "z fold",
    "флип",
    "фолд",
    "телефон",
    "смартфон",
    "mobile phone",
)

# Услуги / скупка: смотрим название + summary (без длинного описания).
NOT_SALE_TERMS: tuple[str, ...] = (
    "выкуп",
    "скупка",
    "скупаем",
    "куплю",
    "купим",
    "покупаем",
    "срочный выкуп",
    "без торга",
    "без скидок",
    "без скидки",
    "ассортимент обновляется",
    "подписавшись на наш профиль",
    "работаем без скидок",
)

KUFAR_QUERY = os.getenv(
    "KUFAR_QUERY",
    "iphone,samsung galaxy s,samsung galaxy z flip,samsung galaxy z fold",
)
KUFAR_QUERIES: tuple[str, ...] = tuple(
    q.strip()
    for q in KUFAR_QUERY.split(",")
    if q.strip()
) or ("iphone", "samsung galaxy s", "samsung galaxy z flip", "samsung galaxy z fold")
KUFAR_REGION = int(os.getenv("KUFAR_REGION", "7"))
KUFAR_SIZE = int(os.getenv("KUFAR_SIZE", "40"))
# Каталожный search-api (phm/ppm/ot) вместо широких текстовых KUFAR_QUERIES.
_kufar_catalog = os.getenv("KUFAR_USE_CATALOG", "true").strip().lower()
KUFAR_USE_CATALOG = _kufar_catalog not in ("0", "false", "no", "off")
KUFAR_CATALOG_COMPARE = os.getenv("KUFAR_CATALOG_COMPARE", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Не целый телефон: проверка по title + summary (стемы ловят стекла/стёкла).
ACCESSORY_HEADLINE_STEMS: tuple[str, ...] = (
    "коробк",
    "стекл",
    "стёкл",
    "защитн",
    "пленк",
    "плёнк",
    "чехол",
    "чехл",
    "аккумулятор",
    "акб",
    "батаре",
    "модул",
    "glass shield",
    "ceramic",
    "film",
)

WHOLE_PHONE_EXCLUDE_HEADLINE: tuple[str, ...] = (
    "клон",
    "clone",
    "replica",
    "реплик",
    "копия",
    "копии",
    "муляж",
    "подделк",
    "дубликат",
    "на запчаст",
    "для запчаст",
    "запчаст",
)
