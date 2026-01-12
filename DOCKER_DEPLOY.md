# Развертывание Telemost-Bitrix через Docker

## Предварительные требования

- Docker (версия 20.10+)
- Docker Compose (версия 2.0+)
- Nginx на сервере (для reverse proxy)
- SSL сертификат для домена it.company.ru

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd telemost-bitrix-app
```

### 2. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
nano .env
```

Обязательно заполните:
- `SECRET_KEY` - случайная строка для Flask
- `BITRIX24_CLIENT_ID` и `BITRIX24_CLIENT_SECRET`
- `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET`, `YANDEX_OAUTH_TOKEN`
- `YANDEX_REDIRECT_URI=https://it.company.ru/telemost-bitrix/auth/yandex/callback`

### 3. Создание директорий для данных

```bash
mkdir -p data logs
chmod 777 data logs
```

### 4. Сборка и запуск контейнера

```bash
# Сборка образа
docker-compose build

# Запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f app
```

### 5. Проверка работы

```bash
# Проверка здоровья приложения
curl http://localhost:5000/health

# Должен вернуть:
# {"status":"healthy","service":"telemost-bitrix-app","base_path":"/telemost-bitrix"}
```

## Настройка Nginx

### Вариант 1: Добавление в существующий конфиг

Добавьте блок `location /telemost-bitrix/` из файла `nginx.conf` в ваш существующий конфиг для `it.company.ru`:

```bash
sudo nano /etc/nginx/sites-available/it.company.ru
```

Добавьте:

```nginx
location /telemost-bitrix/ {
    proxy_pass http://localhost:5000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /telemost-bitrix;

    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    client_max_body_size 10M;
}
```

### Вариант 2: Использование готового конфига

```bash
# Скопируйте конфиг
sudo cp nginx.conf /etc/nginx/sites-available/it.company.ru

# Активируйте и перезагрузите nginx
sudo ln -s /etc/nginx/sites-available/it.company.ru /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Управление приложением

### Остановка

```bash
docker-compose stop
```

### Перезапуск

```bash
docker-compose restart
```

### Обновление

```bash
# Получить последние изменения
git pull

# Пересобрать и перезапустить
docker-compose down
docker-compose build
docker-compose up -d
```

### Просмотр логов

```bash
# Логи контейнера
docker-compose logs -f app

# Логи приложения (в volume)
tail -f logs/telemost_bitrix_app.log
```

### Очистка

```bash
# Остановить и удалить контейнеры
docker-compose down

# Также удалить volumes (БД и логи будут удалены!)
docker-compose down -v
```

## Проверка доступности

После развертывания приложение должно быть доступно по адресу:

```
https://it.company.ru/telemost-bitrix/
```

### Проверка endpoints:

- Health check: `https://it.company.ru/telemost-bitrix/health`
- Главная страница: `https://it.company.ru/telemost-bitrix/`
- API конференций: `https://it.company.ru/telemost-bitrix/api/conferences`

## Мониторинг

### Проверка статуса контейнера

```bash
docker-compose ps
```

### Использование ресурсов

```bash
docker stats telemost-bitrix-app
```

### Healthcheck

Docker автоматически проверяет здоровье контейнера каждые 30 секунд через endpoint `/health`.

Статус можно посмотреть:

```bash
docker inspect --format='{{.State.Health.Status}}' telemost-bitrix-app
```

## Устранение проблем

### Контейнер не запускается

```bash
# Проверьте логи
docker-compose logs app

# Проверьте переменные окружения
docker-compose config
```

### Приложение недоступно через nginx

```bash
# Проверьте nginx
sudo nginx -t
sudo systemctl status nginx

# Проверьте что приложение слушает порт
curl http://localhost:5000/health

# Проверьте логи nginx
sudo tail -f /var/log/nginx/error.log
```

### База данных повреждена

```bash
# Остановите контейнер
docker-compose stop

# Удалите БД
rm data/telemost_conferences.db

# Запустите снова (БД пересоздастся автоматически)
docker-compose start
```

## Backup

### Создание backup БД

```bash
# Создайте директорию для backup
mkdir -p backups

# Скопируйте БД
docker-compose exec app cp /app/data/telemost_conferences.db /app/backups/backup_$(date +%Y%m%d_%H%M%S).db
```

### Восстановление из backup

```bash
# Остановите приложение
docker-compose stop

# Восстановите БД
cp backups/backup_20240101_120000.db data/telemost_conferences.db

# Запустите приложение
docker-compose start
```

## Безопасность

1. **Никогда не коммитьте `.env` файл в git**
2. **Используйте сильный `SECRET_KEY`**
3. **Регулярно обновляйте зависимости**: `pip list --outdated`
4. **Настройте firewall** чтобы порт 5000 был доступен только локально
5. **Используйте HTTPS** (SSL сертификат в nginx)
6. **Ограничьте доступ к логам и БД**

## Production рекомендации

1. **Используйте внешнюю БД** (PostgreSQL) вместо SQLite для лучшей производительности
2. **Настройте логирование** в centralized logging (ELK, Graylog)
3. **Добавьте мониторинг** (Prometheus + Grafana)
4. **Настройте автоматические backup**
5. **Используйте docker secrets** для чувствительных данных
6. **Ограничьте ресурсы контейнера** (CPU, RAM limits в docker-compose.yml)
