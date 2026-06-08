# 🌸 Iris Bot 2.0

Многофункциональный Telegram-бот для управления чатами, развлечений и виртуальной экономики.

---

## 📁 Архитектура проекта

```
iris_bot/
│
├── bot.py                  # Точка входа: инициализация Bot, Dispatcher, подключение роутеров
├── config.py               # Настройки через pydantic-settings (.env)
├── requirements.txt
├── .env.example
│
├── database/
│   ├── db.py               # SQLAlchemy модели (User, Transfer, Marriage, Warning, ...)
│   └── repo.py             # Репозиторий — все CRUD-операции
│
├── handlers/               # Роутеры по модулям (паттерн Router)
│   ├── moderation.py       # !бан, !кик, !мут, !варн, автофильтр, приветствие
│   ├── economy.py          # /баланс, /бонус, /перевод, казино, кости, ставки, РП
│   ├── reputation.py       # +/- карма, /топ, /профиль
│   ├── marriage.py         # /брак, /развод, /браки
│   └── misc.py             # /старт, /помощь, /настройки, /правила
│
├── middlewares/
│   ├── admin.py            # AdminMiddleware — добавляет is_admin в data
│   └── antiflood.py        # AntiFloodMiddleware — ограничение сообщений
│
└── utils/
    └── helpers.py          # mention_user, parse_duration, format_balance, ...
```

---

## ⚙️ Установка

```bash
# 1. Клонируй репозиторий / распакуй архив
cd iris_bot

# 2. Создай виртуальное окружение
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Установи зависимости
pip install -r requirements.txt

# 4. Создай .env файл
cp .env.example .env
# Открой .env и вставь токен бота

# 5. Запусти
python bot.py
```

---

## 📦 БД: SQLite vs PostgreSQL

В `.env` меняй строку подключения:

```bash
# SQLite (дефолт, подходит для тестов)
DATABASE_URL=sqlite+aiosqlite:///iris_bot.db

# PostgreSQL (рекомендуется для продакшна)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/iris_bot
```

---

## 🗂️ Описание модулей

### 🛡️ Модерация (`handlers/moderation.py`)

| Команда | Описание |
|---------|----------|
| `!бан [причина]` | Перманентный бан (ответ на сообщение) |
| `!кик [причина]` | Исключение из чата |
| `!мут [10m/2h/1d] [причина]` | Заглушить на время |
| `!анмут` | Снять мут |
| `!варн [причина]` | Выдать предупреждение (автобан при MAX_WARNINGS) |

Автофильтр: запрещённые слова + ссылки (настраивается через `/add_word`, `/set_links`).

### 💰 Экономика (`handlers/economy.py`)

| Команда | Описание |
|---------|----------|
| `/баланс` | Показать ириски |
| `/бонус` | Ежедневная награда (раз в 24 часа) |
| `/перевод [сумма]` | Перевод другому пользователю (ответ) |
| `/казино [ставка] [вариант]` | Рулетка: red/black/green/even/odd/число |
| `/кости [ставка]` | Два кубика против бота |
| `/ставка [сумма] [орёл/решка]` | Монетка |

РП-команды: `!обнять`, `!поцеловать`, `!ударить`, `!погладить`, `!укусить`, `!подмигнуть`

### ⭐ Репутация (`handlers/reputation.py`)

- `+` или `-` в ответ на сообщение — изменить репутацию (раз в 24 часа на пользователя)
- `/профиль` — статистика пользователя
- `/топ` — топ богачей / активных / репутации

### 💑 Браки (`handlers/marriage.py`)

| Команда | Описание |
|---------|----------|
| `/брак` | Предложение (ответ на сообщение) |
| `да` / `нет` | Принять/отклонить предложение (60 сек.) |
| `/развод` | Расторгнуть брак |
| `/браки` | Список пар в чате |

Стоимость брака — `MARRIAGE_COST` ирисок (default: 200).

---

## 🔧 Middleware

**AdminMiddleware** — добавляет `is_admin: bool` в `data` для каждого сообщения. Хэндлеры модерации и настроек читают этот флаг.

**AntiFloodMiddleware** — скользящее окно: не более N сообщений за M секунд от одного пользователя (настраивается в `bot.py`).

---

## 📝 Логирование

Логи пишутся одновременно в файл `iris_bot.log` и в консоль. Уровень: `INFO`.

---

## 🚀 Деплой (пример systemd)

```ini
[Unit]
Description=Iris Bot 2.0
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/iris_bot
ExecStart=/opt/iris_bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
