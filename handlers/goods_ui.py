"""Клавиатуры и тексты раздела «Товары» (без Telegram-роутера)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_ui import GOODS_CRUMB
from goods_tree import (
    APPLE_LINES,
    GOODS_PER_PAGE,
    LINE_BASIC,
    LINE_LABELS,
    LINE_MAX,
    LINE_PRO,
    SAMSUNG_LINE_LABELS,
    SAMSUNG_LINES,
    SAMSUNG_SERIES_FLIP,
    SAMSUNG_SERIES_FOLD,
    SAMSUNG_SERIES_LABELS,
    SAMSUNG_SERIES_LINES,
    SAMSUNG_SERIES_S,
)
from handlers.helpers import is_vip_user

__all__ = [
    "_max_keyword_slots",
    "_apple_models",
    "_samsung_models",
    "_toggle_models",
    "_goods_mobile_brands_text",
    "_goods_mobile_brands_keyboard",
]


def _max_keyword_slots(user: dict) -> int:
    return 9999 if is_vip_user(user) else 5


def _flatten_groups(groups: dict[str, tuple[str, ...]]) -> list[str]:
    items: list[str] = []
    for values in groups.values():
        items.extend(values)
    return items


def _apple_models() -> list[str]:
    return _flatten_groups(APPLE_LINES)


def _samsung_models() -> list[str]:
    return _flatten_groups(SAMSUNG_LINES)


def _samsung_series_models(series_slug: str) -> list[str]:
    items: list[str] = []
    for line_slug in SAMSUNG_SERIES_LINES.get(series_slug, ()):
        items.extend(SAMSUNG_LINES.get(line_slug, ()))
    return items


def _samsung_series_for_line(line_slug: str) -> str:
    for series_slug, line_slugs in SAMSUNG_SERIES_LINES.items():
        if line_slug in line_slugs:
            return series_slug
    return SAMSUNG_SERIES_S


def _samsung_line_back_button(line_slug: str) -> InlineKeyboardButton:
    series_slug = _samsung_series_for_line(line_slug)
    if series_slug in (SAMSUNG_SERIES_FLIP, SAMSUNG_SERIES_FOLD):
        return InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:s")
    return InlineKeyboardButton(text="⬅️ Назад", callback_data=f"sg:{series_slug}")


def _select_models(user: dict, models: list[str] | tuple[str, ...]) -> list[str]:
    selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
    seen = set(selected)
    for model in models:
        value = model.strip().lower()
        if value and value not in seen:
            selected.append(value)
            seen.add(value)
    return selected


def _toggle_models(user: dict, models: list[str] | tuple[str, ...]) -> tuple[list[str], bool]:
    selected = [k.strip().lower() for k in (user.get("keywords") or []) if k.strip()]
    selected_set = set(selected)
    model_values = [m.strip().lower() for m in models if m.strip()]
    model_set = set(model_values)
    if model_set and model_set.issubset(selected_set):
        return [k for k in selected if k not in model_set], False
    return _select_models(user, model_values), True


def _goods_mobile_brands_text() -> str:
    return (
        f"{GOODS_CRUMB}\n\n"
        "Выберите бренд, затем линейку и модели."
    )


def _goods_mobile_brands_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🍎 Apple", callback_data="goods:a"),
            InlineKeyboardButton(text="📱 Samsung", callback_data="goods:s"),
        ],
    ]
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Все бренды", callback_data="bulk:all")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_samsung_text() -> str:
    return (
        f"{GOODS_CRUMB} › <b>Samsung</b>\n\n"
        "Выберите серию, затем отметьте модели."
    )


def _goods_apple_lines_text() -> str:
    return (
        f"{GOODS_CRUMB} › <b>Apple</b>\n\n"
        "Выберите линейку, затем отметьте модели."
    )


def _goods_apple_lines_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=f"🍎 {LINE_LABELS[LINE_BASIC]}", callback_data=f"gt:{LINE_BASIC}:p:0"),
            InlineKeyboardButton(text=f"🍎 {LINE_LABELS[LINE_PRO]}", callback_data=f"gt:{LINE_PRO}:p:0"),
        ],
        [
            InlineKeyboardButton(text=f"🍎 {LINE_LABELS[LINE_MAX]}", callback_data=f"gt:{LINE_MAX}:p:0"),
        ],
    ]
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Все iPhone", callback_data="bulk:apple")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:m")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_samsung_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Samsung Galaxy S", callback_data=f"sg:{SAMSUNG_SERIES_S}")],
        [
            InlineKeyboardButton(text="Samsung Z Flip", callback_data=f"st:{SAMSUNG_SERIES_FLIP}:p:0"),
            InlineKeyboardButton(text="Samsung Z Fold", callback_data=f"st:{SAMSUNG_SERIES_FOLD}:p:0"),
        ],
    ]
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Весь Samsung", callback_data="bulk:samsung")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:m")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _samsung_series_text(series_slug: str) -> str:
    title = SAMSUNG_SERIES_LABELS.get(series_slug, "Samsung")
    return (
        f"{GOODS_CRUMB} › <b>Samsung</b> › <b>{title}</b>\n\n"
        "Выберите линейку."
    )


def _samsung_series_keyboard(series_slug: str, user: dict | None = None) -> InlineKeyboardMarkup | None:
    line_slugs = SAMSUNG_SERIES_LINES.get(series_slug)
    if not line_slugs:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for line_slug in line_slugs:
        label = SAMSUNG_LINE_LABELS.get(line_slug, line_slug)
        if not SAMSUNG_LINES.get(line_slug):
            continue
        row.append(InlineKeyboardButton(text=label, callback_data=f"st:{line_slug}:p:0"))
        if len(row) >= 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Выбрать всю серию", callback_data=f"bulk:ss:{series_slug}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:s")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _line_pick_text(line_slug: str, *, brand: str, user: dict | None = None) -> str:
    if brand == "apple":
        title = LINE_LABELS.get(line_slug, line_slug)
        brand_title = "Apple"
    else:
        title = SAMSUNG_LINE_LABELS.get(line_slug, line_slug)
        brand_title = "Samsung"
    lines = [
        f"{GOODS_CRUMB} › <b>{brand_title}</b> › <b>{title}</b>",
        "",
        "Нажмите модель, чтобы включить или выключить.",
    ]
    if not is_vip_user(user):
        limit = _max_keyword_slots({"role": "regular"})
        lines.append(f"Обычный аккаунт: до {limit} моделей.")
    lines.append("Готово — в главное меню.")
    return "\n".join(lines)


def _samsung_line_pick_text(line_slug: str, user: dict | None = None) -> str:
    return _line_pick_text(line_slug, brand="samsung", user=user)


def _goods_line_pick_text(line_slug: str, user: dict | None = None) -> str:
    return _line_pick_text(line_slug, brand="apple", user=user)


def _paginated_models_keyboard(
    user: dict,
    models: tuple[str, ...],
    scope_id: str,
    page: int,
    *,
    toggle_prefix: str,
    bulk_callback: str | None,
    footer_buttons: list[InlineKeyboardButton],
) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(models) + GOODS_PER_PAGE - 1) // GOODS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * GOODS_PER_PAGE
    chunk = models[start : start + GOODS_PER_PAGE]
    selected = {k.strip().lower() for k in (user.get("keywords") or []) if k.strip()}

    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row: list[InlineKeyboardButton] = []
        for j in range(2):
            if i + j >= len(chunk):
                continue
            global_idx = start + i + j
            item = chunk[i + j]
            mark = "✅ " if item.lower() in selected else ""
            row.append(
                InlineKeyboardButton(
                    text=f"{mark}{item}",
                    callback_data=f"{toggle_prefix}:{scope_id}:t:{global_idx}",
                )
            )
        if row:
            rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{toggle_prefix}:{scope_id}:p:{page - 1}",
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data=f"{toggle_prefix}:{scope_id}:x:0",
        )
    )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{toggle_prefix}:{scope_id}:p:{page + 1}",
            )
        )
    rows.append(nav)
    if bulk_callback:
        rows.append(
            [InlineKeyboardButton(text="📋 Выбрать всю линейку", callback_data=bulk_callback)]
        )
    rows.append(footer_buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _samsung_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = SAMSUNG_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:sg:{line_slug}" if is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="st",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово", callback_data="kw:done"),
            _samsung_line_back_button(line_slug),
        ],
    )


def _goods_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = APPLE_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:ap:{line_slug}" if is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="gt",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:a"),
        ],
    )

