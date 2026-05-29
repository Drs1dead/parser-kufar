import re
from html import escape
from datetime import datetime, timezone

from config import format_memory_volume, format_price

TELEGRAM_CAPTION_MAX = 1024
_CAPTION_SAFE_MAX = 980


def _esc(value) -> str:
    if value is None:
        return ""
    return escape(str(value))


def _format_list_time(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        try:
            ts = float(raw)
            if ts > 1e12:
                ts /= 1000.0
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
            return dt.strftime("%d.%m.%Y %H:%M")
        except (OSError, OverflowError, ValueError):
            return ""
    text = str(raw).strip()
    if not text:
        return ""
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return text[:32]


def truncate_ad_caption(text: str, *, max_len: int = _CAPTION_SAFE_MAX) -> str:
    """Укорачивает HTML-текст под лимит caption Telegram."""
    if len(text) <= max_len:
        return text
    link_match = re.search(
        r'(\n🔗 <a href="[^"]+">Открыть на Kufar</a>\s*)$',
        text,
    )
    suffix = link_match.group(1) if link_match else ""
    body = text[: len(text) - len(suffix)] if suffix else text
    reserve = max_len - len(suffix) - 20
    if reserve < 80:
        return text[:max_len]
    trimmed = body[:reserve].rstrip()
    return f"{trimmed}\n\n<i>…</i>{suffix}"


def format_ad(
    ad: dict, *, market_avg_price: int | None = None, below_market: bool = False
) -> str:
    """Превращает словарь объявления в HTML-сообщение для Telegram."""
    title = _esc(ad.get("title") or "Без названия")

    price = ad.get("price")
    price_usd = ad.get("price_usd")
    if price is not None:
        price_str = format_price(price)
        if price_usd:
            price_str += f" · ≈ {price_usd}$"
    else:
        price_str = "не указана"

    location = _esc(ad.get("location") or "")
    summary = _esc((ad.get("summary") or "").strip())
    description = _esc(ad.get("description") or "")
    link = ad.get("link") or ""
    listed = _format_list_time(ad.get("list_time"))

    parts: list[str] = []
    if below_market:
        parts.append("🔥 <b>Ниже рыночной цены</b>")
        parts.append("")
    parts.append(f"📱 <b>{title}</b>")
    parts.append(f"💰 <b>{_esc(price_str)}</b>")
    if market_avg_price is not None:
        parts.append(f"📊 Средняя на Kufar · <b>{format_price(market_avg_price)}</b>")
    if summary:
        parts.append(f"📋 {summary}")
    if location:
        parts.append(f"📍 {location}")
    if listed:
        parts.append(f"🕐 Опубликовано · {listed}")
    if description:
        parts.append("")
        parts.append(description)
    parts.append("")
    parts.append(f'🔗 <a href="{_esc(link)}">Открыть на Kufar</a>')

    return "\n".join(parts)


def format_status(user: dict) -> str:
    active = "🔔 включены" if user.get("active") else "🔕 на паузе"
    keywords = user.get("keywords") or []
    kw = ", ".join(keywords) if keywords else "—"
    mem_vols = user.get("memory_volumes") or ["64"]
    mem = ", ".join(format_memory_volume(v) for v in mem_vols)
    max_price = user.get("max_price") or 0
    sent = user.get("sent_count", 0)
    role = "VIP ⭐" if user.get("role") == "vip" else "обычный"
    vip_until = int(user.get("vip_until") or 0)
    vip_until_text = "—"
    if vip_until > 0:
        dt = datetime.fromtimestamp(vip_until, tz=timezone.utc).astimezone()
        vip_until_text = dt.strftime("%d.%m.%Y в %H:%M")

    vip_feed = ""
    if user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        if mode == "below_market":
            vip_feed = "\n🔥 <b>Поток:</b> ниже рынка"
        elif mode == "exchange":
            vip_feed = "\n🔄 <b>Поток:</b> только обмен"

    paused = ""
    if not user.get("active"):
        paused = (
            "\n\n💤 <b>Уведомления на паузе</b>\n"
            "Включите · <b>«Включить уведомления»</b> или <code>/start</code>"
        )

    cid = user.get("chat_id")
    un = (user.get("username") or "").strip()
    if un:
        uq = _esc(un)
        username_line = f"🆔 <b>Telegram:</b> <a href=\"https://t.me/{uq}\">@{uq}</a>\n"
    elif cid is not None:
        cid_i = int(cid)
        username_line = (
            f"🆔 <b>Telegram:</b> без @ · "
            f'<a href="tg://user?id={cid_i}">открыть профиль</a>\n'
        )
    else:
        username_line = "🆔 <b>Telegram:</b> —\n"

    return (
        f"📋 <b>Карточка пользователя</b>\n\n"
        f"{username_line}"
        f"👤 <b>Тип:</b> {role}\n"
        f"⭐ <b>VIP до:</b> {vip_until_text}\n"
        f"📬 <b>Рассылка:</b> {active}\n"
        f"💰 <b>Цена до:</b> {format_price(max_price)}\n"
        f"💾 <b>Память:</b> {_esc(mem)}\n"
        f"📱 <b>Модели:</b> {_esc(kw)}\n"
        f"📨 <b>Отправлено объявлений:</b> {sent}"
        f"{vip_feed}"
        f"{paused}"
    )
