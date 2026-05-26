from html import escape
from datetime import datetime, timezone

from config import format_memory_volume, format_price


def _esc(value) -> str:
    if value is None:
        return ""
    return escape(str(value))


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
    description = _esc(ad.get("description") or "")
    link = ad.get("link") or ""

    parts: list[str] = []
    if below_market:
        parts.append("🔥 <b>Ниже рыночной цены</b>")
        parts.append("")
    parts.append(f"📱 <b>{title}</b>")
    parts.append(f"💰 <b>{_esc(price_str)}</b>")
    if market_avg_price is not None:
        parts.append(f"📊 Средняя на Kufar · <b>{format_price(market_avg_price)}</b>")
    if location:
        parts.append(f"📍 {_esc(location)}")
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
