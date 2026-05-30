# Архитектура

## Структура проекта

```
main.py              # Запуск: Telegram polling + фоновый poller
poller.py            # Цикл: Kufar → фильтры → отправка
user_matching.py     # Какие объявления подходят пользователю
kufar_fetch.py       # Запросы к API Kufar
filters.py           # Правила отбора объявлений
db.py                # SQLite
config.py            # Настройки из .env
bot_ui.py            # Тексты и клавиатуры меню
formatter.py         # Формат карточки объявления
goods_tree.py        # Каталог Apple / Samsung

handlers/
  __init__.py        # Собирает все роутеры
  start.py           # /start, рефералка, ответ на текст
  nav.py             # Меню: цена, память, VIP, пауза, промокод
  goods_ui.py        # Клавиатуры выбора моделей (без роутера)
  goods.py           # Кнопки: товары, bulk, kw, ml, gt, st
  admin.py           # Админ-панель
  helpers.py         # safe_edit_message, is_admin, …
  states.py          # FSM-состояния
```

## Поток рассылки

1. `poller` один раз загружает объявления с Kufar.
2. Для каждого активного пользователя — `match_ads_for_user` (с кэшем средних цен на цикл). `smart_filtering` (жёсткие правила в `filters.py`) включён только если `role == vip`.
3. Новые объявления отправляются в Telegram (`formatter.format_ad`).

### VIP-потоки (`users.vip_feed_mode`)

| Режим | Где фильтруется |
|-------|-----------------|
| `normal` | Базовые фильтры + модели/память |
| `below_market` | + цена ниже средней |
| `exchange` | + `is_exchange_ad` |
| `ideal` | pre: `ideal_passes(stage=pre)` в `user_matching`; strict: enrich описаний → `ideal_passes(stage=strict)` в `poller`; отклонённые strict помечаются `seen` |

Правила «Идеальные» — `filters.py` (`IDEAL_*`, `parse_battery_percents`); состояние из `condition_label` в `kufar_fetch.normalize_listing`.

## Поток кнопок

1. Сообщение попадает в один из роутеров (`start` → `nav` → `goods` → `admin`).
2. Чтение/запись настроек — только через `db.py`.
3. Экран «Товары» — логика клавиатур в `goods_ui.py`, обработка нажатий в `goods.py`.

### Ветка «Товары и модели»

| Кнопка | callback | Файл |
|--------|----------|------|
| Товары и модели | `nav:goods` | `nav.py` → `goods_category_*` из `bot_ui.py` |
| Смартфоны | `goods:m` | `goods.py` → `_goods_mobile_brands_*` из `goods_ui.py` |
| Apple / Samsung | `goods:a` / `goods:s` | `goods.py` |
| Модель в линейке | `gt:` / `st:` / `kw:` | `goods.py` |

В `goods.py` функции из `goods_ui` импортируются **явно** (не `import *` — иначе имена с `_` не подхватываются).

## Скорость

- Один fetch Kufar на цикл, не на пользователя; до `KUFAR_MAX_PAGES` страниц на запрос (cursor).
- Разные интервалы опроса для VIP и обычных аккаунтов.
- Кэш `market_prices` в памяти на один проход poller; в БД — только цены за `PRICE_DATA_RETENTION_DAYS` (по умолчанию 14), старые строки prune при старте и в poller.
- Минимум лишних запросов к БД в хендлерах (один `get_user` после обновления username).
