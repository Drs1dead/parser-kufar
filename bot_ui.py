"""Тексты и клавиатуры бота — отдельно от обработчиков."""
import time
from datetime import datetime, timezone

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    CURRENCY_SIGN,
    DEFAULT_MEMORY_VOLUMES,
    MEMORY_VOLUME_OPTIONS,
    REFERRAL_VIP_DAYS_PER_FRIEND,
    REGULAR_CHECK_INTERVAL,
    VIP_CHECK_INTERVAL,
    VIP_PRICE_USD,
    format_memory_volume,
    format_price,
)
from db import count_referrals, ensure_referral_code

GOODS_CRUMB = "📱 <b>Товары</b>"

BOT_USERNAME: str = ""

HELP_TEXT = (
    "💡 <b>Как пользоваться ботом</b>\n\n"
    "Бот ищет объявления на <b>Kufar.by</b> и присылает подходящие вам в Telegram. "
    f"Все цены — в <b>белорусских рублях ({CURRENCY_SIGN})</b>.\n\n"
    "<b>🚀 С чего начать</b>\n"
    "1️⃣ <b>Товары</b> — отметьте модели телефонов\n"
    "2️⃣ <b>Память</b> и <b>Цена</b> — уточните фильтр\n"
    "3️⃣ <b>Включить уведомления</b> — в главном меню\n\n"
    "<b>Настройки</b>\n"
    "📱 Товары — какие модели искать\n"
    "💾 Память — 64–512 ГБ, «более» = от 512 ГБ\n"
    f"💰 Цена — не дороже выбранной суммы ({CURRENCY_SIGN})\n\n"
    "<b>Уведомления</b>\n"
    "🔔 Включены — новые объявления в чат\n"
    "🔕 Пауза — временно ничего не присылать\n\n"
    "⭐ <b>VIP</b> — больше моделей, особые потоки, промокод, приглашение друзей\n\n"
    "📰 Новости — <a href='https://t.me/kufarsup'>@kufarsup</a>"
)


def _kw_count(user: dict | None) -> int:
    if not user:
        return 0
    return len(user.get("keywords") or [])


def _memory_display(volumes: list[str] | None) -> str:
    vols = volumes or list(DEFAULT_MEMORY_VOLUMES)
    parts = [format_memory_volume(v) for v in vols]
    return ", ".join(parts) if parts else format_memory_volume("64")


def _vip_status_lines(user: dict | None) -> list[str]:
    if not user:
        return ["👤 <b>Аккаунт:</b> —"]
    now = int(time.time())
    vip_until = int(user.get("vip_until") or 0)
    if user.get("role") == "vip" and vip_until > now:
        dt = datetime.fromtimestamp(vip_until, tz=timezone.utc).astimezone()
        until = dt.strftime("%d.%m.%Y в %H:%M")
        return [
            "👤 <b>Аккаунт:</b> VIP ⭐",
            f"📅 <b>Активен до:</b> {until}",
        ]
    return [
        "👤 <b>Аккаунт:</b> обычный",
        "⭐ <b>VIP:</b> не подключён",
    ]


def referral_link_for_user(user: dict | None) -> str:
    if not user or not BOT_USERNAME:
        return ""
    chat_id = user.get("chat_id")
    if chat_id is None:
        return ""
    code = ensure_referral_code(int(chat_id))
    if not code:
        return ""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{code}"


def back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")]


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[back_row()])


def _new_user_intro() -> str:
    return (
        "<b>🚀 Быстрый старт</b>\n"
        "1️⃣ <b>Товары</b> — выберите модели\n"
        f"2️⃣ <b>Цена</b> — лимит в {CURRENCY_SIGN}\n"
        "3️⃣ <b>Включить уведомления</b> 👇"
    )


def home_text(user: dict | None, *, is_new: bool) -> str:
    if user is None:
        return (
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Бот помогает находить телефоны на <b>Kufar.by</b>.\n"
            f"Цены — в белорусских рублях (<b>{CURRENCY_SIGN}</b>).\n\n"
            "Напишите любое сообщение — откроется меню."
        )

    active = user.get("active")
    sub = "🔔 включены" if active else "🔕 на паузе"
    models_n = _kw_count(user)
    max_p = user.get("max_price") or 0
    model_word = _plural_models(models_n)

    if is_new:
        lines = [
            "👋 <b>Рады видеть вас!</b>",
            "",
            "Мы присылаем подходящие объявления с Kufar прямо в этот чат.",
            f"Все суммы — в <b>белорусских рублях ({CURRENCY_SIGN})</b>.",
            "",
            _new_user_intro(),
            "",
            "━━━━ <b>Ваши настройки</b> ━━━━",
        ]
    else:
        lines = [
            "👋 <b>С возвращением!</b>",
            "",
            "━━━━ <b>Сейчас</b> ━━━━",
        ]

    lines += [
        f"📬 Уведомления · <b>{sub}</b>",
        f"📱 Модели · <b>{models_n}</b> {model_word}",
        f"💾 Память · <b>{_memory_display(user.get('memory_volumes'))}</b>",
        f"💰 Цена · до <b>{format_price(max_p)}</b>",
    ]

    if models_n == 0:
        lines += ["", "💡 <i>Сначала выберите модели в «Товары» — иначе искать нечего.</i>"]

    if not active:
        interval_min = max(1, REGULAR_CHECK_INTERVAL // 60)
        if user.get("role") == "vip":
            interval_min = max(1, VIP_CHECK_INTERVAL // 60)
        lines += [
            "",
            "💤 <i>Новые объявления пока не приходят.</i>",
            "Нажмите <b>«Включить уведомления»</b> внизу 👇",
            f"<i>После включения первые совпадения обычно в течение ~{interval_min} мин.</i>",
        ]

    mode = user.get("vip_feed_mode") or "normal"
    if user.get("role") == "vip":
        if mode == "below_market":
            lines += ["", "🔥 Доп. поток · <b>ниже рынка</b>"]
        elif mode == "exchange":
            lines += ["", "🔄 Доп. поток · <b>только обмен</b>"]
        elif mode == "ideal":
            lines += ["", "✨ Доп. поток · <b>идеальные (бета)</b>"]
        else:
            lines += ["", "⭐ VIP активен — настройки во вкладке <b>VIP</b>"]
    elif not is_new:
        lines += ["", "⭐ Больше возможностей — во вкладке <b>VIP</b>"]

    lines += ["", "👇 <b>Меню</b>"]
    return "\n".join(lines)


def _plural_models(n: int) -> str:
    n = abs(n) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        return "моделей"
    if n1 == 1:
        return "модель"
    if 2 <= n1 <= 4:
        return "модели"
    return "моделей"


def home_keyboard(*, is_admin: bool, user: dict | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if user and user.get("active"):
        rows.append(
            [InlineKeyboardButton(text="🔕 Пауза", callback_data="nav:stop")]
        )
    elif user:
        rows.append(
            [InlineKeyboardButton(text="🔔 Включить уведомления", callback_data="nav:resume")]
        )
    rows.append([InlineKeyboardButton(text="📱 Товары и модели", callback_data="nav:goods")])
    rows.append(
        [
            InlineKeyboardButton(text="💰 Цена", callback_data="nav:price"),
            InlineKeyboardButton(text="💾 Память", callback_data="nav:memory"),
        ]
    )
    rows.append([InlineKeyboardButton(text="⭐ VIP", callback_data="nav:vip")])
    rows.append([InlineKeyboardButton(text="💡 Помощь", callback_data="nav:help")])
    if is_admin:
        rows.append([InlineKeyboardButton(text="🔐 Админ-панель", callback_data="nav:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_text(user: dict | None) -> str:
    lines = ["⭐ <b>VIP</b>", "", *_vip_status_lines(user)]

    if user and user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        if mode == "below_market":
            lines.append("🔥 Поток · ниже рынка")
        elif mode == "exchange":
            lines.append("🔄 Поток · только обмен")
        elif mode == "ideal":
            lines.append("✨ Поток · идеальные (бета)")
            lines.append(
                "<i>Только «Отличное»/«Хорошее», явный АКБ ≥ 75%, без поломок и замен. "
                "Нет данных — лот не приходит. Бета.</i>"
            )
        else:
            lines.append("📬 Поток · обычная рассылка")
        lines.append("")
        lines.append("<i>Модели — в «Товары». Потоки — кнопками ниже.</i>")
    else:
        lines += [
            "",
            "📱 без лимита моделей · 🔍 жёсткие фильтры · 🔥 ниже рынка · 🔄 обмен · ✨ идеальные",
            f"💳 <b>{VIP_PRICE_USD}$</b> / 30 дн. · @manohio",
            "",
            "<i>Есть промокод — кнопка ниже.</i>",
        ]

    if user and user.get("chat_id") is not None:
        cid = int(user["chat_id"])
        ref_n = count_referrals(cid)
        link = referral_link_for_user(user)
        days = REFERRAL_VIP_DAYS_PER_FRIEND
        lines += ["", f"🎁 +{days} дн. VIP за друга · приглашено: <b>{ref_n}</b>"]
        if link:
            lines.append(f"🔗 <code>{link}</code>")

    return "\n".join(lines)


def vip_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if user and user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        bm = "🔥 Ниже рынка ✅" if mode == "below_market" else "🔥 Ниже рынка"
        ex = "🔄 Обмен ✅" if mode == "exchange" else "🔄 Обмен"
        idl = "✨ Идеальные (бета) ✅" if mode == "ideal" else "✨ Идеальные (бета)"
        rows.append(
            [
                InlineKeyboardButton(text=bm, callback_data="nav:vipf:bm"),
                InlineKeyboardButton(text=ex, callback_data="nav:vipf:ex"),
            ]
        )
        rows.append(
            [InlineKeyboardButton(text=idl, callback_data="nav:vipf:ideal")]
        )
    rows.append([InlineKeyboardButton(text="🎟 Промокод", callback_data="nav:promo")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def memory_screen_text(user: dict | None) -> str:
    vols = (user or {}).get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
    selected = _memory_display(vols)
    if user and user.get("role") == "vip":
        limit = "⭐ VIP · можно выбрать <b>несколько</b> объёмов"
    else:
        limit = "👤 Обычный аккаунт · <b>один</b> объём (новый заменяет прежний)"
    return (
        "💾 <b>Память устройства</b>\n\n"
        f"✅ Сейчас · <b>{selected}</b>\n\n"
        f"{limit}\n\n"
        "💡 <i>Нет памяти в объявлении — подойдёт при любом выборе.</i>\n\n"
        "👇 Нажмите объём"
    )


def memory_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    selected = set((user or {}).get("memory_volumes") or DEFAULT_MEMORY_VOLUMES)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for vol in MEMORY_VOLUME_OPTIONS:
        label = format_memory_volume(vol, short=True)
        mark = " ✅" if vol in selected else ""
        row.append(
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"mem:t:{vol}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def price_screen_text(user: dict | None) -> str:
    cur = user.get("max_price") if user else None
    cur_txt = f"<b>{format_price(cur)}</b>" if cur is not None else "не задана"
    return (
        f"💰 <b>Лимит по цене</b> <i>({CURRENCY_SIGN})</i>\n\n"
        f"✅ Сейчас · {cur_txt}\n\n"
        f"Пришлём только объявления <b>не дороже</b> этой суммы в белорусских рублях.\n\n"
        "👇 Выберите готовую сумму"
        + ("\n🎯 Или свою цену — кнопка ниже (VIP)" if user and user.get("role") == "vip" else "")
    )


def goods_category_text() -> str:
    return (
        f"{GOODS_CRUMB}\n\n"
        "Отметьте модели — бот будет искать только их на Kufar.\n\n"
        "📱 Сейчас · <b>смартфоны</b> Apple и Samsung."
    )


def goods_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Смартфоны", callback_data="goods:m")],
            back_row(),
        ]
    )


def promo_prompt_text() -> str:
    return (
        "🎟 <b>Промокод</b>\n\n"
        "Отправьте код <b>одним сообщением</b>.\n"
        "VIP активируется сразу после проверки."
    )


def promo_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К VIP", callback_data="nav:vip")],
        ]
    )


def custom_price_prompt_text() -> str:
    return (
        "🎯 <b>Своя цена</b> <i>(VIP)</i>\n\n"
        f"Введите максимум в <b>белорусских рублях ({CURRENCY_SIGN})</b> — одним числом.\n"
        "Например: <code>1200</code>"
    )
