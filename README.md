[README.md](https://github.com/user-attachments/files/29476736/README.md)
# Модуль Уведомлений — Руководство по Развертыванию и Использованию
# АНО ВО "Гуманитарный университет"

---

## Содержание

1. Структура проекта
2. Необходимые компоненты
3. Установка (Linux)
4. Установка (Windows)
5. Конфигурация
6. Запуск приложения
7. Запуск воркера
8. Проверка функциональности через Swagger
9. Примеры полезных нагрузок для уведомлений
10. Примечания по базе данных

---

## 1. Структура проекта

notification_module/
|
|-- main.py # Приложение FastAPI, все HTTP-эндпоинты, менеджер жизненного цикла
|-- models.py # Схемы Pydantic + модели ORM SQLAlchemy
|-- database.py # Асинхронный движок, фабрика сессий, инициализация схемы
|-- config.py # Централизованные настройки, загружаемые из .env
|-- redis_queue.py # FIFO-очередь Redis, цикл воркера, повтор с экспоненциальной задержкой
|-- send_notification.py # Маршрутизация по каналам, EmailSender, VKSender, GatewayClient
|-- create_content.py # Построитель контента на Jinja2, шаблоны по умолчанию
|-- worker.py # Точка входа для отдельного процесса воркера
|-- requirements.txt # Зависимости Python
|-- .env.example # Пример переменных окружения
|-- .env # Ваш локальный конфиг (создается вами, не в системе контроля версий)
|
|-- templates/ # Шаблоны Jinja2 (создаются автоматически при первом запуске)
| |-- new_assignment_email.html
| |-- new_assignment_email.txt
| |-- new_assignment_vk.txt
| |-- deadline_student_email.html
| |-- deadline_student_email.txt
| |-- deadline_student_vk.txt
| |-- deadline_teacher_email.html
| |-- deadline_teacher_email.txt
| |-- deadline_teacher_vk.txt
| |-- review_result_email.html
| |-- review_result_email.txt
| |-- review_result_vk.txt
|
|-- logs/ # Файлы журналов (создаются автоматически)
|-- app.log
|-- worker.log
text


---

## 2. Необходимые компоненты

| Компонент      | Версия       | Примечания                                     |
|----------------|--------------|------------------------------------------------|
| Python         | 3.10 или 3.11| 3.12 также поддерживается                      |
| Redis          | 6.x или 7.x  | Должен быть запущен до старта приложения       |
| (Опционально) PostgreSQL | 14+   | Нужен только для продакшена; по умолчанию SQLite |

---

## 3. Установка — Linux / macOS

```bash
# 1. Склонируйте или скопируйте папку проекта
cd notification_module

# 2. Создайте и активируйте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Установите и запустите Redis (пример для Debian/Ubuntu)
sudo apt-get update && sudo apt-get install -y redis-server
sudo systemctl start redis-server
# Проверка:
redis-cli ping   # должно вернуть PONG

# 5. Создайте ваш конфигурационный файл
cp .env.example .env
# Отредактируйте .env, указав ваши SMTP, VK и настройки базы данных

# 6. Создайте папку для логов
mkdir -p logs
```

4. Установка — Windows

```powershell
# 1. Откройте PowerShell в папке проекта

# 2. Создайте и активируйте виртуальное окружение
python -m venv venv
venv\Scripts\activate

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Установите Redis для Windows
# Вариант A: Используйте MSI с https://github.com/microsoftarchive/redis/releases
# Вариант B: Используйте WSL2 (рекомендуется): wsl --install, затем следуйте инструкциям для Linux внутри WSL.
# Вариант C: Используйте Docker Desktop: docker run -d -p 6379:6379 redis:7

# Проверьте доступность Redis:
# redis-cli.exe ping   (или telnet 127.0.0.1 6379)

# 5. Создайте ваш конфигурационный файл
copy .env.example .env
# Отредактируйте .env с помощью Блокнота или VS Code

# 6. Создайте папку для логов
mkdir logs
```

5. Конфигурация

Отредактируйте .env (скопируйте из .env.example). Минимально необходимое для рабочего прототипа:
ini

# Настройки прототипа по умолчанию (SQLite + Redis на локальном хосте, без учетных данных email/VK)
DATABASE_URL=sqlite+aiosqlite:///./notifications.db
REDIS_URL=redis://localhost:6379/0

Для доставки по электронной почте укажите:
ini

SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=your@yandex.ru
SMTP_PASSWORD=ваш-пароль-приложения
SMTP_FROM_EMAIL=your@yandex.ru

Для доставки через VK укажите:
ini

VK_API_TOKEN=vk1.a.ваш_токен_здесь
VK_GROUP_ID=123456789

Если учетные данные отсутствуют, модуль работает в заглушечном режиме: уведомления
записываются в журнал, но фактически не отправляются. Это позволяет проводить полное
сквозное тестирование очереди, логики повторных попыток и сохранения в базе данных
без внешних зависимостей.
6. Запуск приложения (API-сервер)
Linux / macOS
bash

source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

Windows
powershell

venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

API будет доступен по адресам:

    Swagger UI: http://localhost:8001/docs

    ReDoc: http://localhost:8001/redoc

    Health: http://localhost:8001/health

7. Запуск воркера

Воркер должен запускаться как отдельный процесс (в отдельном окне терминала):
Linux / macOS
bash

source venv/bin/activate
python worker.py

Windows
powershell

venv\Scripts\activate
python worker.py

Воркер забирает задачи из очереди Redis и доставляет их через настроенные
каналы. Без запущенного воркера задачи накапливаются в очереди со статусом
PENDING и обрабатываются после запуска воркера.
8. Проверка функциональности через Swagger

    Откройте http://localhost:8001/docs в браузере.

    Нажмите на зеленый эндпоинт "POST /notifications/send", затем "Try it out".

    Вставьте один из примеров полезной нагрузки из Раздела 9 в тело запроса.

    Нажмите "Execute".

    Ответ будет содержать task_id и статус "pending".

    Проверьте статус доставки:

        Откройте "GET /notifications/status/{task_id}"

        Введите task_id из шага 5

        Выполните — статус должен измениться на "sent" после обработки воркером

    Просмотрите историю:

        Откройте "GET /notifications/history"

        Оставьте все фильтры пустыми, чтобы увидеть все записи

9. Примеры полезных нагрузок для уведомлений
9.1 Новое задание (для студента)
json

{
  "notification_type": "new_assignment",
  "recipient_id": "student-001",
  "channel": "all",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Реализация алгоритма сортировки",
    "topic": "Алгоритмы и структуры данных",
    "deadline": "2025-01-20T23:59:00"
  },
  "student": {
    "full_name": "Иванов Иван Иванович",
    "group": "ПИ-201",
    "course": 2,
    "email": "student@example.com",
    "vk_user_id": "12345678"
  }
}

9.2 Напоминание о дедлайне (для студента)
json

{
  "notification_type": "deadline_student",
  "recipient_id": "student-001",
  "channel": "email",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Реализация алгоритма сортировки",
    "topic": "Алгоритмы и структуры данных",
    "deadline": "2025-01-20T23:59:00"
  },
  "student": {
    "full_name": "Иванов Иван Иванович",
    "group": "ПИ-201",
    "course": 2,
    "email": "student@example.com"
  }
}

9.3 Сводка по дедлайнам (для преподавателя)
json

{
  "notification_type": "deadline_teacher",
  "recipient_id": "teacher-001",
  "channel": "email",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Реализация алгоритма сортировки",
    "topic": "Алгоритмы и структуры данных",
    "deadline": "2025-01-20T23:59:00"
  },
  "teacher": {
    "full_name": "Петров Петр Петрович",
    "email": "teacher@example.com"
  },
  "submission_summary": {
    "submitted": [
      "Иванов Иван Иванович",
      "Сидорова Мария Алексеевна"
    ],
    "not_submitted": [
      "Кузнецов Дмитрий Олегович",
      "Волкова Анастасия Сергеевна"
    ]
  }
}

9.4 Оценка за задание (для студента)
json

{
  "notification_type": "review_result",
  "recipient_id": "student-001",
  "channel": "all",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Реализация алгоритма сортировки",
    "topic": "Алгоритмы и структуры данных",
    "deadline": "2025-01-20T23:59:00",
    "grade": 92.0,
    "max_grade": 100.0,
    "feedback": "Хорошая реализация QuickSort. Анализ сложности верен. Добавьте больше тестов для граничных случаев."
  },
  "student": {
    "full_name": "Иванов Иван Иванович",
    "group": "ПИ-201",
    "course": 2,
    "email": "student@example.com",
    "vk_user_id": "12345678"
  }
}

9.5 Обновление настроек пользователя
text

PUT /notifications/settings/student-001

{
  "email_enabled": true,
  "vk_enabled": false,
  "email_address": "newemail@example.com"
}

10. Примечания по базе данных
SQLite (по умолчанию, прототип)

Дополнительная настройка не требуется. Файл notifications.db создается автоматически
в папке проекта при первом запуске.

Для просмотра базы данных:
bash

# Linux
sqlite3 notifications.db "SELECT task_id, status, notification_type FROM notification_records LIMIT 10;"

# Windows (если sqlite3.exe есть в PATH)
sqlite3.exe notifications.db "SELECT task_id, status FROM notification_records;"

PostgreSQL (продакшен)

    Создайте базу данных:

sql

CREATE DATABASE notifications_db;
CREATE USER notifications_user WITH PASSWORD 'secret';
GRANT ALL PRIVILEGES ON DATABASE notifications_db TO notifications_user;

    Обновите .env:

ini

DATABASE_URL=postgresql+asyncpg://notifications_user:secret@localhost:5432/notifications_db

    Таблицы создаются автоматически при запуске (SQLAlchemy create_all).

11. Устранение неполадок
Отказ в подключении к Redis

Убедитесь, что Redis запущен:
bash

redis-cli ping          # Linux
redis-cli.exe ping      # Windows

Если используется нестандартный порт, обновите REDIS_URL в .env.
Письма не отправляются

    Проверьте учетные данные SMTP в .env.

    Для Yandex: включите "Пароли приложений" в настройках аккаунта и используйте пароль приложения.

    Для Gmail: используйте пароль приложения (не пароль от аккаунта).

    Проверьте logs/worker.log на наличие точной ошибки SMTP.

Сообщения VK не отправляются

    Убедитесь, что токен сообщества имеет разрешение messages.

    Убедитесь, что в настройках сообщества VK включена опция "Разрешить сообщения от сообщества".

    Получатель должен предварительно начать диалог с ботом сообщества.

Задачи остаются в статусе PENDING

Воркер не запущен. Запустите python worker.py в отдельном терминале.
Ошибки шаблонов

Шаблоны автоматически создаются в templates/ при первом запуске. Если они
отсутствуют или повреждены, удалите папку templates/ и перезапустите
приложение — они будут восстановлены из стандартных шаблонов.
