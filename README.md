# Smart Caspian Transit (прототип хакатона)

Стек: **FastAPI** (backend) + **Next.js** (frontend). Данные — демонстрационные, файл `backend/data/store.json` (PostgreSQL подготовлен в `app/models.py`, но не подключён).

## Запуск backend

```bash
cd backend
source .venv/bin/activate   # если venv ещё нет: python3 -m venv .venv && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка: http://127.0.0.1:8000/api/health

### Авторизация (демо)

| Логин   | Пароль    | Роль        |
|---------|-----------|-------------|
| logist  | demo123   | Логист      |
| admin   | admin123  | Администратор |

Все API-запросы (кроме `/api/health` и `/api/auth/login`) требуют заголовок `Authorization: Bearer <token>`.
Сессии хранятся в `store.json`. Для отключения проверки на время отладки: `SCT_AUTH_DISABLED=1`.

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

Откройте http://localhost:3000

Переменная `NEXT_PUBLIC_API_URL` по умолчанию: `http://127.0.0.1:8000/api`
