# Yandex Telemost для Битрикс24

Приложение для интеграции Yandex Telemost с Битрикс24 - создавайте видеоконференции и трансляции прямо из Битрикс24.

## Возможности

- Создание видеоконференций и трансляций в Yandex Telemost
- Автоматическая интеграция с Битрикс24 через BX24 SDK
- Управление участниками и соорганизаторами
- Синхронизация с календарем Битрикс24
- История созданных конференций
- Быстрое копирование ссылок на конференции

## Технологии

- **Backend**: Python 3.11, Flask, SQLite
- **Frontend**: Vue 3 (Composition API), Tailwind CSS
- **Deployment**: Docker, Docker Compose, Nginx
- **Integration**: Bitrix24 REST API, Yandex Telemost API

## Быстрый старт

### Требования

- Docker и Docker Compose
- Nginx (для продакшен развертывания)
- SSL сертификат для домена

### Установка

1. **Клонируйте репозиторий**:
   ```bash
   git clone <repository-url>
   cd telemost-bitrix-app
   ```

2. **Настройте переменные окружения**:
   ```bash
   cp .env.example .env
   nano .env
   ```

   Заполните обязательные переменные:
   ```env
   # Flask
   SECRET_KEY=your-secret-key-here

   # Bitrix24
   BITRIX24_CLIENT_ID=your-bitrix-client-id
   BITRIX24_CLIENT_SECRET=your-bitrix-secret
   BITRIX24_WEBHOOK_URL=https://your-portal.bitrix24.ru/rest/1/webhook_token/

   # Yandex Telemost
   YANDEX_CLIENT_ID=your-yandex-client-id
   YANDEX_CLIENT_SECRET=your-yandex-secret
   YANDEX_REDIRECT_URI=https://it.company.ru/telemost-bitrix/auth/yandex/callback
   YANDEX_OAUTH_TOKEN=your-yandex-oauth-token
   ```

3. **Запустите приложение**:
   ```bash
   ./deploy.sh
   ```

   Или вручную:
   ```bash
   docker-compose up -d
   ```

4. **Настройте Nginx** (см. раздел "Nginx интеграция" ниже)

Приложение будет доступно по адресу: `https://it.company.ru/telemost-bitrix/`

## Разработка

### Локальная разработка без Docker

1. **Установите Python зависимости**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   venv\Scripts\activate  # Windows

   pip install -r requirements.txt
   ```

2. **Установите Node.js зависимости для Tailwind CSS**:
   ```bash
   npm install
   ```

3. **Запустите разработческий режим**:
   ```bash
   # В одном терминале - Flask сервер
   python run.py

   # В другом терминале - автоматическая сборка CSS
   npm run watch:css
   ```

4. **Соберите CSS для продакшена**:
   ```bash
   npm run build:css
   ```

Приложение будет доступно по адресу: `http://localhost:5000`

## Nginx интеграция

Приложение разработано для работы за Nginx reverse proxy с BASE_PATH поддержкой.

### Конфигурация Nginx

Добавьте в ваш nginx.conf:

```nginx
# Upstream
upstream backend_telemost_bitrix {
    server localhost:5000;
}

# Server block
server {
    listen 443 ssl http2;
    server_name it.company.ru;

    # SSL сертификаты
    ssl_certificate /etc/nginx/ssl/company.ru.pem;
    ssl_certificate_key /etc/nginx/ssl/company.ru-key.pem;

    # Telemost-Bitrix приложение
    location /telemost-bitrix/ {
        rewrite ^/telemost-bitrix/(.*) /$1 break;
        proxy_pass http://backend_telemost_bitrix/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Script-Name /telemost-bitrix;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        client_max_body_size 10M;
    }

    # Health check
    location /telemost-bitrix/health {
        rewrite ^/telemost-bitrix/health /health break;
        proxy_pass http://backend_telemost_bitrix;
        access_log off;
    }
}
```

Полная конфигурация доступна в файле `nginx-integration.conf`.

### Перезагрузка Nginx

```bash
sudo nginx -t
sudo nginx -s reload
```

## Структура проекта

```
telemost-bitrix-app/
├── app.py                      # Основное Flask приложение
├── config.py                   # Конфигурация Flask
├── database.py                 # Работа с SQLite базой данных
├── run.py                      # Точка входа для запуска
├── requirements.txt            # Python зависимости
├── package.json                # Node.js зависимости (Tailwind CSS)
├── tailwind.config.js          # Конфигурация Tailwind CSS
│
├── Dockerfile                  # Docker образ приложения
├── docker-compose.yml          # Docker Compose конфигурация
├── .dockerignore               # Исключения для Docker
├── deploy.sh                   # Скрипт автоматического развертывания
│
├── nginx.conf                  # Базовая конфигурация Nginx
├── nginx-integration.conf      # Конфигурация для интеграции в существующий Nginx
├── DOCKER_DEPLOY.md            # Подробная инструкция по развертыванию
│
├── .env.example                # Пример переменных окружения
├── .env                        # Переменные окружения (не в git)
│
├── templates/
│   └── index.html              # Основная страница (Vue 3 + Tailwind)
│
├── static/
│   └── css/
│       └── style.css           # Собранный CSS (Tailwind)
│
├── data/                       # SQLite база данных (Docker volume)
│   └── telemost_conferences.db
│
└── logs/                       # Логи приложения (Docker volume)
```

## API Endpoints

### Основные
- `GET /` - Основная страница приложения
- `GET /health` - Health check endpoint для мониторинга

### Конференции
- `GET /api/conferences` - Получить список конференций текущего пользователя
- `POST /api/conferences` - Создать новую конференцию
- `PUT /api/conferences/<id>` - Обновить конференцию
- `DELETE /api/conferences/<id>` - Удалить конференцию
- `GET /api/conferences/<id>` - Получить конференцию по ID

### Пользователи (для демонстрации)
- `GET /api/bitrix/users` - Получить список пользователей Битрикс24
- `GET /api/current-user` - Получить данные текущего пользователя

## Аутентификация и безопасность

### Идентификация пользователей

Приложение использует Bitrix24 JS SDK (BX24) для идентификации пользователей:

```javascript
// Получение текущего пользователя
BX24.callMethod('user.current', {}, (result) => {
    const user = result.data();
    // user.ID, user.NAME, user.LAST_NAME, user.EMAIL
});
```

Пользователи идентифицируются автоматически при каждом запросе через BX24 SDK, без использования серверных сессий.

### Безопасность

- **HTTPS обязателен**: Приложение работает только через HTTPS
- **SESSION_COOKIE_SAMESITE='None'**: Для работы в iframe Битрикс24
- **SESSION_COOKIE_SECURE=True**: Защита cookie через HTTPS
- **SECRET_KEY**: Генерируйте криптографически стойкий ключ
- **OAuth токены**: Храните в защищенных переменных окружения
- **Не root пользователь**: Docker контейнер запускается от пользователя appuser

### Генерация SECRET_KEY

```python
import secrets
print(secrets.token_hex(32))
```

## База данных

### SQLite структура

**Таблица conferences:**
```sql
CREATE TABLE conferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('conference', 'broadcast')),
    description TEXT,
    start_date DATE,
    start_time TIME,
    cohosts TEXT,
    create_calendar_event BOOLEAN DEFAULT 0,
    invite_users BOOLEAN DEFAULT 0,
    live_stream_title TEXT,
    live_stream_description TEXT,
    owner_id TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    link TEXT UNIQUE,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Бэкап базы данных

```bash
# Создать бэкап
docker-compose exec app sqlite3 /app/data/telemost_conferences.db .dump > backup.sql

# Восстановить из бэкапа
cat backup.sql | docker-compose exec -T app sqlite3 /app/data/telemost_conferences.db
```

## Docker команды

```bash
# Запуск приложения
docker-compose up -d

# Просмотр логов
docker-compose logs -f app

# Перезапуск
docker-compose restart

# Остановка
docker-compose stop

# Полное удаление (с удалением volumes)
docker-compose down -v

# Пересборка образа
docker-compose build --no-cache

# Выполнение команды внутри контейнера
docker-compose exec app bash
```

## Мониторинг

### Health Check

```bash
# Проверка состояния приложения
curl http://localhost:5000/health

# Ответ:
{
  "status": "healthy",
  "service": "telemost-bitrix-app",
  "base_path": "/telemost-bitrix"
}
```

### Логи

```bash
# Просмотр логов Flask приложения
docker-compose logs -f app

# Логи Nginx
tail -f /var/log/nginx/it.company.ru-access.log
tail -f /var/log/nginx/it.company.ru-error.log
```

## Переменные окружения

| Переменная | Описание | Пример |
|-----------|----------|--------|
| `FLASK_ENV` | Режим работы Flask | `production` |
| `SECRET_KEY` | Секретный ключ Flask | `your-secret-key` |
| `DATABASE_PATH` | Путь к SQLite БД | `/app/data/telemost_conferences.db` |
| `BASE_PATH` | Базовый путь для reverse proxy | `/telemost-bitrix` |
| `SCRIPT_NAME` | Префикс для URL (синоним BASE_PATH) | `/telemost-bitrix` |
| `BITRIX24_CLIENT_ID` | ID приложения Битрикс24 | `local.xxx` |
| `BITRIX24_CLIENT_SECRET` | Секрет приложения Битрикс24 | `xxx` |
| `BITRIX24_WEBHOOK_URL` | Webhook URL для API Битрикс24 | `https://portal.bitrix24.ru/rest/1/xxx/` |
| `YANDEX_CLIENT_ID` | ID приложения Yandex | `xxx` |
| `YANDEX_CLIENT_SECRET` | Секрет приложения Yandex | `xxx` |
| `YANDEX_REDIRECT_URI` | Redirect URI для OAuth Yandex | `https://it.company.ru/telemost-bitrix/auth/yandex/callback` |
| `YANDEX_OAUTH_TOKEN` | OAuth токен Yandex Telemost | `y0_xxx` |
| `LOGGING_LEVEL` | Уровень логирования | `INFO` |

## Интеграция с Битрикс24

### Установка приложения в Битрикс24

1. Перейдите в Битрикс24: **Приложения** → **Разработчикам** → **Создать приложение**
2. Выберите тип: **Локальное приложение**
3. Укажите URL приложения: `https://it.company.ru/telemost-bitrix/`
4. Настройте права доступа:
   - `user` - чтение информации о пользователях
   - `calendar` - работа с календарем
5. Сохраните `CLIENT_ID` и `CLIENT_SECRET` в `.env`

### Настройка Yandex Telemost

1. Перейдите в [Yandex OAuth](https://oauth.yandex.ru/)
2. Создайте новое приложение
3. Укажите Callback URL: `https://it.company.ru/telemost-bitrix/auth/yandex/callback`
4. Получите OAuth токен с правами на Telemost API
5. Сохраните `CLIENT_ID`, `CLIENT_SECRET` и `OAUTH_TOKEN` в `.env`

## Устранение неполадок

### Приложение не запускается

```bash
# Проверьте логи
docker-compose logs app

# Проверьте переменные окружения
docker-compose exec app env | grep -E 'BITRIX|YANDEX|SECRET'

# Проверьте права на директории
ls -la data/ logs/
```

### Ошибки при работе в iframe

- Убедитесь, что используется HTTPS
- Проверьте настройки cookie в `config.py`:
  ```python
  SESSION_COOKIE_SAMESITE = 'None'
  SESSION_COOKIE_SECURE = True
  ```

### База данных не создается

```bash
# Проверьте права на директорию data/
chmod 777 data/

# Пересоздайте контейнер
docker-compose down
docker-compose up -d
```

### Nginx возвращает 502 Bad Gateway

```bash
# Проверьте, что приложение запущено
curl http://localhost:5000/health

# Проверьте логи Nginx
tail -f /var/log/nginx/error.log

# Проверьте upstream в nginx.conf
upstream backend_telemost_bitrix {
    server localhost:5000;
}
```

## Производительность

- **Gunicorn workers**: 4 worker processes
- **Gunicorn threads**: 2 threads per worker
- **Request timeout**: 60 seconds
- **Max body size**: 10MB
- **Database**: SQLite с индексами на owner_id, type, status, created_at

## Обновление приложения

```bash
# Получите последние изменения
git pull

# Пересоберите образ
docker-compose build

# Перезапустите контейнеры
docker-compose up -d

# Проверьте здоровье
curl http://localhost:5000/health
```

## Лицензия

MIT License

## Поддержка

Для вопросов и поддержки создайте issue в репозитории.
