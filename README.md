# Smart Caspian Transit (прототип хакатона)

Стек: **FastAPI** + **PostgreSQL** + **Next.js**. Все данные хранятся в PostgreSQL, загруженные файлы — в каталоге `backend/uploads` (или `SCT_UPLOADS_DIR`). Время на сервере и в интерфейсе — **МСК**.

## 1. Запуск

### PostgreSQL

Homebrew (PostgreSQL 18):

```bash
brew services start postgresql@18
psql -d postgres -c "CREATE ROLE sct LOGIN PASSWORD 'sct';" 2>/dev/null || true
psql -d postgres -c "CREATE DATABASE smart_caspian_transit OWNER sct;"
```

Или Docker: `docker compose up -d` (пользователь `sct`, пароль `sct`, БД `smart_caspian_transit`, порт `5432`).

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Проверка: http://127.0.0.1:8000/api/health → `"storage": "postgresql"`. Вход: `logist` / `demo123`. Все `/api/*`, кроме `health` и `auth`, требуют `Authorization: Bearer <token>`; без него — `401`.

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Адрес API задаётся `NEXT_PUBLIC_API_URL` (по умолчанию `http://127.0.0.1:8000/api`). OpenRouter не обязателен: без ключа все расчёты и готовые решения работают, кнопка «Уточнить ИИ» просто вернёт ошибку.

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | строка подключения PostgreSQL |
| `SCT_UPLOADS_DIR` | каталог загруженных документов |
| `SCT_DEMO_ANCHOR` | фиксированная «текущая» дата демо, например `2026-11-12T10:00:00` |
| `OPENROUTER_API_KEY` | необязательный ключ для формулировок ИИ (или файл `backend/.secrets/openrouter.key`) |

## 2. Демо-данные

Если в БД нет грузов, при старте backend создаёт 6 демо-грузов (SCT-1001 … SCT-1006). Даты демо сдвигаются к текущему моменту, поэтому сценарий воспроизводим в любой день.

**Сброс демо перед показом** (удаляет грузы, маршруты, документы, журнал, уведомления и телеметрию в выбранной БД и заново пишет демо-файлы):

```bash
cd backend && source .venv/bin/activate
python -m scripts.seed_demo_shipments
# или через API: POST /api/demo/reset
```

Синтетическая история коридора ж/д → паром (60 рейсов, `seed=42`, помечена `dataSource: "synthetic"`) лежит в `backend/app/data/corridor_history.py` и загружается вместе с демо. Это не статистика перевозчика.

### Отдельная тестовая БД (чтобы не трогать рабочую)

```bash
createdb -O sct smart_caspian_transit_test
cd backend && source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg2://sct:sct@localhost:5432/smart_caspian_transit_test
export SCT_UPLOADS_DIR=/tmp/sct-test-uploads
python -m scripts.seed_demo_shipments
uvicorn app.main:app --port 8001

cd ../frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001/api npx next dev -p 3001
```

## 3. Проверки

```bash
cd backend && .venv/bin/python -m unittest discover -s tests -v
cd frontend && npx tsc --noEmit --incremental false && npm run build
```

Тест транзакционности на PostgreSQL запускается только с отдельной одноразовой БД (её содержимое перезаписывается):

```bash
createdb -O sct smart_caspian_transit_unittest
SCT_TEST_DATABASE_URL=postgresql+psycopg2://sct:sct@localhost:5432/smart_caspian_transit_unittest \
  .venv/bin/python -m unittest discover -s tests -v
```

`npm run build` перезаписывает `frontend/.next`; если параллельно запущен `npm run dev`, перезапустите его после сборки.

## 4. Оперативные события

Единый вход для внешних источников и демо: `POST /api/events` (с авторизацией).

```bash
curl -X POST http://127.0.0.1:8000/api/events \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"eventId":"rzd-0001","eventType":"rail.eta","sourceName":"РЖД","sourceKind":"live",
       "observedAt":"2026-11-13T09:30:00+03:00","shipmentId":"SCT-1001",
       "stageId":"rt-SCT-1001-1","delayHours":52}'
```

| `eventType` | Поля |
|---|---|
| `rail.eta`, `rail.delay` | `shipmentId`, `stageId`, `delayHours` (0–240) или `estimatedArrivalAt` |
| `port.status`, `port.restriction`, `port.departure` | `portName`; `departureStatus`: `open` \| `departure_closed`; `restrictionStartsAt`, `restrictionEndsAt` (ISO); `restrictionNote` / `delayNote` / `message`; опционально `workload`, `windSpeed`, `shipDeparture` (только для ожидающих морских этапов, можно сузить `shipmentId`) |
| `carrier.stage_completed` | `shipmentId`, `stageId`; фактическое прибытие = `observedAt`, предыдущие этапы должны быть завершены |

Ответ: `applied` — событие учтено и прогноз пересчитан; `duplicate` — такой `eventId` уже был, ничего не меняется; `stale` — по этапу или порту уже есть более свежее наблюдение, событие записано в журнал, но не применено. Неизвестный груз, этап не того типа или уже завершённый, некорректные числа и даты → `400`. Сводка источников: `GET /api/infrastructure/status`.

**Демо: закрытие выхода из порта (тестовая БД / API на :8001):**

```bash
# закрыть Астрахань до первого доступного рейса
curl -X POST http://127.0.0.1:8001/api/events -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"eventId":"demo-astr-close-1","eventType":"port.restriction","sourceName":"Порт (симуляция)","sourceKind":"simulation",
       "observedAt":"2026-11-12T10:30:00+03:00","portName":"Астрахань","departureStatus":"departure_closed",
       "restrictionNote":"Порт закрыт для выхода судов","restrictionStartsAt":"2026-11-12T08:00:00+03:00","restrictionEndsAt":"2026-11-13T08:00:00+03:00"}'

# закрыть без даты открытия (ETA морского участка станет «не определён»)
curl -X POST http://127.0.0.1:8001/api/events -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"eventId":"demo-astr-close-open","eventType":"port.restriction","sourceName":"Порт (симуляция)","sourceKind":"simulation",
       "observedAt":"2026-11-12T10:35:00+03:00","portName":"Астрахань","departureStatus":"departure_closed",
       "restrictionNote":"Порт закрыт для выхода судов","restrictionStartsAt":"2026-11-12T08:00:00+03:00"}'

# открыть выход
curl -X POST http://127.0.0.1:8001/api/events -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"eventId":"demo-astr-open-1","eventType":"port.restriction","sourceName":"Порт (симуляция)","sourceKind":"simulation",
       "observedAt":"2026-11-12T11:00:00+03:00","portName":"Астрахань","departureStatus":"open","restrictionNote":"Выход судов открыт"}'
```

На карточке SCT-1001 есть кнопки симуляции порта (тот же API).

## 5. Как устроены расчёты

- **Прогноз**: эвристика стыковки «поезд → паром» (перевалка зависит от загрузки порта, ветер задерживает отход; если груз не успевает к парому — ожидание следующего рейса, кратное 24 ч) плюс история коридора. При трёх и более похожих рейсах (то же направление, запас на пересадку ±3,5 ч, ветер ±5 м/с, загрузка ±18 п.п.) задержка смешивается 55/45, иначе — только эвристика (`heuristic_fallback`, видно в интерфейсе). «Риск» — вероятность сорвать стыковку, «задержка» — часы сверх контрактного срока.
- **Бэктест** (`GET /api/analytics` → `historyBacktest`): обучение на ранних 70% рейсов, проверка на поздних 30%; для каждого рейса используются только рейсы, исход которых был известен к моменту прогноза. Сравнивается MAE модели и чистой эвристики. Демо на синтетике.
- **Объезд**: `GET /api/routes/options/{id}` строит варианты от текущей позиции или узла, до которого груз доедет по плану; пройденные и активный участки сохраняются. Все варианты сравниваются на одной базе — незавершённые участки от текущей позиции до пункта назначения (км, ₽ по тарифу маршрута, кг CO₂ по каждому участку, ч до прогнозного прибытия). `POST /api/routes/select` принимает `expectedVersion`; если состояние груза изменилось после сравнения — `409`, интерфейс предлагает обновить варианты.
- **CO₂**: масса (т) × расстояние (км) × коэффициент вида транспорта (кг CO₂ на т·км), сумма по участкам.
- **Предварительная проверка документов** (`POST /api/documents/preliminary-review`, `{ shipmentId, idempotencyKey }`): проверяет обязательные типы, файлы и поля, ставит «Готов к рассмотрению» или «Требуется исправление», пишет журнал и запись в локальный реестр с отпечатком комплекта. Повтор с тем же ключом не создаёт новую попытку. Если комплект изменился после решения, оно помечается устаревшим. Проверяющая сторона — имитация, не таможня; реестр — локальная цепочка в PostgreSQL, Solidity-контракт `contracts/CorridorPreclearance.sol` не развёрнут.
- **OpenRouter** (`POST /api/analytics/ai/{id}`): только переформулирует готовые шаги, цифры прогноза не меняет.

## 6. Сценарий показа (3–5 минут)

1. Сбросить демо, войти `logist` / `demo123`.
2. **Главная** → SCT-1001 «Астрахань → Энзели». В карточке: текущий этап (поезд Саратов → Астрахань, опоздание 30 ч), стыковка в Астрахани с запасом ~2 ч, ETA и риск, прогноз учитывает 3 похожих рейса.
3. **«Симулировать сообщение от ж/д»** (помечено «Демо»): РЖД сообщает опоздание 52 ч. Карточка показывает источник и время наблюдения, поезд опаздывает к парому на ~20 ч, ETA сдвигается (ожидание следующего парома), риск растёт до высокого, причина объяснена. Повторное нажатие — дубликат, прогноз не удваивается.
4. **«Сравнить варианты маршрута»**: ожидание следующего парома против объезда через Махачкалу (позже и дороже, но риск стыковки низкий). Показать единицы, базу сравнения и недоступные варианты с причиной. Выбрать объезд → после перезагрузки сохранены пройденный ж/д участок, история и новый план; ETA совпадает с предпросмотром.
5. **ИИ-аналитика** → SCT-1001: режим прогноза, число похожих рейсов, бэктест MAE (демо), по три готовых решения на проблему.
6. **Таможня** → SCT-1004: «Подать на предварительную проверку» → «Требуется исправление» (нет декларации, проблемный инвойс) → «Загрузить файл»/«Заменить файл» → подать снова → «Готов к рассмотрению», статус виден в карточке. Заменить любой файл — решение помечается устаревшим.
