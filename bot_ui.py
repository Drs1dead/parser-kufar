"""Тексты и клавиатуры бота — отдельно от обработчиков."""
import time

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from avito_catalog import AVITO_QUICK_CITIES
from config import (
    AVITO_ENABLED,
    DEFAULT_MEMORY_VOLUMES,
    MEMORY_VOLUME_OPTIONS,
    REFERRAL_VIP_DAYS_PER_FRIEND,
    ROLLYPAY_ENABLED,
    VIP_PLANS,
    VIP_PRICE_USD,
    format_local_datetime,
    format_memory_volume,
    format_price_for_country,
    format_price_for_user,
)
from db import count_referrals, ensure_referral_code
from kufar_catalog import QUICK_RGN_BUTTONS, user_city_label
from marketplace.types import (
    COUNTRY_BY,
    COUNTRY_LABELS,
    COUNTRY_RU,
    FLAG_BY,
    FLAG_RU,
    normalize_country,
)
from product_catalog import (
    category_label,
    is_phones_category,
)

GOODS_CRUMB = "<b>Товары</b>"

BOT_USERNAME: str = ""

PRIVACY_POLICY_URL = "https://telegra.ph/POLITIKA-KONFIDENCIALNOSTI-08-12-99"
TERMS_OF_SERVICE_URL = "https://telegra.ph/PUBLICHNAYA-OFERTA-08-12-15"
SUPPORT_URL = "https://t.me/kufiBY"

HELP_TEXT_BY = (
    "<b>Помощь</b>\n\n"
    "Kufi ищет технику на <b>Kufar.by</b> и присылает совпадения. "
    "Цены — в <b>Br</b>.\n\n"
    "1. <b>Товары</b> — модель\n"
    "2. <b>Цена</b> и <b>Город</b>\n"
    "3. <b>Включить</b> уведомления на главной\n\n"
    "Новости и документы — кнопки ниже."
)

HELP_TEXT_RU = (
    "<b>Помощь</b>\n\n"
    "Kufi ищет технику на <b>Avito</b> и присылает совпадения. "
    "Цены — в <b>₽</b>.\n\n"
    "1. <b>Город</b>\n"
    "2. <b>Товары</b> — модель\n"
    "3. <b>Цена</b>\n"
    "4. <b>Включить</b> уведомления\n\n"
    "Новости и документы — кнопки ниже."
)


def help_text(user: dict | None = None) -> str:
    country = normalize_country((user or {}).get("country"))
    if country == COUNTRY_RU:
        return HELP_TEXT_RU
    return HELP_TEXT_BY


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
        return ["Сейчас: —"]
    now = int(time.time())
    vip_until = int(user.get("vip_until") or 0)
    if user.get("role") == "vip" and vip_until > now:
        until = format_local_datetime(vip_until, fmt="%d.%m.%Y в %H:%M")
        return [f"Сейчас: <b>VIP</b> до {until}"]
    return ["Сейчас: обычный аккаунт"]


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
            [InlineKeyboardButton(text="Новости", url=SUPPORT_URL)],
            [
                InlineKeyboardButton(text="Политика", url=PRIVACY_POLICY_URL),
                InlineKeyboardButton(text="Оферта", url=TERMS_OF_SERVICE_URL),
            ],
            back_row(),
        ]
    )


def user_source_label(user: dict | None) -> str:
    country = normalize_country((user or {}).get("country"))
    if country == COUNTRY_RU:
        return "Россия · Avito"
    return "Беларусь · Kufar"


def user_avito_city_label(user: dict | None) -> str:
    label = ((user or {}).get("avito_city_label") or "").strip()
    return label or "не выбран"


def home_text(user: dict | None, *, is_new: bool) -> str:
    if user is None:
        return "<b>Kufi</b>\nНажмите <code>/start</code>"

    active = user.get("active")
    models_n = _kw_count(user)
    max_p = user.get("max_price") or 0
    status = "уведомления вкл." if active else "на паузе"
    source_line = user_source_label(user)
    cat = category_label(user.get("product_category"))
    country = normalize_country(user.get("country"))
    if country == COUNTRY_RU:
        geo = user_avito_city_label(user)
    else:
        geo = user_city_label(user)

    lines = [
        "<b>Kufi</b>",
        f"{source_line} · {status}",
        "",
        f"<b>{cat}</b> · {models_n} {_plural_models(models_n)}",
        f"до {format_price_for_user(max_p, user)} · {geo}",
    ]
    if is_phones_category(user.get("product_category")):
        mem = user.get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
        mem_txt = ", ".join(format_memory_volume(v, short=True) for v in mem)
        lines[-1] += f" · {mem_txt}"

    mode = user.get("vip_feed_mode") or "normal"
    if user.get("role") == "vip":
        if mode == "below_market":
            lines.append("Поток: ниже рынка")
        elif mode == "exchange":
            lines.append("Поток: только обмен")
        elif mode == "ideal":
            lines.append("Поток: идеальные")

    hint = ""
    if country == COUNTRY_RU:
        if not AVITO_ENABLED:
            hint = "Рассылка Avito — скоро."
        elif not user.get("avito_city_id"):
            hint = "Выберите город."
        elif models_n == 0:
            hint = "Выберите модель в «Товары»."
        elif not active:
            hint = "Включите уведомления."
    else:
        if models_n == 0:
            hint = "Выберите модель в «Товары»."
        elif not active:
            hint = "Включите уведомления."
    if is_new and not hint:
        hint = "Настройте фильтры и включите уведомления."
    if hint:
        lines += ["", hint]

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
        rows.append([InlineKeyboardButton(text="Пауза", callback_data="nav:stop")])
    elif user:
        rows.append(
            [InlineKeyboardButton(text="Включить уведомления", callback_data="nav:resume")]
        )
    rows.append(
        [
            InlineKeyboardButton(text="VIP", callback_data="nav:vip"),
            InlineKeyboardButton(text="Помощь", callback_data="nav:help"),
        ]
    )
    goods_row = [
        InlineKeyboardButton(text="Товары", callback_data="nav:goods"),
        InlineKeyboardButton(text="Цена", callback_data="nav:price"),
    ]
    if is_phones_category((user or {}).get("product_category")):
        goods_row.append(
            InlineKeyboardButton(text="Память", callback_data="nav:memory")
        )
    rows.append(goods_row)
    rows.append(
        [
            InlineKeyboardButton(text="Страна", callback_data="nav:country"),
            InlineKeyboardButton(text="Город", callback_data="nav:city"),
        ]
    )
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text="Админ", callback_data="nav:admin")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_text(user: dict | None) -> str:
    lines = ["<b>VIP</b>", *_vip_status_lines(user)]

    if user and user.get("role") == "vip":
        mode = user.get("vip_feed_mode") or "normal"
        if mode == "below_market":
            flow = "ниже рынка"
        elif mode == "exchange":
            flow = "только обмен"
        elif mode == "ideal":
            flow = "идеальные"
        else:
            flow = "обычная рассылка"
        lines += ["", f"Поток: <b>{flow}</b>"]
        if ROLLYPAY_ENABLED:
            lines.append("Продление — кнопка ниже.")
    else:
        lines += [
            "",
            "• без лимита моделей",
            "• фото и описание в рассылке",
            "• потоки: ниже рынка, обмен, идеальные",
        ]
        if not ROLLYPAY_ENABLED:
            lines += ["", f"Цена: <b>{VIP_PRICE_USD}$</b> / 30 дн. · @manohio"]

    if user and user.get("chat_id") is not None:
        cid = int(user["chat_id"])
        ref_n = count_referrals(cid)
        link = referral_link_for_user(user)
        days = REFERRAL_VIP_DAYS_PER_FRIEND
        lines += ["", f"За друга: +{days} дн. · приглашено: <b>{ref_n}</b>"]
        if link:
            lines.append(f"<code>{link}</code>")

    return "\n".join(lines)


def vip_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    is_vip = bool(user and user.get("role") == "vip")
    if is_vip:
        mode = user.get("vip_feed_mode") or "normal"
        bm = "Ниже рынка ✓" if mode == "below_market" else "Ниже рынка"
        ex = "Обмен ✓" if mode == "exchange" else "Обмен"
        idl = "Идеальные ✓" if mode == "ideal" else "Идеальные"
        rows.append(
            [
                InlineKeyboardButton(text=bm, callback_data="nav:vipf:bm"),
                InlineKeyboardButton(text=ex, callback_data="nav:vipf:ex"),
            ]
        )
        rows.append(
            [InlineKeyboardButton(text=idl, callback_data="nav:vipf:ideal")]
        )
    if ROLLYPAY_ENABLED:
        buy_label = "Продлить VIP" if is_vip else "Купить VIP"
        rows.append(
            [InlineKeyboardButton(text=buy_label, callback_data="nav:vip:plans")]
        )
    rows.append([InlineKeyboardButton(text="Промокод", callback_data="nav:promo")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vip_plans_text(user: dict | None = None) -> str:
    week = VIP_PLANS["week"]
    month = VIP_PLANS["month"]
    quarter = VIP_PLANS["quarter"]
    is_vip = bool(user and user.get("role") == "vip")
    action = "Продление" if is_vip else "Покупка"
    return (
        f"<b>Тариф VIP</b>\n"
        f"{action} — выберите срок. Оплата онлайн, VIP включится сам.\n\n"
        f"• {int(week['days'])} дней — <b>${int(week['usd'])}</b>\n"
        f"• {int(month['days'])} дней — <b>${int(month['usd'])}</b>\n"
        f"• {int(quarter['days'])} дней — <b>${int(quarter['usd'])}</b>"
    )


def vip_plans_keyboard() -> InlineKeyboardMarkup:
    week = VIP_PLANS["week"]
    month = VIP_PLANS["month"]
    quarter = VIP_PLANS["quarter"]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{int(week['days'])} дней — ${int(week['usd'])}",
                    callback_data="vip:buy:week",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{int(month['days'])} дней — ${int(month['usd'])}",
                    callback_data="vip:buy:month",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{int(quarter['days'])} дней — ${int(quarter['usd'])}",
                    callback_data="vip:buy:quarter",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:vip")],
        ]
    )


def vip_pay_text(row: dict) -> str:
    days = int(row.get("days") or 0)
    rub = str(row.get("amount_rub") or "")
    usd = row.get("amount_usd")
    usd_part = f" (~${usd:g})" if usd is not None else ""
    return (
        "<b>Оплата VIP</b>\n"
        f"Срок: <b>{days}</b> дн.\n"
        f"Сумма: <b>{rub} ₽</b>{usd_part}\n\n"
        "Нажмите «Оплатить», завершите платёж.\n"
        "После 100% оплаты VIP включится автоматически."
    )


def vip_pay_keyboard(row: dict) -> InlineKeyboardMarkup:
    order_id = str(row.get("order_id") or "")
    pay_url = str(row.get("pay_url") or "")
    rows: list[list[InlineKeyboardButton]] = []
    if pay_url:
        rows.append([InlineKeyboardButton(text="Оплатить", url=pay_url)])
    if order_id:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Проверить оплату",
                    callback_data=f"vip:check:{order_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="К тарифам", callback_data="nav:vip:plans")]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:vip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def memory_screen_text(user: dict | None) -> str:
    vols = (user or {}).get("memory_volumes") or list(DEFAULT_MEMORY_VOLUMES)
    selected = _memory_display(vols)
    hint = (
        "Можно выбрать несколько объёмов."
        if user and user.get("role") == "vip"
        else "Один объём памяти."
    )
    return (
        "<b>Память</b>\n"
        f"Сейчас: <b>{selected}</b>\n"
        f"{hint}"
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
    flag = FLAG_RU if country == COUNTRY_RU else FLAG_BY
    current = COUNTRY_LABELS.get(country, country)
    ru_note = "Avito" if AVITO_ENABLED else "скоро"
    return (
        "<b>Страна</b>\n"
        f"Сейчас: {flag} <b>{current}</b>\n"
        f"{FLAG_BY} Беларусь — Kufar · {FLAG_RU} Россия — {ru_note}\n"
        "Лимит цены подстроится под валюту."
    )


def country_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    country = normalize_country((user or {}).get("country"))
    by_mark = " ✅" if country == COUNTRY_BY else ""
    ru_mark = " ✅" if country == COUNTRY_RU else ""
    ru_suffix = " · Avito" if AVITO_ENABLED else " · скоро"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{FLAG_BY} Беларусь · Kufar{by_mark}",
                    callback_data="country:by",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{FLAG_RU} Россия{ru_suffix}{ru_mark}",
                    callback_data="country:ru",
                )
            ],
            back_row(),
        ]
    )


def avito_city_screen_text(user: dict | None) -> str:
    current = user_avito_city_label(user)
    hint = (
        "Дальше — товары, цена и уведомления."
        if AVITO_ENABLED
        else "Рассылка Avito скоро; город можно выбрать заранее."
    )
    return (
        "<b>Город</b>\n"
        f"Сейчас: <b>{current}</b>\n"
        f"{hint}"
    )


def avito_city_typed_prompt_text() -> str:
    return (
        "<b>Город</b>\n"
        "Введите название, например <code>Москва</code>."
    )


def avito_city_pick_keyboard(options: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, opt in enumerate(options):
        label = str(opt.get("label") or "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"avito:pick:{idx}",
                )
            ]
        )
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def avito_city_keyboard(user: dict | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    current_city = str((user or {}).get("avito_city_id") or "").strip()
    for idx, (label, region_id, city_id) in enumerate(AVITO_QUICK_CITIES):
        mark = " ✅" if current_city and current_city == city_id else ""
        row.append(
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"avito:quick:{idx}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(
                text="Ввести город",
                callback_data="avito:city:typed",
            )
        ]
    )
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def city_screen_text(user: dict | None) -> str:
    current = user_city_label(user)
    return (
        "<b>Город</b>\n"
        f"Сейчас: <b>{current}</b>\n"
        "Область ниже или ввод названия."
    )


def city_typed_prompt_text() -> str:
    return (
        "<b>Город</b>\n"
        "Введите название, например <code>Барановичи</code>."
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
    rows.append(
        [
            InlineKeyboardButton(
                text="Ввести город",
                callback_data="nav:city:typed",
            )
        ]
    )
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def price_screen_text(user: dict | None) -> str:
    cur = user.get("max_price") if user else None
    cur_txt = (
        f"<b>{format_price_for_user(cur, user)}</b>"
        if cur is not None
        else "не задана"
    )
    country = normalize_country((user or {}).get("country"))
    hint = "Объявления не дороже этой суммы."
    if country == COUNTRY_RU:
        hint = "Лимит в ₽. Обычно 10–50 тыс. для б/у."
    if user and user.get("role") == "vip":
        hint += " Своя сумма — кнопка ниже."
    return (
        "<b>Цена</b>\n"
        f"Сейчас: {cur_txt}\n"
        f"{hint}"
    )


def promo_prompt_text() -> str:
    return "<b>Промокод</b>\nОтправьте код одним сообщением."


def promo_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:vip")],
        ]
    )


def custom_price_prompt_text(user: dict | None = None) -> str:
    country = normalize_country((user or {}).get("country"))
    sign = "₽" if country == COUNTRY_RU else "Br"
    example = "25000" if country == COUNTRY_RU else "1200"
    return (
        "<b>Своя цена</b>\n"
        f"Максимум в {sign}, одним числом.\n"
        f"Например: <code>{example}</code>"
    )
