"""Клавиатуры и тексты раздела «Товары» (без Telegram-роутера)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import DEVICE_CATALOG
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
from handlers.helpers import PER_PAGE

__all__ = [
    "_max_keyword_slots",
    "_is_vip_user",
    "_flatten_groups",
    "_apple_models",
    "_samsung_models",
    "_models_for_scope",
    "_model_list_title",
    "_model_list_bulk_callback",
    "_model_list_back_button",
    "_samsung_series_models",
    "_samsung_series_for_line",
    "_samsung_line_back_button",
    "_select_models",
    "_toggle_models",
    "_goods_mobile_brands_text",
    "_goods_mobile_brands_keyboard",
    "_goods_samsung_text",
    "_goods_apple_lines_text",
    "_goods_apple_lines_keyboard",
    "_goods_samsung_keyboard",
    "_samsung_series_text",
    "_samsung_series_keyboard",
    "_samsung_line_pick_text",
    "_paginated_models_keyboard",
    "_samsung_line_keyboard",
    "_goods_line_pick_text",
    "_goods_line_keyboard",
    "_build_keywords_text",
    "_build_model_list_text",
    "_model_list_keyboard",
    "_keywords_keyboard",
]


def _max_keyword_slots(user: dict) -> int:
    return 9999 if user.get("role") == "vip" else 5


def _is_vip_user(user: dict | None) -> bool:
    return bool(user and user.get("role") == "vip")


def _flatten_groups(groups: dict[str, tuple[str, ...]]) -> list[str]:
    items: list[str] = []
    for values in groups.values():
        items.extend(values)
    return items


def _apple_models() -> list[str]:
    return _flatten_groups(APPLE_LINES)


def _samsung_models() -> list[str]:
    return _flatten_groups(SAMSUNG_LINES)


def _models_for_scope(scope: str) -> list[str]:
    if scope == "a":
        return _apple_models()
    if scope == "s":
        return _samsung_models()
    return list(DEVICE_CATALOG)


def _model_list_title(scope: str) -> str:
    if scope == "a":
        return "Apple › <b>Все модели</b>"
    if scope == "s":
        return "Samsung › <b>Все модели</b>"
    return "<b>Все модели</b>"


def _model_list_bulk_callback(scope: str) -> str:
    if scope == "a":
        return "bulk:apple"
    if scope == "s":
        return "bulk:samsung"
    return "bulk:all"


def _model_list_back_button(scope: str) -> InlineKeyboardButton:
    if scope == "a":
        return InlineKeyboardButton(text="⬅️ К линейкам", callback_data="goods:a")
    if scope == "s":
        return InlineKeyboardButton(text="⬅️ К сериям", callback_data="goods:s")
    return InlineKeyboardButton(text="⬅️ К брендам", callback_data="goods:m")


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
        return InlineKeyboardButton(text="⬅️ К сериям", callback_data="goods:s")
    return InlineKeyboardButton(text="⬅️ К линейкам", callback_data=f"sg:{series_slug}")


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
        f"{GOODS_CRUMB} › <b>Смартфоны</b>\n\n"
        "🏷️ Выберите <b>бренд</b> — дальше линейки и модели."
    )


def _goods_mobile_brands_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🍎 Apple", callback_data="goods:a"),
            InlineKeyboardButton(text="📱 Samsung", callback_data="goods:s"),
        ],
    ]
    if _is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Все бренды", callback_data="bulk:all")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:h")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_samsung_text() -> str:
    return (
        f"{GOODS_CRUMB} › <b>Samsung</b>\n\n"
        "📱 Серия → линейка → отметьте нужные модели."
    )


def _goods_apple_lines_text() -> str:
    return (
        f"{GOODS_CRUMB} › <b>Apple</b>\n\n"
        "🍎 Линейка iPhone → отметьте модели галочкой."
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
    if _is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Все iPhone", callback_data="bulk:apple")])
    rows.extend(
        [
            [InlineKeyboardButton(text="📃 Список всех моделей", callback_data="goods:w")],
            [InlineKeyboardButton(text="⬅️ К брендам", callback_data="goods:m")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _goods_samsung_keyboard(user: dict | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Samsung Galaxy S", callback_data=f"sg:{SAMSUNG_SERIES_S}")],
        [
            InlineKeyboardButton(text="Samsung Z Flip", callback_data=f"st:{SAMSUNG_SERIES_FLIP}:p:0"),
            InlineKeyboardButton(text="Samsung Z Fold", callback_data=f"st:{SAMSUNG_SERIES_FOLD}:p:0"),
        ],
    ]
    if _is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Весь Samsung", callback_data="bulk:samsung")])
    rows.extend(
        [
            [InlineKeyboardButton(text="📃 Список всех моделей", callback_data="goods:sw")],
            [InlineKeyboardButton(text="⬅️ К брендам", callback_data="goods:m")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _samsung_series_text(series_slug: str) -> str:
    title = SAMSUNG_SERIES_LABELS.get(series_slug, "Samsung")
    return (
        f"{GOODS_CRUMB} › <b>Samsung</b> › <b>{title}</b>\n\n"
        "👇 Выберите <b>линейку</b>"
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
    if _is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Выбрать всю серию", callback_data=f"bulk:ss:{series_slug}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="goods:s")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _samsung_line_pick_text(line_slug: str) -> str:
    title = SAMSUNG_LINE_LABELS.get(line_slug, line_slug)
    return (
        f"{GOODS_CRUMB} › <b>Мобильные</b> › <b>Samsung</b> › <b>{title}</b>\n\n"
        "Нажмите на модель — <b>вкл/выкл</b>.\n"
        f"Лимит ручного выбора для обычного пользователя: до {_max_keyword_slots({'role': 'regular'})} позиций.\n"
        "Ниже — <b>Готово</b>, возврат к линейкам или в меню."
    )


def _paginated_models_keyboard(
    user: dict,
    models: tuple[str, ...],
    line_slug: str,
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
                    callback_data=f"{toggle_prefix}:{line_slug}:t:{global_idx}",
                )
            )
        if row:
            rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"{toggle_prefix}:{line_slug}:p:{page - 1}"
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data=f"{toggle_prefix}:{line_slug}:x:0",
        )
    )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="➡️", callback_data=f"{toggle_prefix}:{line_slug}:p:{page + 1}"
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
    bulk = f"bulk:sg:{line_slug}" if _is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="st",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово ✅", callback_data="kw:done"),
            _samsung_line_back_button(line_slug),
        ],
    )


def _goods_line_pick_text(line_slug: str) -> str:
    title = LINE_LABELS.get(line_slug, line_slug)
    return (
        f"{GOODS_CRUMB} › <b>Мобильные</b> › <b>Apple</b> › <b>{title}</b>\n\n"
        "Нажмите на модель — <b>вкл/выкл</b>.\n"
        f"Лимит ручного выбора для обычного пользователя: до {_max_keyword_slots({'role': 'regular'})} позиций.\n"
        "Ниже — <b>Готово</b>, возврат к линейкам или в меню."
    )


def _goods_line_keyboard(user: dict, line_slug: str, page: int) -> InlineKeyboardMarkup | None:
    models = APPLE_LINES.get(line_slug)
    if not models:
        return None
    bulk = f"bulk:ap:{line_slug}" if _is_vip_user(user) else None
    return _paginated_models_keyboard(
        user,
        models,
        line_slug,
        page,
        toggle_prefix="gt",
        bulk_callback=bulk,
        footer_buttons=[
            InlineKeyboardButton(text="Готово ✅", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ К линейкам", callback_data="goods:a"),
        ],
    )
def _build_keywords_text(user: dict) -> str:
    selected = user.get("keywords") or []
    role = user.get("role")
    limit = "без лимита ⭐" if role == "vip" else "до 5 моделей"
    return (
        f"{GOODS_CRUMB} › <b>Смартфоны</b> › <b>Все модели</b>\n\n"
        "👆 Нажмите модель — добавить или убрать из поиска.\n"
        f"📌 Лимит · <b>{limit}</b>\n\n"
        f"✅ Выбрано · <b>{len(selected)}</b>\n"
        + ("<code>" + ", ".join(selected) + "</code>" if selected else "<i>Пока ничего не выбрано</i>")
    )


def _build_model_list_text(user: dict, scope: str) -> str:
    selected = user.get("keywords") or []
    role = user.get("role")
    limit = "без лимита ⭐" if role == "vip" else "до 5 моделей"
    models = _models_for_scope(scope)
    selected_in_scope = {
        k.strip().lower()
        for k in selected
        if k.strip().lower() in {m.strip().lower() for m in models}
    }
    return (
        f"{GOODS_CRUMB} › <b>Смартфоны</b> › {_model_list_title(scope)}\n\n"
        "👆 Нажмите модель — добавить или убрать.\n"
        f"📌 Лимит · <b>{limit}</b>\n\n"
        f"✅ В этой группе · <b>{len(selected_in_scope)}</b> из <b>{len(models)}</b>\n"
        f"📱 Всего моделей · <b>{len(selected)}</b>"
    )


def _model_list_keyboard(user: dict, scope: str, *, page: int) -> InlineKeyboardMarkup:
    models = _models_for_scope(scope)
    total_pages = max(1, (len(models) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * PER_PAGE
    chunk = models[start : start + PER_PAGE]
    selected = {k.strip().lower() for k in (user.get("keywords") or []) if k.strip()}

    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row: list[InlineKeyboardButton] = []
        for j in range(2):
            if i + j >= len(chunk):
                continue
            idx = start + i + j
            item = chunk[i + j]
            mark = "✅ " if item.lower() in selected else ""
            row.append(InlineKeyboardButton(text=f"{mark}{item}", callback_data=f"ml:{scope}:t:{idx}"))
        if row:
            rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"ml:{scope}:p:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=f"ml:{scope}:x:0"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"ml:{scope}:p:{page + 1}"))
    rows.append(nav)
    if _is_vip_user(user):
        rows.append(
            [InlineKeyboardButton(text="📋 Выбрать все", callback_data=_model_list_bulk_callback(scope))]
        )
    rows.append(
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="kw:done"),
            _model_list_back_button(scope),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _keywords_keyboard(user: dict, *, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(DEVICE_CATALOG) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * PER_PAGE
    chunk = DEVICE_CATALOG[start : start + PER_PAGE]
    selected = {k.strip().lower() for k in (user.get("keywords") or []) if k.strip()}

    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row: list[InlineKeyboardButton] = []
        for j in range(2):
            if i + j >= len(chunk):
                continue
            idx = start + i + j
            item = chunk[i + j]
            mark = "✅ " if item.lower() in selected else ""
            row.append(
                InlineKeyboardButton(text=f"{mark}{item}", callback_data=f"kw:toggle:{idx}")
            )
        if row:
            rows.append(row)

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"kw:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="kw:x"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"kw:page:{page + 1}"))
    rows.append(nav)
    if _is_vip_user(user):
        rows.append([InlineKeyboardButton(text="📋 Выбрать все", callback_data="bulk:all")])
    rows.append(
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="kw:done"),
            InlineKeyboardButton(text="⬅️ Apple", callback_data="goods:a"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
