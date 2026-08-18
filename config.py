import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

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

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
REGULAR_CHECK_INTERVAL = int(os.getenv("REGULAR_CHECK_INTERVAL", "600"))
VIP_CHECK_INTERVAL = int(os.getenv("VIP_CHECK_INTERVAL", "60"))

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

DEFAULT_KEYWORDS = [
    "iphone x",
    "iphone xs",
    "iphone xs max",
    "iphone xr",
    "iphone 11",
]
DEVICE_CATALOG = [
    "iphone se",
    "iphone x",
    "iphone xs",
    "iphone xs max",
    "iphone xr",
    "iphone 11",
    "iphone 11 pro",
    "iphone 11 pro max",
    "iphone 12",
    "iphone 12 mini",
    "iphone 12 pro",
    "iphone 12 pro max",
    "iphone 13",
    "iphone 13 mini",
    "iphone 13 pro",
    "iphone 13 pro max",
    "iphone 14",
    "iphone 14 plus",
    "iphone 14 pro",
    "iphone 14 pro max",
    "iphone 15",
    "iphone 15 plus",
    "iphone 15 pro",
    "iphone 15 pro max",
    "iphone 16",
    "iphone 16 plus",
    "iphone 16 pro",
    "iphone 16 pro max",
    "iphone 17",
    "iphone 17 pro",
    "iphone 17 pro max",
    "samsung galaxy s20",
    "samsung galaxy s20 plus",
    "samsung galaxy s20 ultra",
    "samsung galaxy s21",
    "samsung galaxy s21 plus",
    "samsung galaxy s21 ultra",
    "samsung galaxy s22",
    "samsung galaxy s22 plus",
    "samsung galaxy s22 ultra",
    "samsung galaxy s23",
    "samsung galaxy s23 plus",
    "samsung galaxy s23 ultra",
    "samsung galaxy s24",
    "samsung galaxy s24 plus",
    "samsung galaxy s24 ultra",
    "samsung galaxy s25",
    "samsung galaxy s25 plus",
    "samsung galaxy s25 ultra",
    "samsung galaxy z flip",
    "samsung galaxy z flip 5g",
    "samsung galaxy z flip 3",
    "samsung galaxy z flip 4",
    "samsung galaxy z flip 5",
    "samsung galaxy z flip 6",
    "samsung galaxy z flip 7",
    "samsung galaxy z flip 7 fe",
    "samsung galaxy z fold",
    "samsung galaxy z fold 2",
    "samsung galaxy z fold 3",
    "samsung galaxy z fold 4",
    "samsung galaxy z fold 5",
    "samsung galaxy z fold 6",
    "samsung galaxy z fold 7",
]

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
