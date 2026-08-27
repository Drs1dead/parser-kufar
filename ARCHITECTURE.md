# Архитектура

## Структура проекта

```
main.py              # Запуск: Telegram polling + фоновый poller
poller.py            # Цикл: Kufar → фильтры → отправка
user_matching.py     # Какие объявления подходят пользователю
kufar_fetch.py       # Запросы к API Kufar
kufar_catalog.py     # Фасеты cat/phm/ppm/ot/rgn/ar по категории
kufar_geo.py         # Поиск населённых пунктов (data/kufar_geo.json)
product_catalog.py   # Категории и списки моделей
filters.py           # Правила отбора объявлений
db.py                # SQLite
config.py            # Настройки из .env
bot_ui.py            # Тексты и клавиатуры меню
formatter.py         # Формат карточки объявления
goods_tree.py        # Линейки внутри категории

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

1. `poller` берёт due-пользователей. При `KUFAR_USE_CATALOG` группирует их по ключу `категория + rgn + ar + модели + память` (память только у смартфонов) и качает Kufar **один раз на ключ** (с TTL-кэшем ~18 с). Текстовый `query` не используем: на Kufar это полнотекст, а не фильтр модели.
2. Для каждого due — `match_ads_for_user` по батчу его ключа. При catalog: без `smart_filtering` (кроме VIP «идеальные»), магазины (`company_ad`) и тонкий антихлам в заголовке; модель (и память у смартфонов) ещё раз проверяются локально.
3. Новые объявления отправляются в Telegram (`formatter.format_ad`).

Фасеты: [`kufar_catalog.py`](kufar_catalog.py). Старый текстовый fetch (`KUFAR_QUERIES`) — если `KUFAR_USE_CATALOG=false`.

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

### Ветка «Товары»

| Кнопка | callback | Файл |
|--------|----------|------|
| Товары | `nav:goods` | `nav.py` → категории |
| Категория | `gc:` / `gx:` | `goods.py` |
| Смартфоны | `goods:m` / `goods:a` / `goods:s` | `goods.py` |
| Модель в линейке | `gt:` / `st:` / `lt:` / `pt:` / `wt:` | `goods.py` |

В `goods.py` функции из `goods_ui` импортируются **явно** (не `import *` — иначе имена с `_` не подхватываются).

## Скорость

- При `KUFAR_USE_CATALOG` — один fetch на уникальный ключ (категория+город+модели+память), не на пользователя; до `KUFAR_MAX_PAGES` страниц на запрос (cursor).
- VIP опрашивается отдельно (~30 с), обычные — реже (~7 мин); тик poller не длиннее VIP и не ждёт fetch обычных.
- Кэш `market_prices` в памяти на один проход poller; в БД — только цены за `PRICE_DATA_RETENTION_DAYS` (по умолчанию 14), старые строки prune при старте и в poller.
- Минимум лишних запросов к БД в хендлерах (один `get_user` после обновления username).
