# Smart Caspian Transit (прототип хакатона)

Стек: **FastAPI** + **PostgreSQL** + **Next.js**.

Данные хранятся в **PostgreSQL** (не в JSON-файлах). При первом запуске создаются таблицы, учётки и справочник портов. **Демо-грузов нет** — добавляйте их в разделе «Грузы».

## 1. PostgreSQL

**Вариант A — Homebrew (у вас PostgreSQL 18):**

```bash
brew services start postgresql@18
```

База и пользователь для проекта (один раз):

```bash
/opt/homebrew/opt/postgresql@18/bin/psql -d postgres -c "CREATE ROLE sct LOGIN PASSWORD 'sct';" 2>/dev/null || true
/opt/homebrew/opt/postgresql@18/bin/psql -d postgres -c "CREATE DATABASE smart_caspian_transit OWNER sct;"
```

**Вариант B — Docker:**

```bash
docker compose up -d
```

Параметры: пользователь `sct`, пароль `sct`, БД `smart_caspian_transit`, порт `5432`.

Переменная (опционально):

```bash
export DATABASE_URL=postgresql+psycopg2://sct:sct@localhost:5432/smart_caspian_transit
```

## 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка: http://127.0.0.1:8000/api/health → `"storage": "postgresql"`

### Авторизация (начальные пользователи в БД)

| Логин  | Пароль    |
|--------|-----------|
| logist | demo123   |
| admin  | admin123  |

Сессии в таблице `auth_sessions`. Отладка без проверки: `SCT_AUTH_DISABLED=1`.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:3000

## Миграция со старого JSON

Если остался `backend/data/store.json` — его можно удалить, приложение его больше не использует.

При первом запуске с новой схемой таблицы создаются автоматически (`create_all`). Если в БД **нет грузов**, при старте backend подставляются **6 тестовых** (SCT-1001 … SCT-1006).

Перезагрузить демо-грузы вручную:

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_demo_shipments
```
