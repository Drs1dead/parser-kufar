# Руководство разработчика — Kufar Support Bot

Полное описание проекта: назначение модулей, потоки данных, база, конфигурация, Telegram UI и отладка.

**Связанные файлы:** [README.md](README.md) (запуск и деплой), [ARCHITECTURE.md](ARCHITECTURE.md) (краткая схема).

---

## Содержание

1. [Что делает бот](#1-что-делает-бот)
2. [Два движка при запуске](#2-два-движка-при-запуске)
3. [Карта файлов](#3-карта-файлов)
4. [Запуск и конфигурация](#4-запуск-и-конфигурация)
5. [База данных](#5-база-данных)
6. [Поток рассылки](#6-поток-рассылки)
7. [Kufar API](#7-kufar-api)
8. [Фильтры](#8-фильтры)
9. [Telegram UI и handlers](#9-telegram-ui-и-handlers)
10. [Обычный vs VIP](#10-обычный-vs-vip)
11. [Формат сообщений](#11-формат-сообщений)
12. [Типичные задачи](#12-типичные-задачи)
13. [Тесты](#13-тесты)
14. [Порядок чтения кода](#14-порядок-чтения-кода)
15. [Ограничения и подводные камни](#15-ограничения-и-подводные-камни)

---

## 1. Что делает бот

Telegram-бот на **aiogram 3**, который подписывает пользователей на **новые объявления с Kufar.by** (в основном iPhone и Samsung). Пользователь в меню задаёт:

- **модели** (keywords),
- **объём памяти**,
- **максимальную цену** (Br / BYN),
- включает или ставит на паузу рассылку.

Фоновый процесс (`poller.py`) периодически загружает листинг с API Kufar, отфильтровывает объявления и отправляет подходящие в чат. Есть **VIP**: другие интервалы, больше моделей, потоки «ниже рынка / обмен / идеальные», рефералка и промокоды. Данные — **SQLite**.

---

## 2. Два движка при запуске

При `python main.py` работают **две параллельные asyncio-задачи**:


| Движок               | Файлы                  | Назначение                             |
| -------------------- | ---------------------- | -------------------------------------- |
| **Polling Telegram** | `main.py`, `handlers/` | Кнопки, `/start`, настройки, админка   |
| **Poller рассылки**  | `poller.py`            | Цикл: Kufar → фильтры → отправка в чат |


```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│  init_db() → Bot + Dispatcher → include_router(handlers)     │
│              → asyncio.create_task(poller(bot))              │
│              → dp.start_polling()                            │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────┐              ┌──────────────────────────┐
│ handlers/*      │              │ poller.py (бесконечный цикл)│
│ Telegram updates│              │  sleep(CHECK_INTERVAL)     │
└─────────────────┘              │  → fetch_ads (1× на цикл)  │
                                 │  → для каждого active user │
                                 │  → match → send            │
                                 └──────────────────────────┘
```

**Важно:** Kufar запрашивается **один раз на цикл** для всех подписчиков, а не отдельно на каждого пользователя.

### Последовательность старта (`main.py`)


| Шаг | Действие                                                                  |
| --- | ------------------------------------------------------------------------- |
| 1   | `configure_logging()`                                                     |
| 2   | Проверка `TOKEN`, `CHECK_INTERVAL`, `MARKET_DISCOUNT_THRESHOLD`           |
| 3   | `init_db()` — схема, миграции колонок, prune                              |
| 4   | `Bot` + `BOT_USERNAME` для реферальных ссылок                             |
| 5   | `Dispatcher` + `handlers.router`                                          |
| 6   | Фоновая задача `poller(bot)`                                              |
| 7   | `start_polling`; при выходе — cancel poller, закрыть сессию, `db.close()` |


---

## 3. Карта файлов

### Корень проекта


| Файл / папка         | Назначение                                                                |
| -------------------- | ------------------------------------------------------------------------- |
| `main.py`            | Точка входа: env, БД, бот, роутеры, фоновый poller                        |
| `config.py`          | Настройки из `.env`, каталог устройств, стоп-слова, хелперы цены/даты     |
| `db.py`              | Единственный слой SQLite: пользователи, seen, рынок, VIP, промо, рефералы |
| `poller.py`          | Рассылка: expiry VIP, fetch, matching, enrich, отправка                   |
| `user_matching.py`   | Сопоставление объявлений с профилем и VIP-потоком                         |
| `filters.py`         | Правила отбора объявлений                                                 |
| `kufar_fetch.py`     | HTTP к Kufar, нормализация, описание со страницы                          |
| `formatter.py`       | HTML карточки объявления для Telegram                                     |
| `bot_ui.py`          | Тексты экранов и inline-клавиатуры                                        |
| `goods_tree.py`      | Дерево Apple/Samsung из `DEVICE_CATALOG`                                  |
| `logging_setup.py`   | Настройка логов, `log_exception`                                          |
| `.env.example`       | Шаблон переменных окружения                                               |
| `requirements.txt`   | Зависимости Python                                                        |
| `README.md`          | Запуск, деплой BotHost, продуктовые правила                               |
| `ARCHITECTURE.md`    | Краткая архитектура и callback-таблица «Товары»                           |
| `DEVELOPER_GUIDE.md` | Этот документ                                                             |


### `handlers/` — Telegram


| Файл          | Назначение                                            |
| ------------- | ----------------------------------------------------- |
| `__init__.py` | Сборка роутеров: `nav` → `goods` → `admin` → `start`  |
| `start.py`    | `/start`, `?start=ref_`*, любой текст → главное меню  |
| `nav.py`      | Меню, цена, память, VIP, пауза, промокод, FSM цены    |
| `goods.py`    | Callback выбора моделей (`goods:`, `bulk:`, `kw:`, …) |
| `goods_ui.py` | Клавиатуры каталога (без роутера)                     |
| `admin.py`    | Панель для `ADMIN_IDS`                                |
| `helpers.py`  | `safe_edit_message`, `require_user_cb`, `is_admin`    |
| `states.py`   | FSM-состояния (промо, цена, админ)                    |


### Тесты


| Файл                      | Что проверяет             |
| ------------------------- | ------------------------- |
| `test_filters.py`         | Правила `filters.py`      |
| `test_ideal_filters.py`   | Поток «Идеальные»         |
| `test_goods_tree.py`      | `goods_tree.py`           |
| `test_goods_handlers.py`  | Callback товаров          |
| `test_referrals.py`       | Реферальная программа     |
| `test_price_retention.py` | Retention `market_prices` |
| `test_formatter_time.py`  | Время в сообщениях        |
| `test_sprint2.py`         | Прочие сценарии           |


Запуск: `python -m unittest discover -v`

### Данные (не в Git)


| Путь               | Когда                         |
| ------------------ | ----------------------------- |
| `data/bot.db`      | Локальная разработка          |
| `/app/data/bot.db` | BotHost (персистентная папка) |
| `DB_PATH` в `.env` | Явное указание пути           |


---

## 4. Запуск и конфигурация

```bash
cp .env.example .env   # заполнить TOKEN, ADMIN_IDS
pip install -r requirements.txt
python main.py
```

### Основные переменные `.env`


| Переменная                     | По умолчанию     | Смысл                                       |
| ------------------------------ | ---------------- | ------------------------------------------- |
| `TOKEN`                        | —                | Токен Telegram-бота                         |
| `ADMIN_IDS`                    | —                | ID админов через запятую                    |
| `DB_PATH`                      | авто             | Путь к SQLite                               |
| `CHECK_INTERVAL`               | 10               | Тик poller (сек), не длиннее VIP            |
| `VIP_CHECK_INTERVAL`           | 30               | Мин. интервал рассылки для VIP              |
| `REGULAR_CHECK_INTERVAL`       | 420              | Мин. интервал для обычного (~7 мин)         |
| `FIRST_RUN_LIMIT`              | 3                | Сколько объявлений при первом включении     |
| `KUFAR_QUERY`                  | iphone, samsung… | Поисковые запросы через запятую             |
| `KUFAR_REGION`                 | 7                | Регион Kufar                                |
| `KUFAR_SIZE`                   | 40               | Объявлений на страницу API                  |
| `KUFAR_MAX_PAGES`              | 2                | Страниц cursor на запрос                    |
| `MARKET_DISCOUNT_THRESHOLD`    | 0.85             | Порог «ниже рынка» (доля от средней)        |
| `PRICE_DATA_RETENTION_DAYS`    | 14               | Хранение цен для средней                    |
| `SEEN_ADS_RETENTION_DAYS`      | 90               | Хранение `seen_ads`                         |
| `IDEAL_MIN_BATTERY_PERCENT`    | 75               | Мин. % АКБ для потока «Идеальные»           |
| `LOG_LEVEL`                    | INFO             | DEBUG — подробные логи и traceback          |
| `FILTER_DEBUG_LOG`             | false            | Лог причин отклонения объявлений            |
| `REFERRAL_VIP_DAYS_PER_FRIEND` | 1                | Дней VIP за приглашённого                   |
| `DISPLAY_TIMEZONE`             | Europe/Minsk     | Часовой пояс в карточках                    |


Полный список констант и списков стоп-слов — в `**config.py`**.

### Где что лежит в `config.py`


| Блок      | Примеры                                                                                      |
| --------- | -------------------------------------------------------------------------------------------- |
| Время     | `DISPLAY_TZ`, `format_local_datetime()`                                                      |
| Деньги    | `CURRENCY_SIGN`, `format_price()`, `MAX_PRICE_PRESETS`                                       |
| Память    | `MEMORY_VOLUME_OPTIONS`, `DEFAULT_MEMORY_VOLUMES`                                            |
| Kufar     | `KUFAR_QUERIES`, `KUFAR_REGION`, `KUFAR_SIZE`                                                |
| Каталог   | `DEVICE_CATALOG`, `DEFAULT_KEYWORDS`                                                         |
| Фильтры   | `DEFAULT_EXCLUDE_TERMS`, `PARTS_EXCLUDE_TERMS`, `NOT_SALE_TERMS`, `ACCESSORY_HEADLINE_STEMS` |
| VIP ideal | `IDEAL_ALLOWED_CONDITIONS`, `IDEAL_MIN_BATTERY_PERCENT`                                      |
| Админ     | `ADMIN_IDS`                                                                                  |


---

## 5. База данных

Файл: `**db.py**`. Один connection, `threading.RLock`, WAL mode.

### Выбор пути к БД


| Приоритет | Путь                                                          |
| --------- | ------------------------------------------------------------- |
| 1         | `DB_PATH` из `.env`                                           |
| 2         | `/app/data/bot.db` если есть `/app/data` (BotHost)            |
| 3         | `<проект>/data/bot.db` + миграция из старого `bot.db` в корне |


### Таблицы


| Таблица             | Назначение                            | Ключевые поля                                                                                                                                                              |
| ------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `users`             | Профиль подписчика                    | `chat_id`, `active`, `role`, `vip_until`, `max_price`, `keywords`, `memory_volumes`, `vip_feed_mode`, `referral_code`, `referred_by`, `poll_last_vip`, `poll_last_regular` |
| `seen_ads`          | Уже показанные объявления             | `(chat_id, link)`, `seen_at`                                                                                                                                               |
| `market_prices`     | Глобальные цены для средней по модели | `link`, `device_key`, `price`, `sent_at`                                                                                                                                   |
| `sent_prices`       | Вспомогательная история цен           | prune вместе с `market_prices`                                                                                                                                             |
| `promo_codes`       | Промокоды VIP                         | `code`, `vip_days`, `max_uses`, `is_active`                                                                                                                                |
| `promo_activations` | Кто активировал промо                 | `(chat_id, code)`                                                                                                                                                          |
| `referrals`         | Реферальные связи                     | `referred_chat_id` → `referrer_chat_id`                                                                                                                                    |


### Словарь пользователя (`get_user`)

После `get_user(chat_id)` в коде приходит `dict`:


| Ключ                                  | Тип / значение                                   |
| ------------------------------------- | ------------------------------------------------ |
| `chat_id`                             | int                                              |
| `active`                              | bool — рассылка включена                         |
| `role`                                | `"regular"` | `"vip"`                            |
| `vip_until`                           | Unix timestamp окончания VIP                     |
| `max_price`                           | int, Br                                          |
| `keywords`                            | `list[str]` — модели в нижнем регистре           |
| `memory_volumes`                      | `list[str]` — `"64"`, `"128"`, …, `"512+"`       |
| `vip_feed_mode`                       | `normal` | `below_market` | `exchange` | `ideal` |
| `referral_code`                       | строка для ссылки                                |
| `referred_by`                         | chat_id пригласившего или None                   |
| `poll_last_vip` / `poll_last_regular` | время последней рассылки                         |


### API `db.py` по задачам


| Задача       | Функции                                                                                                               |
| ------------ | --------------------------------------------------------------------------------------------------------------------- |
| Регистрация  | `add_user`, `get_user`, `set_active`, `update_user_username`                                                          |
| Настройки    | `update_max_price`, `update_keywords`, `update_memory_volumes`, `update_vip_feed_mode`                                |
| VIP          | `set_vip`, `revoke_vip`, `expire_all_vip`, `grant_vip_days`, `redeem_promo_code`                                      |
| Рассылка     | `get_active_users`, `seen_links_for`, `mark_seen`, `count_seen`, `increment_sent`, `set_poll_last_run`                |
| Рынок        | `save_market_price`, `avg_market_price`, `clear_market_prices`, `prune_price_tables`                                  |
| Рефералы     | `process_referral_signup`, `ensure_referral_code`, `count_referrals`, `get_user_by_referral_code`                     |
| Админ        | `list_users_page`, `find_users_by_username`, `delete_user_completely`, `create_promo_code`, `list_active_promo_codes` |
| Обслуживание | `init_db`, `prune_seen_ads`, `close`, `checkpoint_wal`                                                                |


### Поведение VIP при истечении


| Событие                            | Что происходит                                                             |
| ---------------------------------- | -------------------------------------------------------------------------- |
| Естественное окончание `vip_until` | `role` → regular, память → **64 GB**, модели и `max_price` **сохраняются** |
| `revoke_vip` в админке             | То же + явный сброс                                                        |
| Уведомление                        | Текст из `poller.VIP_EXPIRED_MSG`                                          |


Встроенный промокод при `init_db`: `**VIPTRIAL7`** (7 дней).

---

## 6. Поток рассылки

Файл: `**poller.py**`.

### Цикл poller (тик `CHECK_INTERVAL`, VIP и обычные раздельно)

```
expire_all_vip / prune (реже, чем тик)
users = get_active_users()
VIP due → fetch только их ключи → _process_user → mark polled
обычные due → свой fetch
sleep(min(CHECK_INTERVAL, время до следующего due))
```

### Интервал на пользователя


| Роль    | Поле в БД           | Интервал из config       |
| ------- | ------------------- | ------------------------ |
| VIP     | `poll_last_vip`     | `VIP_CHECK_INTERVAL`     |
| Обычный | `poll_last_regular` | `REGULAR_CHECK_INTERVAL` |


Если `poll_last_* == 0` — обрабатывается сразу (первый раз после регистрации/сброса).

### `_process_user` — логика отправки


| Этап | Описание                                                                                           |
| ---- | -------------------------------------------------------------------------------------------------- |
| 1    | `match_ads_for_user()` — список подходящих                                                         |
| 2    | Первый запуск (`count_seen == 0`): не больше `FIRST_RUN_LIMIT`, остальные → `mark_seen`            |
| 3    | Режим `ideal`: enrich описаний → `ideal_passes(strict)`; отклонённые → seen                        |
| 4    | Иначе: enrich только если описание пустое                                                          |
| 5    | Исключить уже в `seen_links_for`                                                                   |
| 6    | Для VIP: средняя цена из `market_cache` / `avg_market_price`                                       |
| 7    | `_send_ad()` — медиагруппа или текст; при успехе → seen, increment_sent, `save_market_price` (VIP) |


### Сопоставление — `user_matching.py`


| Условие                     | Поведение                                                                     |
| --------------------------- | ----------------------------------------------------------------------------- |
| Обычный пользователь        | `max_price` из профиля, `basic_filtering=True`, без `smart_filtering`         |
| VIP, `vip_feed_mode=normal` | `smart_filtering=True`, лимит цены из профиля                                 |
| VIP `below_market`          | Лимит цены **не** действует (`VIP_SPECIAL_MAX_PRICE`); цена < средней × порог |
| VIP `exchange`              | Только `is_exchange_ad`                                                       |
| VIP `ideal`                 | Pre: `ideal_passes(pre)`; strict — в poller после описания                    |


Центральный вызов фильтров: `**matches_filters()**` в `filters.py` (см. раздел 8).

### VIP-потоки (`users.vip_feed_mode`)


| Режим          | Где отсекается                       | Особенности                                      |
| -------------- | ------------------------------------ | ------------------------------------------------ |
| `normal`       | `user_matching` + `filters`          | Все подходящие по моделям/памяти/цене            |
| `below_market` | `user_matching._below_market_accept` | Нужна средняя в `market_prices`                  |
| `exchange`     | `user_matching._exchange_accept`     | Текст про обмен                                  |
| `ideal`        | pre в matching, strict в poller      | Пропуск «новых» телефонов на pre; % АКБ в strict |


### Пополнение `market_prices`


| Источник                         | Когда                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------ |
| `_ingest_market_prices_from_ads` | После каждого fetch: целые телефона из листинга (VIP-фильтр без device/memory) |
| После успешной отправки VIP      | `save_market_price` в `_process_user`                                          |


Средняя: `**avg_market_price(device_key)**` за последние `PRICE_DATA_RETENTION_DAYS` дней.

---

## 7. Kufar API

Файл: `**kufar_fetch.py**`.

### Endpoints и запросы


| Что       | URL / способ                                                       |
| --------- | ------------------------------------------------------------------ |
| Листинг   | `GET https://api.kufar.by/search-api/v2/search/rendered-paginated` |
| Параметры | `query`, `size`, `rgn`, `cur=BYR`, `sort=lst.d`, `cursor`          |
| Описание  | `GET` страница объявления → regex `__NEXT_DATA_`_ → `body`         |


### Нормализованное объявление (`dict`)


| Поле                          | Смысл                               |
| ----------------------------- | ----------------------------------- |
| `ad_id`                       | ID на Kufar                         |
| `title`                       | Заголовок (subject)                 |
| `price`                       | BYN, целое                          |
| `price_usd`                   | опционально                         |
| `location`                    | регион, район                       |
| `summary`                     | Состояние, модель, память, цвет     |
| `condition_label`             | Состояние из параметров             |
| `phone_model`, `phone_memory` | Сырые поля Kufar                    |
| `memory_gb`                   | int или None                        |
| `description`                 | Текст (может быть пустым до enrich) |
| `link`                        | URL без query                       |
| `list_time`                   | Время публикации                    |
| `photo_urls`                  | До 5 URL галереи                    |


### `fetch_ads(with_description=...)`


| `with_description` | Использование                                              |
| ------------------ | ---------------------------------------------------------- |
| `True`             | Полная подгрузка описаний для всех (дорого)                |
| `False`            | Poller: только листинг; описания точечно в `_process_user` |


Дедупликация по `ad_id` между несколькими `KUFAR_QUERIES`.

---

## 8. Фильтры

Файл: `**filters.py**`. Списки терминов — `**config.py**`.

### Флаги `matches_filters()`


| Флаг              | Когда True                | Эффект                                        |
| ----------------- | ------------------------- | --------------------------------------------- |
| `smart_filtering` | VIP (обычный поток)       | Жёсткий отбор: не продажа, новый, запчасти, … |
| `basic_filtering` | regular                   | Отсев коробок/аксессуаров по заголовку        |
| `device_filter`   | matching для пользователя | Модель ∈ `keywords`                           |
| `memory_filter`   | matching                  | Объём ∈ `memory_volumes`                      |
| `skip_new_phone`  | ideal pre                 | Не отсекать «новый» на pre-стадии             |


### Основные функции


| Функция                                  | Назначение                              |
| ---------------------------------------- | --------------------------------------- |
| `matches_filters`                        | Проходит / не проходит                  |
| `filter_reject_reason`                   | Код причины (для логов и тестов)        |
| `ad_device_key`                          | Ключ модели для `market_prices`         |
| `is_whole_phone_listing`                 | Целый телефон vs аксессуар              |
| `is_exchange_ad`                         | Объявление про обмен                    |
| `ideal_passes(ad, stage="pre"|"strict")` | Поток «Идеальные»                       |
| `parse_battery_percents`                 | % АКБ из текста                         |
| `memory_matches_ad`                      | Память объявления vs выбор пользователя |


### Коды отклонения (примеры)


| Константа                  | Смысл                 |
| -------------------------- | --------------------- |
| `REJECT_PRICE_HIGH`        | Цена выше лимита      |
| `REJECT_NO_KEYWORDS`       | Модель не в выбранных |
| `REJECT_NOT_WHOLE_PHONE`   | Не целый телефон      |
| `REJECT_IDEAL_BATTERY_LOW` | Низкий % АКБ          |
| `REJECT_EXCHANGE_NO_HINT`  | Нет признаков обмена  |


Отладка: `.env` → `FILTER_DEBUG_LOG=true`.

---

## 9. Telegram UI и handlers

### Порядок роутеров (`handlers/__init__.py`)

```
nav → goods → admin → start
```

`start` в конце: ловит `/start` и **любой текст** → главное меню (сбрасывает FSM).

### Callback-префиксы


| Префикс                    | Файл       | Примеры                                           |
| -------------------------- | ---------- | ------------------------------------------------- |
| `nav:`                     | `nav.py`   | `nav:home`, `nav:set:500`, `nav:vip`, `nav:pause` |
| `mem:t:`                   | `nav.py`   | `mem:t:128` — переключение памяти                 |
| `goods:`                   | `goods.py` | `goods:m` — смартфоны                             |
| `bulk:`                    | `goods.py` | Массовый выбор (VIP)                              |
| `kw:`, `ml:`, `gt:`, `st:` | `goods.py` | Модели по индексу / линейке                       |
| `adm:`                     | `admin.py` | `adm:st`, `adm:us:0`, `adm:promo`                 |


### Ветка «Товары и модели»


| Шаг              | callback              | Файлы                                   |
| ---------------- | --------------------- | --------------------------------------- |
| Товары           | `nav:goods`           | `nav.py` → `bot_ui.goods_category_*`    |
| Смартфоны        | `goods:m`             | `goods.py` → `goods_ui._goods_mobile_*` |
| Apple / Samsung  | `goods:a` / `goods:s` | `goods.py`                              |
| Линейка / модель | `gt:`, `st:`, `kw:`   | `goods.py` + `goods_tree.py`            |


**Важно:** в `goods.py` импорт из `goods_ui` — **явный** (не `import *`), иначе функции с `_` не подхватятся.

### FSM (`handlers/states.py`)


| StatesGroup            | Состояние          | Назначение              |
| ---------------------- | ------------------ | ----------------------- |
| `PromoCodeState`       | `waiting_code`     | Ввод промокода          |
| `CustomPriceState`     | `waiting_price`    | Своя цена (VIP)         |
| `AdminPromoState`      | несколько          | Создание/удаление промо |
| `AdminUserSearchState` | `waiting_username` | Поиск пользователя      |
| `AdminVipGrantState`   | `waiting_days`     | Выдача VIP              |


### Рефералка


| Элемент    | Где                                                                 |
| ---------- | ------------------------------------------------------------------- |
| Ссылка     | `bot_ui.referral_link_for_user` → `https://t.me/BOT?start=ref_CODE` |
| Парсинг    | `start.extract_referral_code`                                       |
| Начисление | `db.process_referral_signup` + уведомление пригласившему            |


Правила: только **новый** пользователь; повторный `/start` не даёт бонус; свою ссылку использовать нельзя.

### Разделение UI и логики


| Слой                     | Файл                 | Содержит                                          |
| ------------------------ | -------------------- | ------------------------------------------------- |
| Тексты и клавиатуры меню | `bot_ui.py`          | `home_text`, `home_keyboard`, VIP, память, помощь |
| Клавиатуры каталога      | `goods_ui.py`        | Apple/Samsung, пагинация, лимиты keywords         |
| Обработка нажатий        | `nav.py`, `goods.py` | Чтение/запись через `db.py`                       |
| Хелперы Telegram         | `helpers.py`         | `safe_edit_message`, `require_user_cb`            |


---

## 10. Обычный vs VIP


| Возможность             | Обычный                            | VIP                                      |
| ----------------------- | ---------------------------------- | ---------------------------------------- |
| Моделей в keywords      | 1 (`REGULAR_MAX_KEYWORDS`)         | без лимита (`goods_ui._max_keyword_slots`) |
| Память                  | один объём                         | несколько; нельзя снять последний        |
| Интервал рассылки       | `REGULAR_CHECK_INTERVAL` (~7 мин) | `VIP_CHECK_INTERVAL` (~30 с)             |
| Фильтры                 | basic + цена/модель/память         | + smart (жёсткий отбор)                  |
| Потоки рассылки         | только normal                      | normal / below_market / exchange / ideal |
| Средняя цена в карточке | нет                                | да                                       |
| Своя цена (FSM)         | нет                                | да                                       |
| Промокод / реферал      | реферал только у VIP во вкладке    | да                                       |


### Память в БД


| Пользователь                   | Формат `memory_volumes`            |
| ------------------------------ | ---------------------------------- |
| regular                        | один токен, напр. `64`             |
| VIP                            | CSV, напр. `64,128,256`            |
| токен `512+`                   | «от 512 ГБ» (1 ТБ и т.д.)          |
| память не указана в объявлении | проходит под любой выбранный объём |


---

## 11. Формат сообщений

Файл: `**formatter.py`**.


| Функция               | Назначение                                                         |
| --------------------- | ------------------------------------------------------------------ |
| `format_ad(...)`      | HTML-карточка: заголовок, цена, локация, summary, описание, ссылка |
| `truncate_ad_caption` | Укорочение под лимит caption Telegram (1024)                       |
| `format_status`       | Статус пользователя для админки                                    |


Параметры `format_ad`:


| Параметр           | Эффект                            |
| ------------------ | --------------------------------- |
| `market_avg_price` | Показ средней (VIP)               |
| `below_market`     | Метка «ниже рынка»                |
| `ideal_feed`       | Оформление для потока «Идеальные» |


Poller: до **5 фото** в `send_media_group`, иначе `send_message`; при ошибке медиа — fallback на текст.

---

## 12. Типичные задачи


| Задача                           | Куда смотреть                                                           |
| -------------------------------- | ----------------------------------------------------------------------- |
| Текст кнопки / экрана            | `bot_ui.py`, при необходимости `handlers/nav.py`                        |
| Новая модель телефона            | `config.py` → `DEVICE_CATALOG`; при необходимости `goods_tree.py`       |
| Ужесточить отбор                 | `filters.py`, списки в `config.py`                                      |
| Частота рассылки                 | `.env`, `poller._should_process_user`                                   |
| Новый VIP-поток                  | `user_matching.py`, `poller.py`, `bot_ui.py`, `db.update_vip_feed_mode` |
| Не приходят объявления           | `active`, `keywords`, `seen_ads`, логи poller, `FILTER_DEBUG_LOG`       |
| Разная «средняя» у пользователей | один инстанс бота, одна БД, `market_prices`                             |
| Деплой BotHost                   | `README.md`, `DB_PATH=/app/data/bot.db`                                 |
| Админ-функция                    | `handlers/admin.py`, `db.py`                                            |
| Стоп-слово в заголовке           | `config.DEFAULT_EXCLUDE_TERMS`                                          |
| Запчасти / платы                 | `config.PARTS_EXCLUDE_TERMS`                                            |


---

## 13. Тесты

```bash
python -m unittest discover -v
```

На продакшен-сервере тесты **не обязательны**; локально — после правок в `filters.py`, рефералке, каталоге.

---

## 14. Порядок чтения кода


| #   | Файл                              | Зачем                             |
| --- | --------------------------------- | --------------------------------- |
| 1   | `README.md`                       | Продукт и деплой                  |
| 2   | `main.py`                         | Старт и два движка                |
| 3   | `config.py`                       | Все настройки                     |
| 4   | `db.py`                           | `init_db`, `get_user`, `add_user` |
| 5   | `handlers/start.py` + `bot_ui.py` | Вход пользователя                 |
| 6   | `kufar_fetch.py`                  | Откуда данные                     |
| 7   | `filters.py`                      | Правила                           |
| 8   | `user_matching.py`                | Связка user + ads                 |
| 9   | `poller.py`                       | Рассылка end-to-end               |
| 10  | `handlers/nav.py`, `goods.py`     | Настройки                         |
| 11  | `handlers/admin.py`               | Операции админа                   |


---

## 15. Ограничения и подводные камни


| Тема               | Деталь                                                                   |
| ------------------ | ------------------------------------------------------------------------ |
| Один инстанс       | Несколько процессов / разные `DB_PATH` → разные средние и дубли рассылки |
| Любой текст        | `start.on_any_text` сбрасывает FSM и показывает главное меню             |
| Блокировка бота    | `TelegramForbiddenError` → `set_active(False)`                           |
| Описания Kufar     | Отдельный HTTP на карточку; в poller — точечная подгрузка                |
| `import `* в goods | Не использовать — ломает импорт `_`-функций из `goods_ui`                |
| Git и БД           | `bot.db`, `data/` в `.gitignore` — бэкапить вручную на BotHost           |
| Callback data      | Лимит Telegram 64 байта — короткие slug в `goods_tree.py`                |
| Истечение VIP      | Память → 64 GB; модели и цена сохраняются                                |


---

## Диаграмма: от Kufar до чата пользователя

```
Kufar API                    poller                      Telegram
    │                           │                            │
    ├─ fetch_ads ──────────────►│                            │
    │   (normalize_listing)     │                            │
    │                           ├─ match_ads_for_user       │
    │                           │   (filters.py)            │
    │                           ├─ enrich descriptions      │
    │                           │   (ideal / пустые)        │
    │                           ├─ format_ad                │
    │                           └─ send_message / media ───►│
    │                                                        user
    └─ (опционально) HTML страница для description ─────────►│
```

---

## Диаграмма: настройки пользователя

```
Пользователь → inline-кнопка → handlers (nav/goods/admin)
                                    │
                                    ▼
                              db.update_* / set_*
                                    │
                                    ▼
                              SQLite users
                                    │
         poller читает get_active_users + get_user поля
                                    │
                                    ▼
                              match_ads_for_user → рассылка
```

---

*Документ сгенерирован для сопровождения кодовой базы Kufar Support Bot. При изменении архитектуры обновляйте этот файл вместе с `ARCHITECTURE.md`.*