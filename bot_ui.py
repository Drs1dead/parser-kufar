"""Тексты и клавиатуры бота — отдельно от обработчиков."""
import time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    CURRENCY_SIGN,
    DEFAULT_MEMORY_VOLUMES,
    MEMORY_VOLUME_OPTIONS,
    REFERRAL_VIP_DAYS_PER_FRIEND,
    VIP_PRICE_USD,
    format_local_datetime,
    format_memory_volume,
    format_price,
)
from db import count_referrals, ensure_referral_code
from kufar_catalog import QUICK_RGN_BUTTONS, user_city_label
from marketplace.types import COUNTRY_BY, COUNTRY_LABELS, normalize_country
from product_catalog import (
    category_label,
    is_phones_category,
)

GOODS_CRUMB = "<b>Товары</b>"

BOT_USERNAME: str = ""

PRIVACY_POLICY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
TERMS_OF_SERVICE_URL = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"
SUPPORT_URL = "https://t.me/kufiBY"

HELP_TEXT = (
    "<b>Помощь</b>\n\n"
    "Kufi ищет технику на <b>Kufar.by</b> и присылает совпадения. "
    f"Цены — в <b>{CURRENCY_SIGN}</b>.\n\n"
    "Настройте <b>Товары</b>, лимит и город, затем включите уведомления.\n\n"
    "Новости и документы — кнопки ниже."
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
        return ["Аккаунт: —"]
    now = int(time.time())
    vip_until = int(user.get("vip_until") or 0)
    if user.get("role") == "vip" and vip_until > now:
        until = format_local_datetime(vip_until, fmt="%d.%m.%Y в %H:%M")
        return [
            "Аккаунт: <b>VIP</b>",
            f"До: <b>{until}</b>",
        ]
    return [
        "Аккаунт: обычный",
        "VIP не подключён",
    ]


def referral_link_for_user(user: dict | None) -> str:
    if not user or not BOT_USERNAME:
        return ""
    chat_id = user.get("chat_id")
    if chat_id is None:
        return ""
    code = ensure_referral_code(int(chat_id), user=user)
    if not code:
        return ""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{code}"


def back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:home")]


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[back_row()])


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📰 Новости", url=SUPPORT_URL)],
            [
                InlineKeyboardButton(text="🔒 Политика", url=PRIVACY_POLICY_URL),
                InlineKeyboardButton(text="📄 Оферта", url=TERMS_OF_SERVICE_URL),
            ],
            back_row(),
        ]
    )


def home_text(user: dict | None, *, is_new: bool) -> str:
    if user is None:
        return (
            "<b>Kufi</b>\n"
            "Kufar · нажмите <code>/start</code>"
        )

    active = user.get("active")
    models_n = _kw_count(user)
    max_p = user.get("max_price") or 0
    status = "уведомления включены" if active else "на паузе"
    cat = category_label(user.get("product_category"))
    lines = [
        "<b>Kufi</b>",
        f"Kufar · {status}",
        "",
        f"{cat} · {models_n} {_plural_models(models_n)}",
    ]
    geo = user_city_label(user)
    detail = f"до {format_price(max_p)} · {geo}"
    if is_phones_category(user.get("product_category")):
        mem = (user.get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES))
        mem_txt = ", ".join(format_memory_volume(v, short=True) for v in mem)
        detail += f" · {mem_txt}"
    lines.append(detail)

    if is_new:
        hint = "Товары и фильтры — кнопки ниже, затем включите уведомления."
        lines += ["", hint]

    mode = user.get("vip_feed_mode") or "normal"
    if user.get("role") == "vip":
        if mode == "below_market":
            lines.append("Поток: ниже рынка")
        elif mode == "exchange":
            lines.append("Поток: только обмен")
        elif mode == "ideal":
            lines.append("Поток: идеальные")

    if models_n == 0:
        lines.append("Выберите модели в «Товары».")
    elif not active:
        lines.append("Уведомления выключены.")

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
        rows.append([InlineKeyboardButton(text="🔕 Пауза", callback_data="nav:stop")])
    elif user:
        rows.append(
            [InlineKeyboardButton(text="🔔 Включить", callback_data="nav:resume")]
        )
    rows.append(
        [
            InlineKeyboardButton(text="⭐ VIP", callback_data="nav:vip"),
            InlineKeyboardButton(text="💡 Помощь", callback_data="nav:help"),
        ]
    )
    goods_row = [
        InlineKeyboardButton(text="📱 Товары", callback_data="nav:goods"),
        InlineKeyboardButton(text="💰 Цена", callback_data="nav:price"),
    ]
    if is_phones_category((user or {}).get("product_category")):
        goods_row.append(
            InlineKeyboardButton(text="💾 Память", callback_data="nav:memory")
        )
    rows.append(goods_row)
    rows.append(
        [
            InlineKeyboardButton(text="🌍 Страна", callback_data="nav:country"),
            InlineKeyboardButton(text="📍 Город", callback_data="nav:city"),
        ]
    )
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text="🔐 Админ-панель", callback_data="nav:admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_text(user: dict | None) -> str:
    lines = ["⭐ <b>VIP</b>", "", *_vip_status_lines(user)]

    if user and user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        if mode == "below_market":
            lines += ["", "Поток: <b>ниже рынка</b>"]
        elif mode == "exchange":
            lines += ["", "Поток: <b>только обмен</b>"]
        elif mode == "ideal":
            lines += ["", "Поток: <b>идеальные</b>"]
        else:
            lines += ["", "Поток: <b>обычная рассылка</b>"]
    else:
        lines += [
            "",
            "Что даёт VIP:",
            "• без лимита моделей",
            "• сразу, без мусора",
            "• ниже рынка, обмен, идеальные",
            "",
            f"Цена: <b>{VIP_PRICE_USD}$</b> / 30 дней · @manohio",
            "Промокод — кнопка ниже.",
        ]

    if user and user.get("chat_id") is not None:
        cid = int(user["chat_id"])
        ref_n = count_referrals(cid)
        link = referral_link_for_user(user)
        days = REFERRAL_VIP_DAYS_PER_FRIEND
        lines += ["", f"За друга: +{days} дн. VIP · приглашено: <b>{ref_n}</b>"]
        if link:
            lines.append(f"<code>{link}</code>")

    return "\n".join(lines)


def vip_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if user and user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        bm = "🔥 Ниже рынка ✅" if mode == "below_market" else "🔥 Ниже рынка"
        ex = "🔄 Обмен ✅" if mode == "exchange" else "🔄 Обмен"
        idl = "✨ Идеальные ✅" if mode == "ideal" else "✨ Идеальные"
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
    limit = (
        "VIP: можно несколько объёмов."
        if user and user.get("role") == "vip"
        else "Обычный аккаунт: один объём."
    )
    return (
        "<b>Память</b>\n"
        f"Сейчас: <b>{selected}</b>\n"
        f"{limit}"
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


def country_screen_text(user: dict | None) -> str:
    country = normalize_country((user or {}).get("country"))
    current = COUNTRY_LABELS.get(country, country)
    return (
        "<b>Страна</b>\n"
        f"Сейчас: <b>{current}</b>\n"
        "Беларусь — Kufar. Россия — скоро (Avito)."
    )


def country_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    country = normalize_country((user or {}).get("country"))
    by_mark = " ✅" if country == COUNTRY_BY else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Беларусь{by_mark}",
                    callback_data="country:by",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Россия · скоро",
                    callback_data="country:ru",
                )
            ],
            back_row(),
        ]
    )


def city_screen_text(user: dict | None) -> str:
    current = user_city_label(user)
    return (
        "<b>Город</b>\n"
        f"Сейчас: <b>{current}</b>\n"
        "Введите название или выберите область."
    )


def city_typed_prompt_text() -> str:
    return (
        "📍 <b>Город</b>\n\n"
        "Введите название города или населённого пункта, например "
        "<code>Барановичи</code> или <code>Бобруйск</code>."
    )


def city_pick_keyboard(options: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, opt in enumerate(options):
        label = str(opt.get("label") or "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"city:pick:{idx}",
                )
            ]
        )
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _region_selected(user: dict | None, rgn: int) -> bool:
    if not user:
        return False
    return int(user.get("city_rgn") or 0) == rgn and user.get("city_ar") is None


def city_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append(
        [
            InlineKeyboardButton(
                text="⌨️ Ввести город",
                callback_data="nav:city:typed",
            )
        ]
    )
    row: list[InlineKeyboardButton] = []
    for rgn, label in QUICK_RGN_BUTTONS:
        mark = " ✅" if _region_selected(user, rgn) else ""
        row.append(
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"city:rgn:{rgn}",
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
    extra = ""
    if user and user.get("role") == "vip":
        extra = "\n\nСвоя сумма — кнопка ниже."
    return (
        "<b>Цена</b>\n"
        f"Сейчас: {cur_txt}\n"
        "Не дороже этой суммы."
        f"{extra}"
    )


def promo_prompt_text() -> str:
    return "🎟 <b>Промокод</b>\n\nОтправьте код одним сообщением."


def promo_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:vip")],
        ]
    )


def custom_price_prompt_text() -> str:
    return (
        "🎯 <b>Своя цена</b> (VIP)\n\n"
        f"Введите максимум в {CURRENCY_SIGN} — одним числом.\n"
        "Например: <code>1200</code>"
    )
