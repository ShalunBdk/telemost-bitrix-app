# Гайд по интеграции приложений в Битрикс24

> Этот гайд основан на реальном проекте интеграции Yandex Telemost с Битрикс24. Используйте его как справочник для создания новых приложений в Claude Code.

## Оглавление

1. [Общая архитектура](#1-общая-архитектура)
2. [Структура проекта](#2-структура-проекта)
3. [OAuth авторизация с Битрикс24](#3-oauth-авторизация-с-битрикс24)
4. [Установка приложения](#4-установка-приложения)
5. [Хранение данных пользователей (личный кабинет)](#5-хранение-данных-пользователей-личный-кабинет)
6. [API структура](#6-api-структура)
7. [Фронтенд интеграция](#7-фронтенд-интеграция)
8. [Конфигурация](#8-конфигурация)
9. [Развертывание](#9-развертывание)
10. [Чеклист интеграции](#10-чеклист-интеграции)

---

## 1. Общая архитектура

### Как работает приложение в Битрикс24

```
┌─────────────────────────────────────────────────────────────────┐
│                        Битрикс24 Portal                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     iframe                                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │              Ваше приложение                        │  │  │
│  │  │                                                     │  │  │
│  │  │  ┌─────────────┐    ┌──────────────────────────┐   │  │  │
│  │  │  │  BX24 SDK   │────│  Ваш Backend (Flask)     │   │  │  │
│  │  │  │ JavaScript  │    │  + Database (SQLite)     │   │  │  │
│  │  │  └─────────────┘    └──────────────────────────┘   │  │  │
│  │  │                              │                      │  │  │
│  │  │                              ▼                      │  │  │
│  │  │                     ┌──────────────────┐            │  │  │
│  │  │                     │  External APIs   │            │  │  │
│  │  │                     │  (Yandex, etc.)  │            │  │  │
│  │  │                     └──────────────────┘            │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые принципы

1. **Приложение работает в iframe** - Битрикс24 загружает ваше приложение внутри iframe
2. **BX24 SDK** - JavaScript библиотека для взаимодействия с Битрикс24 API
3. **OAuth токены** - Битрикс24 автоматически передает токены при загрузке
4. **Личный кабинет** - данные привязываются к `user_id` из Битрикс24

---

## 2. Структура проекта

### Минимальная структура для интеграции

```
my-bitrix-app/
├── app.py                    # Flask приложение (основной файл)
├── config.py                 # Конфигурация (env переменные)
├── database.py               # Работа с БД
├── requirements.txt          # Python зависимости
├── .env                      # Переменные окружения
│
├── models/
│   └── bitrix24.py          # Битрикс24 API клиент
│
├── templates/
│   ├── index.html           # Главная страница (Vue/React)
│   └── install.html         # Страница установки
│
├── static/
│   ├── js/
│   └── css/
│
└── docker-compose.yml       # Docker конфигурация
```

### requirements.txt

```
Flask>=2.3.0
gunicorn>=21.0.0
python-dotenv>=1.0.0
requests>=2.31.0
PyJWT>=2.8.0
```

---

## 3. OAuth авторизация с Битрикс24

### 3.1 Получение учетных данных

1. Зайдите в [Битрикс24 Маркетплейс](https://partners.bitrix24.ru/)
2. Создайте приложение и получите:
   - `BITRIX24_CLIENT_ID`
   - `BITRIX24_CLIENT_SECRET`

### 3.2 OAuth Flow

```python
# models/bitrix24.py

import requests
from flask import current_app, session

class Bitrix24API:
    OAUTH_URL = 'https://oauth.bitrix.info/oauth/token/'

    @staticmethod
    def get_access_token(auth_code):
        """Обмен authorization code на токены"""
        response = requests.get(Bitrix24API.OAUTH_URL, params={
            'grant_type': 'authorization_code',
            'client_id': current_app.config['BITRIX24_CLIENT_ID'],
            'client_secret': current_app.config['BITRIX24_CLIENT_SECRET'],
            'code': auth_code
        })
        return response.json()

    @staticmethod
    def refresh_tokens(refresh_token, domain):
        """Обновление токенов"""
        response = requests.get(Bitrix24API.OAUTH_URL, params={
            'grant_type': 'refresh_token',
            'client_id': current_app.config['BITRIX24_CLIENT_ID'],
            'client_secret': current_app.config['BITRIX24_CLIENT_SECRET'],
            'refresh_token': refresh_token
        })
        return response.json()

    @staticmethod
    def call_method(domain, access_token, method, params=None):
        """Вызов REST API метода Битрикс24"""
        url = f'https://{domain}/rest/{method}.json'
        response = requests.post(url, data={
            'auth': access_token,
            **(params or {})
        })
        return response.json()

    @staticmethod
    def get_current_user(domain, access_token):
        """Получение информации о текущем пользователе"""
        return Bitrix24API.call_method(domain, access_token, 'user.current')
```

### 3.3 Сохранение токенов в сессии

```python
# app.py

from flask import Flask, session, request

app = Flask(__name__)

# ВАЖНО: Настройки cookies для работы в iframe
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Обязательно для iframe
app.config['SESSION_COOKIE_SECURE'] = True       # Требует HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True

@app.route('/auth/bitrix24')
def auth_bitrix24():
    """OAuth callback от Битрикс24"""
    code = request.args.get('code')
    domain = request.args.get('domain')

    # Обмен кода на токены
    tokens = Bitrix24API.get_access_token(code)

    # Сохранение в сессии
    session['bitrix_access_token'] = tokens['access_token']
    session['bitrix_refresh_token'] = tokens['refresh_token']
    session['bitrix_domain'] = domain
    session['bitrix_member_id'] = tokens.get('member_id')
    session.permanent = True

    return redirect(url_for('index'))
```

---

## 4. Установка приложения

### 4.1 Endpoint установки

Битрикс24 отправляет POST запрос на URL установки при добавлении приложения.

```python
# app.py

@app.route('/install', methods=['GET', 'POST'])
def install():
    """Обработка установки приложения в Битрикс24"""

    # Объединяем параметры из GET, POST и JSON
    params = {}
    params.update(request.args.to_dict())
    params.update(request.form.to_dict())
    if request.is_json:
        params.update(request.get_json(silent=True) or {})

    event = params.get('event')

    # Способ 1: Событие ONAPPINSTALL (через маркетплейс)
    if event == 'ONAPPINSTALL' and 'auth' in params:
        auth = params['auth']
        domain = auth.get('domain')
        access_token = auth.get('access_token')
        refresh_token = auth.get('refresh_token')
        member_id = auth.get('member_id')

    # Способ 2: DEFAULT placement (стандартная установка)
    else:
        domain = params.get('DOMAIN')
        access_token = params.get('AUTH_ID')
        refresh_token = params.get('REFRESH_ID')
        member_id = params.get('member_id')

    if not domain or not access_token:
        return "Ошибка установки: отсутствуют параметры авторизации", 400

    # Сохраняем токены
    session['bitrix_access_token'] = access_token
    session['bitrix_refresh_token'] = refresh_token
    session['bitrix_domain'] = domain
    session['bitrix_member_id'] = member_id
    session.permanent = True

    # Возвращаем HTML с завершением установки
    return render_install_finish_page(domain)


def render_install_finish_page(domain):
    """HTML страница завершения установки"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="//api.bitrix24.com/api/v1/"></script>
    </head>
    <body>
        <script>
            BX24.init(function() {{
                BX24.installFinish();  // ВАЖНО: Завершает установку
            }});
        </script>
        <div style="text-align: center; padding: 50px;">
            <h2>Приложение успешно установлено!</h2>
            <p>Домен: {domain}</p>
        </div>
    </body>
    </html>
    '''
```

### 4.2 Шаблон install.html

```html
<!-- templates/install.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Установка приложения</title>
    <script src="//api.bitrix24.com/api/v1/"></script>
</head>
<body>
    <script>
        BX24.init(function() {
            // Завершаем установку
            BX24.installFinish();
        });
    </script>

    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
        <h2>{{ app_name }} успешно установлено!</h2>
        {% if domain %}
        <p>Домен: {{ domain }}</p>
        {% endif %}
        <p>Вы можете закрыть это окно.</p>
    </div>
</body>
</html>
```

---

## 5. Хранение данных пользователей (личный кабинет)

### 5.1 Получение user_id

Каждый пользователь Битрикс24 имеет уникальный `user_id`. Используйте его для создания личного кабинета.

**Способ 1: Через BX24 SDK (фронтенд)**

```javascript
// В index.html
BX24.init(function() {
    BX24.callMethod('user.current', {}, function(result) {
        const user = result.data();
        console.log('User ID:', user.ID);
        console.log('User Name:', user.NAME + ' ' + user.LAST_NAME);
        console.log('User Email:', user.EMAIL);

        // Передаем на backend
        sendUserToBackend(user);
    });
});
```

**Способ 2: Через параметры запроса (backend)**

```python
# app.py

def get_user_from_request():
    """Извлечение информации о пользователе из запроса"""
    # Битрикс24 может передавать user_id в параметрах
    user_id = request.args.get('user_id') or request.form.get('user_id')

    # Или можно получить через API
    if not user_id and session.get('bitrix_access_token'):
        domain = session.get('bitrix_domain')
        token = session.get('bitrix_access_token')
        result = Bitrix24API.get_current_user(domain, token)
        if result.get('result'):
            user_id = result['result'].get('ID')

    return {
        'id': user_id,
        'name': request.args.get('user_name', 'Unknown')
    }
```

### 5.2 Схема базы данных

```python
# database.py

import sqlite3
from datetime import datetime

DATABASE_PATH = 'data/app.db'

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Основная таблица с данными пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id TEXT NOT NULL,           -- ID пользователя в Битрикс24
            owner_name TEXT,                  -- ФИО пользователя
            domain TEXT,                      -- Домен портала Битрикс24

            -- Ваши поля данных
            item_name TEXT NOT NULL,
            item_data TEXT,                   -- JSON для сложных данных

            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Индекс для быстрого поиска по пользователю
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_owner_id
        ON user_data(owner_id)
    ''')

    # Таблица токенов (опционально, для хранения вне сессии)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bitrix24_tokens (
            domain TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER,
            member_id TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def get_user_items(owner_id):
    """Получение данных конкретного пользователя"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM user_data
        WHERE owner_id = ?
        ORDER BY created_at DESC
    ''', (owner_id,))

    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items


def save_user_item(owner_id, owner_name, domain, item_name, item_data=None):
    """Сохранение данных пользователя"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO user_data (owner_id, owner_name, domain, item_name, item_data)
        VALUES (?, ?, ?, ?, ?)
    ''', (owner_id, owner_name, domain, item_name, item_data))

    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id
```

### 5.3 API для личного кабинета

```python
# app.py

from flask import jsonify

@app.route('/api/items', methods=['GET'])
def get_items():
    """Получение данных текущего пользователя"""
    user = get_user_from_request()
    if not user['id']:
        return jsonify({'error': 'User not authenticated'}), 401

    items = get_user_items(user['id'])
    return jsonify(items)


@app.route('/api/items', methods=['POST'])
def create_item():
    """Создание записи для текущего пользователя"""
    user = get_user_from_request()
    if not user['id']:
        return jsonify({'error': 'User not authenticated'}), 401

    data = request.get_json()

    item_id = save_user_item(
        owner_id=user['id'],
        owner_name=user['name'],
        domain=session.get('bitrix_domain'),
        item_name=data.get('name'),
        item_data=json.dumps(data.get('data', {}))
    )

    return jsonify({'id': item_id, 'success': True})


@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Удаление записи (только своей)"""
    user = get_user_from_request()
    if not user['id']:
        return jsonify({'error': 'User not authenticated'}), 401

    # Проверяем, что запись принадлежит пользователю
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        DELETE FROM user_data
        WHERE id = ? AND owner_id = ?
    ''', (item_id, user['id']))

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Item not found or access denied'}), 404
```

---

## 6. API структура

### 6.1 Основные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET/POST | Главная страница приложения |
| `/install` | GET/POST | Установка приложения |
| `/auth/bitrix24` | GET | OAuth callback |
| `/api/items` | GET | Получить данные пользователя |
| `/api/items` | POST | Создать запись |
| `/api/items/<id>` | PUT | Обновить запись |
| `/api/items/<id>` | DELETE | Удалить запись |
| `/api/users/current` | GET | Информация о пользователе |
| `/health` | GET | Health check |

### 6.2 Полный пример app.py

```python
# app.py

from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from datetime import timedelta
import os

from config import Config
from database import init_db, get_user_items, save_user_item
from models.bitrix24 import Bitrix24API

app = Flask(__name__)
app.config.from_object(Config)

# КРИТИЧЕСКИ ВАЖНО для работы в iframe Битрикс24
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Инициализация БД при старте
with app.app_context():
    init_db()


def get_user_from_request():
    """Извлечение пользователя из запроса или сессии"""
    user_id = request.args.get('user_id') or request.form.get('user_id')
    user_name = request.args.get('user_name') or request.form.get('user_name')

    # Пробуем получить из JSON
    if request.is_json:
        data = request.get_json(silent=True) or {}
        user_id = user_id or data.get('user_id')
        user_name = user_name or data.get('user_name')

    return {'id': user_id, 'name': user_name or 'Unknown'}


@app.route('/', methods=['GET', 'POST'])
def index():
    """Главная страница приложения"""
    # Обработка параметров от Битрикс24
    params = {**request.args.to_dict(), **request.form.to_dict()}

    # Сохраняем токены если переданы
    if params.get('AUTH_ID'):
        session['bitrix_access_token'] = params['AUTH_ID']
        session['bitrix_refresh_token'] = params.get('REFRESH_ID')
        session['bitrix_domain'] = params.get('DOMAIN')
        session.permanent = True

    # Проверяем авторизацию
    is_authenticated = bool(session.get('bitrix_access_token'))

    return render_template('index.html',
        bitrix_auth=is_authenticated,
        domain=session.get('bitrix_domain', '')
    )


@app.route('/install', methods=['GET', 'POST'])
def install():
    """Установка приложения"""
    params = {**request.args.to_dict(), **request.form.to_dict()}
    if request.is_json:
        params.update(request.get_json(silent=True) or {})

    event = params.get('event')

    # ONAPPINSTALL событие
    if event == 'ONAPPINSTALL' and 'auth' in params:
        auth = params['auth']
        domain = auth.get('domain')
        access_token = auth.get('access_token')
        refresh_token = auth.get('refresh_token')
        member_id = auth.get('member_id')
    else:
        # Стандартная установка
        domain = params.get('DOMAIN')
        access_token = params.get('AUTH_ID')
        refresh_token = params.get('REFRESH_ID')
        member_id = params.get('member_id')

    if domain and access_token:
        session['bitrix_access_token'] = access_token
        session['bitrix_refresh_token'] = refresh_token
        session['bitrix_domain'] = domain
        session['bitrix_member_id'] = member_id
        session.permanent = True

    return render_template('install.html', domain=domain)


@app.route('/api/items', methods=['GET'])
def api_get_items():
    """Получение данных пользователя"""
    user = get_user_from_request()
    if not user['id']:
        return jsonify({'error': 'User ID required'}), 400

    items = get_user_items(user['id'])
    return jsonify(items)


@app.route('/api/items', methods=['POST'])
def api_create_item():
    """Создание записи"""
    user = get_user_from_request()
    if not user['id']:
        return jsonify({'error': 'User ID required'}), 400

    data = request.get_json() or {}

    item_id = save_user_item(
        owner_id=user['id'],
        owner_name=user['name'],
        domain=session.get('bitrix_domain'),
        item_name=data.get('name', 'Untitled'),
        item_data=json.dumps(data)
    )

    return jsonify({'id': item_id, 'success': True}), 201


@app.route('/api/users/current', methods=['GET'])
def api_current_user():
    """Информация о текущем пользователе"""
    user = get_user_from_request()
    return jsonify(user)


@app.route('/health')
def health():
    """Health check для мониторинга"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 7. Фронтенд интеграция

### 7.1 Базовый шаблон index.html

```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Мое приложение</title>

    <!-- ВАЖНО: BX24 SDK должен загружаться первым -->
    <script src="//api.bitrix24.com/api/v1/"></script>

    <!-- Vue 3 -->
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>

    <!-- Tailwind CSS (опционально) -->
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">

<div id="app">
    <!-- Шапка -->
    <header class="bg-white shadow p-4 mb-4">
        <div class="flex justify-between items-center">
            <h1 class="text-xl font-bold">[[ appName ]]</h1>
            <div class="flex items-center gap-2">
                <span v-if="currentUser" class="text-sm text-gray-600">
                    [[ currentUser.NAME ]] [[ currentUser.LAST_NAME ]]
                </span>
                <span v-if="bitrixAuth" class="text-green-500 text-sm">Битрикс24 подключен</span>
            </div>
        </div>
    </header>

    <!-- Основной контент -->
    <main class="container mx-auto px-4">
        <!-- Кнопка создания -->
        <button @click="showCreateModal = true"
                class="bg-blue-500 text-white px-4 py-2 rounded mb-4">
            Создать
        </button>

        <!-- Список данных пользователя -->
        <div class="bg-white rounded shadow">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-2 text-left">Название</th>
                        <th class="px-4 py-2 text-left">Дата</th>
                        <th class="px-4 py-2 text-left">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="item in items" :key="item.id" class="border-t">
                        <td class="px-4 py-2">[[ item.item_name ]]</td>
                        <td class="px-4 py-2">[[ formatDate(item.created_at) ]]</td>
                        <td class="px-4 py-2">
                            <button @click="deleteItem(item.id)"
                                    class="text-red-500 hover:text-red-700">
                                Удалить
                            </button>
                        </td>
                    </tr>
                    <tr v-if="items.length === 0">
                        <td colspan="3" class="px-4 py-8 text-center text-gray-500">
                            Нет данных
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Модальное окно создания -->
        <div v-if="showCreateModal"
             class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div class="bg-white rounded-lg p-6 w-96">
                <h2 class="text-lg font-bold mb-4">Создать запись</h2>
                <input v-model="newItemName"
                       type="text"
                       placeholder="Название"
                       class="w-full border rounded px-3 py-2 mb-4">
                <div class="flex justify-end gap-2">
                    <button @click="showCreateModal = false"
                            class="px-4 py-2 text-gray-600">
                        Отмена
                    </button>
                    <button @click="createItem"
                            class="px-4 py-2 bg-blue-500 text-white rounded">
                        Создать
                    </button>
                </div>
            </div>
        </div>
    </main>
</div>

<script>
const { createApp, ref, onMounted } = Vue;

// Получаем BASE_PATH из Flask
const BASE_PATH = '{{ config.BASE_PATH | default("", true) }}';

createApp({
    delimiters: ['[[', ']]'],  // Чтобы не конфликтовать с Jinja2

    setup() {
        // Состояние
        const appName = ref('Мое приложение');
        const bitrixAuth = ref({{ 'true' if bitrix_auth else 'false' }});
        const currentUser = ref(null);
        const items = ref([]);
        const showCreateModal = ref(false);
        const newItemName = ref('');

        // Получение текущего пользователя через BX24 SDK
        const getCurrentUser = () => {
            return new Promise((resolve) => {
                BX24.callMethod('user.current', {}, (result) => {
                    if (result.data()) {
                        currentUser.value = result.data();
                        resolve(result.data());
                    } else {
                        resolve(null);
                    }
                });
            });
        };

        // Загрузка данных пользователя
        const loadItems = async () => {
            if (!currentUser.value) return;

            try {
                const url = `${BASE_PATH}/api/items?user_id=${currentUser.value.ID}&user_name=${encodeURIComponent(currentUser.value.NAME)}`;
                const response = await fetch(url, { credentials: 'include' });
                items.value = await response.json();
            } catch (error) {
                console.error('Error loading items:', error);
            }
        };

        // Создание записи
        const createItem = async () => {
            if (!newItemName.value.trim()) return;

            try {
                const response = await fetch(`${BASE_PATH}/api/items?user_id=${currentUser.value.ID}&user_name=${encodeURIComponent(currentUser.value.NAME)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ name: newItemName.value })
                });

                if (response.ok) {
                    newItemName.value = '';
                    showCreateModal.value = false;
                    await loadItems();
                }
            } catch (error) {
                console.error('Error creating item:', error);
            }
        };

        // Удаление записи
        const deleteItem = async (itemId) => {
            if (!confirm('Удалить запись?')) return;

            try {
                const response = await fetch(`${BASE_PATH}/api/items/${itemId}?user_id=${currentUser.value.ID}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });

                if (response.ok) {
                    await loadItems();
                }
            } catch (error) {
                console.error('Error deleting item:', error);
            }
        };

        // Форматирование даты
        const formatDate = (dateStr) => {
            if (!dateStr) return '';
            return new Date(dateStr).toLocaleDateString('ru-RU');
        };

        // Инициализация при монтировании
        onMounted(() => {
            // ВАЖНО: Дожидаемся инициализации BX24
            BX24.init(async () => {
                console.log('BX24 initialized');
                await getCurrentUser();
                await loadItems();
            });
        });

        return {
            appName,
            bitrixAuth,
            currentUser,
            items,
            showCreateModal,
            newItemName,
            createItem,
            deleteItem,
            formatDate
        };
    }
}).mount('#app');
</script>

</body>
</html>
```

### 7.2 Полезные методы BX24 SDK

```javascript
// Инициализация (обязательно первым)
BX24.init(function() {
    // SDK готов к работе
});

// Получение текущего пользователя
BX24.callMethod('user.current', {}, function(result) {
    console.log(result.data());
    // { ID: "1", NAME: "Иван", LAST_NAME: "Петров", EMAIL: "ivan@company.ru", ... }
});

// Получение списка пользователей
BX24.callMethod('user.get', { FILTER: { ACTIVE: true } }, function(result) {
    console.log(result.data());
});

// Создание события в календаре
BX24.callMethod('calendar.event.add', {
    type: 'user',
    ownerId: userId,
    name: 'Название события',
    from: '2024-01-15T10:00:00',
    to: '2024-01-15T11:00:00',
    description: 'Описание'
}, function(result) {
    console.log('Event created:', result.data());
});

// Batch запросы (несколько методов за раз)
BX24.callBatch({
    'user': ['user.current', {}],
    'departments': ['department.get', {}]
}, function(result) {
    console.log('User:', result.user.data());
    console.log('Departments:', result.departments.data());
});

// Завершение установки (только в install)
BX24.installFinish();

// Открытие модального окна с внешней страницей
BX24.openApplication({
    'bx24_label': {
        'text': 'Заголовок'
    }
});

// Изменение размера фрейма
BX24.fitWindow();
BX24.resizeWindow(800, 600);
```

---

## 8. Конфигурация

### 8.1 Файл .env

```env
# Flask
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=production

# Base path для reverse proxy (если приложение на подпути)
BASE_PATH=/my-app
SCRIPT_NAME=/my-app

# Bitrix24 OAuth
BITRIX24_CLIENT_ID=your_client_id_from_bitrix24
BITRIX24_CLIENT_SECRET=your_client_secret_from_bitrix24

# Database
DATABASE_PATH=./data/app.db

# Logging
LOGGING_LEVEL=INFO
```

### 8.2 config.py

```python
# config.py

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Base path для reverse proxy
    BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')
    APPLICATION_ROOT = BASE_PATH or '/'

    # Bitrix24
    BITRIX24_CLIENT_ID = os.environ.get('BITRIX24_CLIENT_ID')
    BITRIX24_CLIENT_SECRET = os.environ.get('BITRIX24_CLIENT_SECRET')

    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', './data/app.db')

    # Session - КРИТИЧНО для iframe
    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # Logging
    LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO')
```

---

## 9. Развертывание

### 9.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Создание директории для данных
RUN mkdir -p /app/data

# Переменные окружения
ENV FLASK_ENV=production
ENV DATABASE_PATH=/app/data/app.db

# Запуск через gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app"]
```

### 9.2 docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    build: .
    container_name: my-bitrix-app
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
      - BASE_PATH=${BASE_PATH:-}
      - BITRIX24_CLIENT_ID=${BITRIX24_CLIENT_ID}
      - BITRIX24_CLIENT_SECRET=${BITRIX24_CLIENT_SECRET}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 9.3 Nginx конфигурация

```nginx
upstream my_bitrix_app {
    server localhost:5000;
}

server {
    listen 443 ssl http2;
    server_name your-domain.ru;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Если приложение на подпути /my-app
    location /my-app/ {
        rewrite ^/my-app/(.*) /$1 break;
        proxy_pass http://my_bitrix_app/;

        # Важные заголовки
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Script-Name /my-app;

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

## 10. Чеклист интеграции

### Перед началом разработки

- [ ] Зарегистрировать приложение в Битрикс24 Маркетплейс
- [ ] Получить `BITRIX24_CLIENT_ID` и `BITRIX24_CLIENT_SECRET`
- [ ] Настроить URL установки и URL приложения в настройках

### Обязательные компоненты

- [ ] OAuth авторизация через Битрикс24
- [ ] Endpoint `/install` для установки
- [ ] Session cookies с `SameSite=None; Secure`
- [ ] BX24 SDK на фронтенде
- [ ] `BX24.installFinish()` при установке
- [ ] `BX24.init()` при загрузке приложения

### Личный кабинет

- [ ] Получение `user_id` через `BX24.callMethod('user.current')`
- [ ] Таблица в БД с полем `owner_id`
- [ ] Фильтрация данных по `owner_id`
- [ ] API endpoints с проверкой пользователя

### Безопасность

- [ ] HTTPS обязателен
- [ ] Токены хранятся в httpOnly сессии
- [ ] Проверка владельца при операциях с данными
- [ ] Валидация входных данных

### Развертывание

- [ ] Docker/docker-compose настроен
- [ ] Nginx с SSL настроен
- [ ] Health check endpoint работает
- [ ] Логирование настроено
- [ ] База данных на персистентном хранилище

---

## Частые проблемы и решения

### 1. Cookies не сохраняются в iframe

**Проблема:** Сессия не работает, пользователь постоянно разлогинивается

**Решение:**
```python
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True  # Требует HTTPS!
```

### 2. BX24 is not defined

**Проблема:** SDK не загружается

**Решение:**
```html
<!-- SDK должен загружаться ДО вашего кода -->
<script src="//api.bitrix24.com/api/v1/"></script>
<script>
    // Ваш код ПОСЛЕ загрузки SDK
    BX24.init(function() { ... });
</script>
```

### 3. Установка не завершается

**Проблема:** Приложение "зависает" при установке

**Решение:**
```javascript
BX24.init(function() {
    BX24.installFinish();  // Обязательно вызвать!
});
```

### 4. CORS ошибки

**Проблема:** Запросы блокируются из-за CORS

**Решение:**
```python
from flask_cors import CORS

CORS(app, supports_credentials=True, origins=[
    'https://*.bitrix24.ru',
    'https://*.bitrix24.com'
])
```

### 5. Токены истекли

**Проблема:** API возвращает ошибку авторизации

**Решение:**
```python
def call_api_with_refresh(domain, access_token, refresh_token, method, params):
    result = Bitrix24API.call_method(domain, access_token, method, params)

    if result.get('error') == 'expired_token':
        # Обновляем токены
        new_tokens = Bitrix24API.refresh_tokens(refresh_token, domain)
        session['bitrix_access_token'] = new_tokens['access_token']
        session['bitrix_refresh_token'] = new_tokens['refresh_token']

        # Повторяем запрос
        result = Bitrix24API.call_method(domain, new_tokens['access_token'], method, params)

    return result
```

---

## Ссылки

- [Документация REST API Битрикс24](https://dev.1c-bitrix.ru/rest_help/)
- [BX24 JavaScript SDK](https://dev.1c-bitrix.ru/rest_help/js_library/)
- [Маркетплейс партнеров](https://partners.bitrix24.ru/)
- [OAuth авторизация](https://dev.1c-bitrix.ru/rest_help/oauth/index.php)
