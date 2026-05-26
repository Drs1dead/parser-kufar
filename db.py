import logging
import secrets
import shutil
import sqlite3
import string
import threading
import time
from pathlib import Path
from typing import Optional

from config import (
    DB_PATH as DB_PATH_OVERRIDE,
    DEFAULT_KEYWORDS,
    DEFAULT_MAX_PRICE,
    DEFAULT_MEMORY_VOLUMES,
    MEMORY_VOLUME_OPTIONS,
    REFERRAL_VIP_DAYS_PER_FRIEND,
    SQLITE_BUSY_TIMEOUT,
    SQLITE_SYNCHRONOUS,
    VIP_SUBSCRIPTION_DAYS,
)

log = logging.getLogger(__name__)

_SQLITE_SYNC_NUM = {"OFF": 0, "NORMAL": 1, "FULL": 2, "EXTRA": 3}[SQLITE_SYNCHRONOUS]
TRIAL_PROMO_CODE = "VIPTRIAL7"
TRIAL_PROMO_DAYS = 7


def _norm_username(username: str | None) -> str:
    if not username:
        return ""
    return username.strip().lstrip("@")[:64]


def _norm_promo_code(code: str | None) -> str:
    if not code:
        return ""
    return code.strip().upper()[:64]


def _norm_memory_volumes(volumes: list[str] | None) -> list[str]:
    allowed = set(MEMORY_VOLUME_OPTIONS)
    cleaned: list[str] = []
    for v in volumes or []:
        s = str(v).strip()
        if s in allowed and s not in cleaned:
            cleaned.append(s)
    if not cleaned:
        return list(DEFAULT_MEMORY_VOLUMES)
    return cleaned


def _memory_csv(volumes: list[str]) -> str:
    return ",".join(_norm_memory_volumes(volumes))


def _parse_memory_csv(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_MEMORY_VOLUMES)
    return _norm_memory_volumes([p.strip() for p in raw.split(",") if p.strip()])


def _generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(32):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        cur = _execute("SELECT 1 FROM users WHERE referral_code = ?", (code,))
        if cur.fetchone() is None:
            return code
    return "".join(secrets.choice(alphabet) for _ in range(12))


_USER_SELECT = (
    "chat_id, active, role, vip_until, max_price, keywords, sent_count, created_at, "
    "vip_feed_mode, username, memory_volumes, referral_code, referred_by"
)


def _row_to_user(row: tuple) -> dict:
    return {
        "chat_id": row[0],
        "active": bool(row[1]),
        "role": row[2],
        "vip_until": int(row[3] or 0),
        "max_price": row[4],
        "keywords": [k.strip() for k in row[5].split(",") if k.strip()],
        "sent_count": row[6],
        "created_at": row[7],
        "vip_feed_mode": row[8] or "normal",
        "username": (row[9] or "").strip() if len(row) > 9 else "",
        "memory_volumes": _parse_memory_csv(row[10] if len(row) > 10 else None),
        "referral_code": (row[11] or "").strip() if len(row) > 11 else "",
        "referred_by": int(row[12]) if len(row) > 12 and row[12] is not None else None,
    }


def _migrate_legacy_db(target: Path) -> None:
    """Переносит старый bot.db из корня проекта в постоянную папку data (один раз)."""
    if target.exists():
        return
    project_dir = Path(__file__).resolve().parent
    legacy = project_dir / "bot.db"
    if not legacy.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, target)
    log.info("[DB] перенесена база %s → %s", legacy, target)
    for suffix in ("-wal", "-shm"):
        side = Path(str(legacy) + suffix)
        if side.is_file():
            try:
                shutil.copy2(side, Path(str(target) + suffix))
            except OSError:
                log.warning("[DB] не удалось скопировать %s", side, exc_info=True)


def _sqlite_path() -> str:
    """
    Абсолютный путь к SQLite (не зависит от cwd).

    Приоритет:
    1) DB_PATH из .env / панели BotHost
    2) /app/data/bot.db — персистентное хранилище BotHost (не затирается при git deploy)
    3) <проект>/data/bot.db локально (с миграцией из старого bot.db в корне)
    """
    if DB_PATH_OVERRIDE:
        p = Path(DB_PATH_OVERRIDE).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    bothost_data = Path("/app/data")
    if bothost_data.is_dir():
        db_file = bothost_data / "bot.db"
        _migrate_legacy_db(db_file)
        bothost_data.mkdir(parents=True, exist_ok=True)
        return str(db_file)

    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "bot.db"
    _migrate_legacy_db(db_file)
    return str(db_file)


SQLITE_PATH = _sqlite_path()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        SQLITE_PATH,
        timeout=SQLITE_BUSY_TIMEOUT,
        check_same_thread=False,
        isolation_level=None,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA synchronous={_SQLITE_SYNC_NUM}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


conn = _connect()
_db_lock = threading.RLock()


def _execute(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _db_lock:
        return conn.execute(sql, params)


def _executescript(script: str) -> None:
    with _db_lock:
        conn.executescript(script)


def _table_columns(name: str) -> set[str]:
    cur = _execute(f"PRAGMA table_info({name})")
    return {row[1] for row in cur.fetchall()}


def init_db() -> None:
    log.debug("sqlite path=%s", SQLITE_PATH)
    # Старая схема (с прошлых экспериментов) — сносим, чтобы создать заново
    existing = _table_columns("users")
    if existing and "active" not in existing:
        _execute("DROP TABLE users")

    _executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            chat_id    INTEGER PRIMARY KEY,
            active     INTEGER NOT NULL DEFAULT 1,
            role       TEXT    NOT NULL DEFAULT 'regular',
            vip_until  INTEGER NOT NULL DEFAULT 0,
            max_price  INTEGER NOT NULL,
            keywords   TEXT    NOT NULL,
            sent_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS seen_ads (
            chat_id INTEGER NOT NULL,
            link    TEXT    NOT NULL,
            seen_at INTEGER NOT NULL,
            PRIMARY KEY (chat_id, link)
        );
        
        CREATE TABLE IF NOT EXISTS sent_prices (
            chat_id    INTEGER NOT NULL,
            link       TEXT    NOT NULL,
            device_key TEXT    NOT NULL,
            price      INTEGER NOT NULL,
            sent_at    INTEGER NOT NULL,
            PRIMARY KEY (chat_id, link)
        );
        
        CREATE TABLE IF NOT EXISTS market_prices (
            link       TEXT PRIMARY KEY,
            device_key TEXT    NOT NULL,
            price      INTEGER NOT NULL,
            sent_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promo_codes (
            code       TEXT PRIMARY KEY,
            vip_days   INTEGER NOT NULL,
            max_uses   INTEGER NOT NULL DEFAULT 0,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS promo_activations (
            chat_id INTEGER NOT NULL,
            code    TEXT    NOT NULL,
            used_at INTEGER NOT NULL,
            PRIMARY KEY (chat_id, code),
            FOREIGN KEY (code) REFERENCES promo_codes(code) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_seen_chat ON seen_ads(chat_id);
        CREATE INDEX IF NOT EXISTS idx_sent_prices_lookup ON sent_prices(chat_id, device_key);
        CREATE INDEX IF NOT EXISTS idx_market_prices_device ON market_prices(device_key);
        CREATE INDEX IF NOT EXISTS idx_promo_activations_code ON promo_activations(code);
        """
    )
    cols = _table_columns("users")
    if "role" not in cols:
        _execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'regular'")
    if "vip_until" not in cols:
        _execute("ALTER TABLE users ADD COLUMN vip_until INTEGER NOT NULL DEFAULT 0")
    if "vip_feed_mode" not in cols:
        _execute(
            "ALTER TABLE users ADD COLUMN vip_feed_mode TEXT NOT NULL DEFAULT 'normal'"
        )
    if "username" not in cols:
        _execute("ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''")
    cols = _table_columns("users")
    if "memory_volumes" not in cols:
        _execute(
            "ALTER TABLE users ADD COLUMN memory_volumes TEXT NOT NULL DEFAULT '64'"
        )
    if "referral_code" not in cols:
        _execute("ALTER TABLE users ADD COLUMN referral_code TEXT NOT NULL DEFAULT ''")
    if "referred_by" not in cols:
        _execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
    _executescript(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            referred_chat_id  INTEGER PRIMARY KEY,
            referrer_chat_id  INTEGER NOT NULL,
            created_at        INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_chat_id);
        """
    )
    _backfill_referral_codes()
    promo_cols = _table_columns("promo_codes")
    if "max_uses" not in promo_cols:
        _execute("ALTER TABLE promo_codes ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 0")
    _execute(
        "INSERT OR IGNORE INTO promo_codes (code, vip_days, max_uses, is_active, created_at) VALUES (?, ?, 0, 1, ?)",
        (TRIAL_PROMO_CODE, TRIAL_PROMO_DAYS, int(time.time())),
    )
    _cleanup_used_up_promo_codes()


def _backfill_referral_codes() -> None:
    cur = _execute(
        "SELECT chat_id FROM users WHERE referral_code IS NULL OR referral_code = ''"
    )
    for (chat_id,) in cur.fetchall():
        _execute(
            "UPDATE users SET referral_code = ? WHERE chat_id = ?",
            (_generate_referral_code(), chat_id),
        )


def update_user_username(chat_id: int, username: str | None) -> None:
    """Telegram @username без «@»; пусто — сброс."""
    _execute(
        "UPDATE users SET username = ? WHERE chat_id = ?",
        (_norm_username(username), chat_id),
    )


def add_user(chat_id: int, *, username: str | None = None) -> bool:
    """Добавить пользователя или реактивировать. True если это новый юзер."""
    u = _norm_username(username)
    cur = _execute("SELECT active FROM users WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    if row is None:
        ref_code = _generate_referral_code()
        _execute(
            "INSERT INTO users (chat_id, active, role, vip_until, max_price, keywords, "
            "created_at, vip_feed_mode, username, memory_volumes, referral_code) "
            "VALUES (?, 1, 'regular', 0, ?, ?, ?, 'normal', ?, ?, ?)",
            (
                chat_id,
                DEFAULT_MAX_PRICE,
                ",".join(DEFAULT_KEYWORDS),
                int(time.time()),
                u,
                _memory_csv(list(DEFAULT_MEMORY_VOLUMES)),
                ref_code,
            ),
        )
        return True
    if row[0] == 0:
        _execute(
            "UPDATE users SET active = 1, username = ? WHERE chat_id = ?",
            (u, chat_id),
        )
    else:
        _execute("UPDATE users SET username = ? WHERE chat_id = ?", (u, chat_id))
    return False


def set_active(chat_id: int, active: bool) -> None:
    _execute(
        "UPDATE users SET active = ? WHERE chat_id = ?",
        (1 if active else 0, chat_id),
    )


def get_user(chat_id: int) -> Optional[dict]:
    _expire_vip(chat_id)
    cur = _execute(
        f"SELECT {_USER_SELECT} FROM users WHERE chat_id = ?",
        (chat_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    user = _row_to_user(row)
    if user.get("role") != "vip" and len(user.get("memory_volumes") or []) > 1:
        norm = list(DEFAULT_MEMORY_VOLUMES)
        _execute(
            "UPDATE users SET memory_volumes = ? WHERE chat_id = ?",
            (_memory_csv(norm), chat_id),
        )
        user["memory_volumes"] = norm
    return user


def count_users_total() -> int:
    cur = _execute("SELECT COUNT(*) FROM users")
    return int(cur.fetchone()[0])


def count_users_active() -> int:
    cur = _execute("SELECT COUNT(*) FROM users WHERE active = 1")
    return int(cur.fetchone()[0])


def count_users_vip() -> int:
    _expire_all_vip()
    now = int(time.time())
    cur = _execute(
        "SELECT COUNT(*) FROM users WHERE role = 'vip' AND vip_until > ?",
        (now,),
    )
    return int(cur.fetchone()[0])


def list_users_page(*, offset: int, limit: int) -> list[dict]:
    _expire_all_vip()
    cur = _execute(
        f"SELECT {_USER_SELECT} FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [_row_to_user(r) for r in cur.fetchall()]


def clear_market_prices() -> int:
    cur = _execute("DELETE FROM market_prices")
    return cur.rowcount if cur.rowcount is not None else 0


def get_active_users() -> list[dict]:
    _expire_all_vip()
    cur = _execute(f"SELECT {_USER_SELECT} FROM users WHERE active = 1")
    return [_row_to_user(r) for r in cur.fetchall()]


def update_max_price(chat_id: int, max_price: int) -> None:
    _execute(
        "UPDATE users SET max_price = ? WHERE chat_id = ?",
        (max_price, chat_id),
    )


def update_keywords(chat_id: int, keywords: list[str]) -> None:
    cleaned = [k.strip().lower() for k in keywords if k.strip()]
    _execute(
        "UPDATE users SET keywords = ? WHERE chat_id = ?",
        (",".join(cleaned), chat_id),
    )


def update_memory_volumes(chat_id: int, volumes: list[str]) -> None:
    _execute(
        "UPDATE users SET memory_volumes = ? WHERE chat_id = ?",
        (_memory_csv(volumes), chat_id),
    )


def ensure_referral_code(chat_id: int) -> str:
    user = get_user(chat_id)
    if user is None:
        return ""
    code = (user.get("referral_code") or "").strip()
    if code:
        return code
    code = _generate_referral_code()
    _execute(
        "UPDATE users SET referral_code = ? WHERE chat_id = ?",
        (code, chat_id),
    )
    return code


def get_user_by_referral_code(code: str) -> Optional[dict]:
    ref = (code or "").strip().upper()
    if not ref:
        return None
    cur = _execute(
        f"SELECT {_USER_SELECT} FROM users WHERE referral_code = ?",
        (ref,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def count_referrals(referrer_chat_id: int) -> int:
    cur = _execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_chat_id = ?",
        (referrer_chat_id,),
    )
    return int(cur.fetchone()[0])


def grant_vip_days(chat_id: int, days: int) -> None:
    set_vip(chat_id, days=max(1, int(days)))


def process_referral_signup(new_chat_id: int, ref_code: str) -> bool:
    """Начисляет VIP-дни пригласившему за нового друга. True если бонус выдан."""
    referrer = get_user_by_referral_code(ref_code)
    if referrer is None:
        return False
    referrer_id = int(referrer["chat_id"])
    if referrer_id == new_chat_id:
        return False
    cur = _execute(
        "SELECT 1 FROM referrals WHERE referred_chat_id = ?",
        (new_chat_id,),
    )
    if cur.fetchone() is not None:
        return False
    now = int(time.time())
    try:
        _execute(
            "INSERT INTO referrals (referred_chat_id, referrer_chat_id, created_at) "
            "VALUES (?, ?, ?)",
            (new_chat_id, referrer_id, now),
        )
    except sqlite3.IntegrityError:
        return False
    _execute(
        "UPDATE users SET referred_by = ? WHERE chat_id = ? AND referred_by IS NULL",
        (referrer_id, new_chat_id),
    )
    grant_vip_days(referrer_id, REFERRAL_VIP_DAYS_PER_FRIEND)
    log.info(
        "referral bonus referrer=%s new_user=%s days=%s",
        referrer_id,
        new_chat_id,
        REFERRAL_VIP_DAYS_PER_FRIEND,
    )
    return True


def reset_user_filters(chat_id: int) -> None:
    _execute(
        "UPDATE users SET max_price = ?, keywords = ?, memory_volumes = ? WHERE chat_id = ?",
        (
            DEFAULT_MAX_PRICE,
            ",".join(DEFAULT_KEYWORDS),
            _memory_csv(list(DEFAULT_MEMORY_VOLUMES)),
            chat_id,
        ),
    )


def is_seen(chat_id: int, link: str) -> bool:
    cur = _execute(
        "SELECT 1 FROM seen_ads WHERE chat_id = ? AND link = ?",
        (chat_id, link),
    )
    return cur.fetchone() is not None


def mark_seen(chat_id: int, link: str) -> None:
    _execute(
        "INSERT OR IGNORE INTO seen_ads (chat_id, link, seen_at) VALUES (?, ?, ?)",
        (chat_id, link, int(time.time())),
    )


def count_seen(chat_id: int) -> int:
    cur = _execute("SELECT COUNT(*) FROM seen_ads WHERE chat_id = ?", (chat_id,))
    return int(cur.fetchone()[0])


def increment_sent(chat_id: int) -> None:
    _execute(
        "UPDATE users SET sent_count = sent_count + 1 WHERE chat_id = ?",
        (chat_id,),
    )


def save_sent_price(chat_id: int, link: str, device_key: str, price: int) -> None:
    _execute(
        "INSERT OR IGNORE INTO sent_prices (chat_id, link, device_key, price, sent_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (chat_id, link, device_key, price, int(time.time())),
    )


def avg_sent_price(chat_id: int, device_key: str) -> int | None:
    cur = _execute(
        "SELECT AVG(price) FROM sent_prices WHERE chat_id = ? AND device_key = ?",
        (chat_id, device_key),
    )
    row = cur.fetchone()
    avg_value = row[0] if row else None
    if avg_value is None:
        return None
    return int(avg_value)


def save_market_price(link: str, device_key: str, price: int) -> None:
    _execute(
        "INSERT OR IGNORE INTO market_prices (link, device_key, price, sent_at) "
        "VALUES (?, ?, ?, ?)",
        (link, device_key, price, int(time.time())),
    )


def avg_market_price(device_key: str) -> int | None:
    cur = _execute(
        "SELECT AVG(price) FROM market_prices WHERE device_key = ?",
        (device_key,),
    )
    row = cur.fetchone()
    avg_value = row[0] if row else None
    if avg_value is None:
        return None
    return int(avg_value)


def update_vip_feed_mode(chat_id: int, mode: str) -> None:
    if mode not in ("normal", "below_market", "exchange"):
        return
    _execute(
        "UPDATE users SET vip_feed_mode = ? WHERE chat_id = ? AND role = 'vip'",
        (mode, chat_id),
    )


def checkpoint_wal() -> None:
    """Сброс WAL на диск (безопаснее при копировании bot.db и при остановке процесса)."""
    try:
        _execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error:
        log.debug("wal_checkpoint skipped", exc_info=True)


def close() -> None:
    try:
        checkpoint_wal()
    finally:
        with _db_lock:
            conn.close()


def set_vip(chat_id: int, *, days: int = VIP_SUBSCRIPTION_DAYS) -> None:
    ensure_referral_code(chat_id)
    now = int(time.time())
    add_seconds = max(1, days) * 24 * 60 * 60
    cur = _execute(
        "SELECT role, vip_until FROM users WHERE chat_id = ?", (chat_id,)
    )
    row = cur.fetchone()
    if row is None:
        return
    role, vip_until_raw = row[0], int(row[1] or 0)
    if role == "vip" and vip_until_raw > now:
        vip_until = max(now, vip_until_raw) + add_seconds
    else:
        vip_until = now + add_seconds
    _execute(
        "UPDATE users SET role = 'vip', vip_until = ? WHERE chat_id = ?",
        (vip_until, chat_id),
    )


def redeem_promo_code(chat_id: int, code: str) -> tuple[str, int | None]:
    _cleanup_used_up_promo_codes()
    promo = _norm_promo_code(code)
    if not promo:
        return "not_found", None

    cur = _execute(
        "SELECT vip_days, is_active, max_uses FROM promo_codes WHERE code = ?",
        (promo,),
    )
    row = cur.fetchone()
    if row is None or int(row[1] or 0) != 1:
        return "not_found", None

    max_uses = int(row[2] or 0)
    if max_uses > 0 and _promo_uses_count(promo) >= max_uses:
        _execute("DELETE FROM promo_codes WHERE code = ?", (promo,))
        return "not_found", None

    try:
        _execute(
            "INSERT INTO promo_activations (chat_id, code, used_at) VALUES (?, ?, ?)",
            (chat_id, promo, int(time.time())),
        )
    except sqlite3.IntegrityError:
        return "already_used", None

    days = max(1, int(row[0] or 0))
    if max_uses > 0 and _promo_uses_count(promo) >= max_uses:
        _execute("DELETE FROM promo_codes WHERE code = ?", (promo,))
    return "ok", days


def create_promo_code(code: str, *, vip_days: int, max_uses: int) -> bool:
    promo = _norm_promo_code(code)
    if not promo:
        return False
    try:
        _execute(
            "INSERT INTO promo_codes (code, vip_days, max_uses, is_active, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (promo, max(1, int(vip_days)), max(0, int(max_uses)), int(time.time())),
        )
    except sqlite3.IntegrityError:
        return False
    return True


def find_users_by_username(username: str, *, limit: int = 10) -> list[dict]:
    un = _norm_username(username)
    if not un:
        return []
    cur = _execute(
        f"SELECT {_USER_SELECT} FROM users WHERE LOWER(username) = LOWER(?) "
        "ORDER BY created_at DESC LIMIT ?",
        (un, max(1, int(limit))),
    )
    return [_row_to_user(row) for row in cur.fetchall()]


def delete_user_completely(chat_id: int) -> bool:
    cur = _execute("SELECT 1 FROM users WHERE chat_id = ?", (chat_id,))
    if cur.fetchone() is None:
        return False
    _execute("DELETE FROM seen_ads WHERE chat_id = ?", (chat_id,))
    _execute("DELETE FROM sent_prices WHERE chat_id = ?", (chat_id,))
    _execute("DELETE FROM promo_activations WHERE chat_id = ?", (chat_id,))
    _execute(
        "DELETE FROM referrals WHERE referred_chat_id = ? OR referrer_chat_id = ?",
        (chat_id, chat_id),
    )
    _execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
    return True


def delete_promo_code(code: str) -> bool:
    promo = _norm_promo_code(code)
    if not promo:
        return False
    cur = _execute("SELECT 1 FROM promo_codes WHERE code = ?", (promo,))
    if cur.fetchone() is None:
        return False
    _execute("DELETE FROM promo_activations WHERE code = ?", (promo,))
    _execute("DELETE FROM promo_codes WHERE code = ?", (promo,))
    return True


def list_active_promo_codes() -> list[dict]:
    _cleanup_used_up_promo_codes()
    cur = _execute(
        "SELECT code, vip_days, max_uses, created_at FROM promo_codes WHERE is_active = 1 ORDER BY created_at DESC"
    )
    rows = []
    for code, vip_days, max_uses, created_at in cur.fetchall():
        uses = _promo_uses_count(code)
        rows.append(
            {
                "code": code,
                "vip_days": int(vip_days or 0),
                "max_uses": int(max_uses or 0),
                "uses": uses,
                "created_at": int(created_at or 0),
            }
        )
    return rows


def _regular_defaults_sql_values() -> tuple:
    return (
        DEFAULT_MAX_PRICE,
        ",".join(DEFAULT_KEYWORDS),
        _memory_csv(list(DEFAULT_MEMORY_VOLUMES)),
    )


def revoke_vip(chat_id: int) -> None:
    max_price, keywords, memory = _regular_defaults_sql_values()
    _execute(
        "UPDATE users SET role = 'regular', vip_until = 0, vip_feed_mode = 'normal', "
        "max_price = ?, keywords = ?, memory_volumes = ? "
        "WHERE chat_id = ?",
        (max_price, keywords, memory, chat_id),
    )


def _expire_vip(chat_id: int) -> None:
    now = int(time.time())
    max_price, keywords, memory = _regular_defaults_sql_values()
    _execute(
        "UPDATE users SET role = 'regular', vip_until = 0, vip_feed_mode = 'normal', "
        "max_price = ?, keywords = ?, memory_volumes = ? "
        "WHERE chat_id = ? AND role = 'vip' AND vip_until > 0 AND vip_until < ?",
        (max_price, keywords, memory, chat_id, now),
    )


def _expire_all_vip() -> None:
    now = int(time.time())
    max_price, keywords, memory = _regular_defaults_sql_values()
    _execute(
        "UPDATE users SET role = 'regular', vip_until = 0, vip_feed_mode = 'normal', "
        "max_price = ?, keywords = ?, memory_volumes = ? "
        "WHERE role = 'vip' AND vip_until > 0 AND vip_until < ?",
        (max_price, keywords, memory, now),
    )


def _promo_uses_count(code: str) -> int:
    cur = _execute(
        "SELECT COUNT(*) FROM promo_activations WHERE code = ?",
        (_norm_promo_code(code),),
    )
    return int(cur.fetchone()[0])


def _cleanup_used_up_promo_codes() -> None:
    _execute(
        """
        DELETE FROM promo_codes
        WHERE max_uses > 0
          AND (
              SELECT COUNT(*)
              FROM promo_activations
              WHERE promo_activations.code = promo_codes.code
          ) >= max_uses
        """
    )
