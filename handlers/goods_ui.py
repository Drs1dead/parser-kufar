"""Клавиатуры и тексты раздела «Товары» (без Telegram-роутера)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_ui import GOODS_CRUMB
from config import REGULAR_MAX_KEYWORDS
from goods_tree import (
    APPLE_LINES,
    GOODS_PER_PAGE,
    LAPTOP_LINE_LABELS,
    LAPTOP_LINES,
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
    TABLET_LINE_LABELS,
    TABLET_LINES,
    WATCH_LINE_LABELS,
    WATCH_LINES,
)
from handlers.helpers import is_vip_user
from product_catalog import (
    CATEGORY_EMOJI,
    CATEGORY_LABELS,
    PRODUCT_CATEGORIES,
    category_label,
    model_label,
    normalize_category,
)

__all__ = [
    "_max_keyword_slots",
    "_apple_models",
    "_samsung_models",
    "_toggle_models",
    "_goods_mobile_brands_text",
    "_goods_mobile_brands_keyboard",
]


def _max_keyword_slots(user: dict) -> int:
    return 9999 if is_vip_user(user) else REGULAR_MAX_KEYWORDS


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
    return f"{GOODS_CRUMB} › <b>Смартфоны</b>"


def _goods_mobile_brands_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🍎 Apple", callback_data="goods:a"),
            InlineKeyboardButton(text="📱 Samsung", callback_data="goods:s"),
        ],
    ]
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="Все бренды", callback_data="bulk:all")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:goods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_samsung_text() -> str:
    return f"{GOODS_CRUMB} › <b>Samsung</b>"


def _goods_apple_lines_text() -> str:
    return f"{GOODS_CRUMB} › <b>Apple</b>"


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
        rows.append([InlineKeyboardButton(text="Все iPhone", callback_data="bulk:apple")])
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
        rows.append([InlineKeyboardButton(text="Весь Samsung", callback_data="bulk:samsung")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:m")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _samsung_series_text(series_slug: str) -> str:
    title = SAMSUNG_SERIES_LABELS.get(series_slug, "Samsung")
    return f"{GOODS_CRUMB} › <b>Samsung</b> › <b>{title}</b>"


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
        rows.append([InlineKeyboardButton(text="Вся серия", callback_data=f"bulk:ss:{series_slug}")])
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
    ]
    if not is_vip_user(user):
        limit = _max_keyword_slots({"role": "regular"})
        lines += ["", "Обычный аккаунт: 1 модель." if limit == 1 else f"До {limit} моделей."]
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
                    text=f"{mark}{model_label(item)}",
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
            [InlineKeyboardButton(text="Вся линейка", callback_data=bulk_callback)]
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


def _goods_categories_text(user: dict | None = None) -> str:
    current = category_label((user or {}).get("product_category"))
    return (
        f"{GOODS_CRUMB}\n\n"
        f"Сейчас: <b>{current}</b>\n\n"
        "Одна категория. Смена сбросит модели."
    )


def _goods_categories_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    current = normalize_category((user or {}).get("product_category"))
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for slug in PRODUCT_CATEGORIES:
        mark = " ✅" if slug == current else ""
        row.append(
            InlineKeyboardButton(
                text=f"{CATEGORY_EMOJI[slug]} {CATEGORY_LABELS[slug]}{mark}",
                callback_data=f"gc:{slug}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_switch_confirm_text(slug: str) -> str:
    return (
        f"{GOODS_CRUMB}\n\n"
        f"Сменить на <b>{category_label(slug)}</b>?\n"
        "Выбранные модели сбросятся."
    )


def _goods_switch_confirm_keyboard(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, сменить", callback_data=f"gx:{slug}"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:goods")],
        ]
    )


def _category_lines_text(slug: str) -> str:
    return f"{GOODS_CRUMB} › <b>{category_label(slug)}</b>"


def _laptop_lines_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=LAPTOP_LINE_LABELS[slug],
                callback_data=f"lt:{slug}:p:0",
            )
            for slug in LAPTOP_LINE_LABELS
        ]
    ]
    if is_vip_user(user):
        rows.append(
            [InlineKeyboardButton(text="Все MacBook", callback_data="bulk:lap")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:goods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _tablet_lines_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for slug, label in TABLET_LINE_LABELS.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"pt:{slug}:p:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if is_vip_user(user):
        rows.append([InlineKeyboardButton(text="Все iPad", callback_data="bulk:tab")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:goods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _watch_lines_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=label, callback_data=f"wt:{slug}:p:0")
            for slug, label in WATCH_LINE_LABELS.items()
        ]
    ]
    if is_vip_user(user):
        rows.append(
            [InlineKeyboardButton(text="Все Apple Watch", callback_data="bulk:wat")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:goods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _flatten_line_map(lines: dict[str, tuple[str, ...]]) -> list[str]:
    return _flatten_groups(lines)


def _category_line_pick_text(brand: str, line_slug: str, user: dict | None = None) -> str:
    labels = {
        "laptop": (LAPTOP_LINE_LABELS, "Ноутбуки"),
        "tablet": (TABLET_LINE_LABELS, "Планшеты"),
        "watch": (WATCH_LINE_LABELS, "Смарт-часы"),
    }
    line_labels, brand_title = labels[brand]
    title = line_labels.get(line_slug, line_slug)
    lines = [
        f"{GOODS_CRUMB} › <b>{brand_title}</b> › <b>{title}</b>",
    ]
    if not is_vip_user(user):
        limit = _max_keyword_slots({"role": "regular"})
        lines += ["", "Обычный аккаунт: 1 модель." if limit == 1 else f"До {limit} моделей."]
    return "\n".join(lines)


def _laptop_line_pick_text(line_slug: str, user: dict | None = None) -> str:
    return _category_line_pick_text("laptop", line_slug, user)


def _tablet_line_pick_text(line_slug: str, user: dict | None = None) -> str:
    return _category_line_pick_text("tablet", line_slug, user)


def _watch_line_pick_text(line_slug: str, user: dict | None = None) -> str:
    return _category_line_pick_text("watch", line_slug, user)


def _laptop_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = LAPTOP_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:ll:{line_slug}" if is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="lt",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="gc:laptops"),
        ],
    )


def _tablet_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = TABLET_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:tl:{line_slug}" if is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="pt",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="gc:tablets"),
        ],
    )


def _watch_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = WATCH_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:wl:{line_slug}" if is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="wt",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="gc:watches"),
        ],
    )

