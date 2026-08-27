import re
from html import escape
from datetime import datetime, timezone

from config import (
    AD_DESCRIPTION_MAX_CHARS,
    AD_DESCRIPTION_MAX_CHARS_REGULAR,
    DISPLAY_TZ,
    format_local_datetime,
    format_memory_volume,
    format_price,
)
from currency_display import format_triple_price
from kufar_catalog import user_city_label
from marketplace.types import normalize_country, SOURCE_AVITO
from product_catalog import category_label

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
            return format_local_datetime(ts)
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
        return dt.astimezone(DISPLAY_TZ).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return text[:32]


def truncate_ad_caption(text: str, *, max_len: int = _CAPTION_SAFE_MAX) -> str:
    """Укорачивает HTML-текст под лимит caption Telegram."""
    if len(text) <= max_len:
        return text
    link_match = re.search(
        r'(\n🔗 <a href="[^"]+">Открыть на (?:Kufar|Avito)</a>\s*)$',
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
    ad: dict,
    *,
    market_avg_price: int | None = None,
    below_market: bool = False,
    ideal_feed: bool = False,
    compact: bool = False,
    country: str | None = None,
) -> str:
    """Превращает словарь объявления в HTML-сообщение для Telegram."""
    title = _esc(ad.get("title") or "Без названия")
    user_country = normalize_country(country)

    price = ad.get("price")
    price_usd = ad.get("price_usd")
    if price is not None and isinstance(price, int):
        price_str = format_triple_price(
            price,
            country=user_country,
            price_usd_hint=price_usd if isinstance(price_usd, int) else None,
        )
    else:
        price_str = "не указана"

    location = _esc(ad.get("location") or "")
    summary = _esc((ad.get("summary") or "").strip())
    desc_raw = (ad.get("description") or "").strip()
    desc_limit = (
        AD_DESCRIPTION_MAX_CHARS_REGULAR if compact else AD_DESCRIPTION_MAX_CHARS
    )
    if len(desc_raw) > desc_limit:
        desc_raw = desc_raw[: desc_limit - 1].rstrip() + "…"
    description = _esc(desc_raw)
    link = ad.get("link") or ""
    listed = _format_list_time(ad.get("list_time"))

    parts: list[str] = []
    if ideal_feed:
        parts.append("✨ <b>Идеальные</b>")
        parts.append("")
    elif below_market:
        parts.append("🔥 <b>Ниже рынка</b>")
        parts.append("")
    parts.append(f"<b>{title}</b>")
    parts.append(f"<b>{_esc(price_str)}</b>")
    if market_avg_price is not None:
        avg_str = format_triple_price(market_avg_price, country=user_country)
        parts.append(f"Средняя · {_esc(avg_str)}")
    if summary:
        parts.append(summary)
    if location:
        parts.append(location)
    if listed and not compact:
        parts.append(f"Опубликовано · {listed}")
    if description:
        parts.append("")
        parts.append(description)
    parts.append("")
    link_label = "Открыть на Avito" if ad.get("source") == SOURCE_AVITO else "Открыть на Kufar"
    parts.append(f'🔗 <a href="{_esc(link)}">{link_label}</a>')

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
        vip_until_text = format_local_datetime(vip_until, fmt="%d.%m.%Y в %H:%M")

    vip_feed = ""
    if user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        if mode == "below_market":
            vip_feed = "\n🔥 <b>Поток:</b> ниже рынка"
        elif mode == "exchange":
            vip_feed = "\n🔄 <b>Поток:</b> только обмен"
        elif mode == "ideal":
            vip_feed = "\n✨ <b>Поток:</b> идеальные"

    paused = ""
    if not user.get("active"):
        paused = (
            "\n\n💤 <b>Уведомления на паузе</b>\n"
            "Включите · <b>«Включить»</b> или <code>/start</code>"
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
        f"📂 <b>Категория:</b> {_esc(category_label(user.get('product_category')))}\n"
        f"💾 <b>Память:</b> {_esc(mem)}\n"
        f"📍 <b>Город:</b> {_esc(user_city_label(user))}\n"
        f"📱 <b>Модели:</b> {_esc(kw)}\n"
        f"📨 <b>Отправлено объявлений:</b> {sent}"
        f"{vip_feed}"
        f"{paused}"
    )