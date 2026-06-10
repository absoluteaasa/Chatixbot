# 🤖 Chatix 2.0

Многофункциональный Telegram-бот для управления чатами, виртуальной экономики и развлечений.

**Username:** @chatixcm_bot

---

## 📁 Архитектура проекта

```
chatix1.8/
│
├── bot.py                  # Точка входа: инициализация Bot, Dispatcher, роутеры
├── config.py               # Настройки через pydantic-settings (.env)
├── requirements.txt
├── .env.example
│
├── database/
│   ├── db.py               # SQLAlchemy модели
│   └── repo.py             # CRUD-операции
│
├── handlers/
│   ├── moderation.py       # бан, кик, мут, варн, автофильтр
│   ├── economy.py          # баланс, бонус, перевод, казино, кости, ставка
│   ├── reputation.py       # карма, профиль, топ
│   ├── marriage.py         # брак, развод, браки
│   ├── profile.py          # профиль, кто я, кто ты
│   ├── roles.py            # роли, повысить, понизить
│   ├── shop.py             # магазин, купить
│   ├── spam.py             # спамбаза
│   ├── banlist.py          # бан-лист
│   ├── top.py              # топ активности
│   ├── chat_manage.py      # управление чатом, заметки, дуэль
│   └── misc.py             # старт, помощь, правила, приветствие
│
├── middlewares/
│   ├── admin.py            # AdminMiddleware
│   └── antiflood.py        # AntiFloodMiddleware
│
└── utils/
    └── helpers.py
```

---

## ⚙️ Установка

```bash
# 1. Распакуй архив
cd chatix1.8

# 2. Создай виртуальное окружение
python -m venv venv
source venv/bin/activate

# 3. Установи зависимости
pip install -r requirements.txt

# 4. Создай .env файл
cp .env.example .env
# Вставь BOT_TOKEN и другие параметры

# 5. Запусти
python bot.py
```

---

## 📦 БД: SQLite vs PostgreSQL

```
# SQLite (дефолт)
DATABASE_URL=sqlite+aiosqlite:///chatix.db

# PostgreSQL (продакшн)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/chatix
```

---

## 🔧 Команды

Все команды работают с префиксами `!`, `/`, `.` или без префикса.

### 🛡️ Модерация
`бан`, `кик`, `мут [10m/2h/1d]`, `анмут`, `варн`, `разбан`

### 💰 Экономика
`баланс`, `бонус`, `перевод [сумма]`, `казино [ставка]`, `кости [ставка]`, `ставка [сумма]`

### 💑 Браки
`брак`, `развод`, `браки`

### ⭐ Репутация
`+` / `-` в ответ на сообщение, `профиль`, `топ`

### 🎭 РП
`обнять`, `поцеловать`, `ударить`, `погладить`, `укусить`, `подмигнуть`

### ⚙️ Управление
`повысить`, `понизить`, `передать`, `закреп`, `открепить`, `очистить`

---

## 📝 Логирование

Логи пишутся в файл `chatix.log` и в консоль. Уровень: `INFO`.

---

## 🚀 Деплой (systemd)

```ini
[Unit]
Description=Chatix 2.0
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/chatix
ExecStart=/opt/chatix/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
