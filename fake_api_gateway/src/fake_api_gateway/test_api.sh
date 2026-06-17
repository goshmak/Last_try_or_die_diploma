#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8001"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Тестирование Notification Service${NC}"
echo -e "${BLUE}================================${NC}\n"

# 1. Проверка здоровья
echo -e "${GREEN}1. Проверка здоровья сервисов:${NC}"
curl -s "${BASE_URL}/api/test/health" | jq '.'
echo -e "\n"

# 2. Обновление настроек пользователя
echo -e "${GREEN}2. Обновление настроек для студента:${NC}"
curl -s -X POST "${BASE_URL}/api/users/preferences" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "user_type": "student",
    "email": "ivan@example.com",
    "telegram_id": "123456789",
    "notification_channel": "both",
    "enable_new_assignment": true,
    "enable_deadline": true,
    "enable_checked": true
  }' | jq '.'
echo -e "\n"

# 3. Создание нового задания
echo -e "${GREEN}3. Создание нового задания:${NC}"
curl -s -X POST "${BASE_URL}/api/assignments/create" \
  -H "Content-Type: application/json" \
  -d '{
    "assignment_id": 100,
    "assignment_number": "ЛР-001",
    "assignment_description": "Написать программу на Python",
    "deadline": "2024-12-01 23:59:59",
    "subject_name": "Программирование",
    "group_name": "Группа А-101"
  }' | jq '.'
echo -e "\n"

# 4. Проверка дедлайна
echo -e "${GREEN}4. Проверка дедлайна:${NC}"
curl -s -X POST "${BASE_URL}/api/assignments/check-deadline" \
  -H "Content-Type: application/json" \
  -d '{
    "assignment_id": 100,
    "assignment_number": "ЛР-001",
    "subject_name": "Программирование",
    "group_name": "Группа А-101",
    "deadline": "2024-12-01 23:59:59"
  }' | jq '.'
echo -e "\n"

# 5. Проверка задания
echo -e "${GREEN}5. Проверка задания студента:${NC}"
curl -s -X POST "${BASE_URL}/api/assignments/check" \
  -H "Content-Type: application/json" \
  -d '{
    "assignment_id": 100,
    "assignment_number": "ЛР-001",
    "student_id": 1,
    "grade": "5 (отлично)",
    "feedback": "Хорошая работа! Программа работает корректно."
  }' | jq '.'
echo -e "\n"

# 6. Тестовое уведомление всем
echo -e "${GREEN}6. Отправка тестовых уведомлений всем пользователям:${NC}"
curl -s -X POST "${BASE_URL}/api/test/send-to-all" | jq '.'
echo -e "\n"

# 7. История уведомлений студента
echo -e "${GREEN}7. История уведомлений студента:${NC}"
curl -s "${BASE_URL}/api/notifications/history/1?limit=10" | jq '.'
echo -e "\n"

# 8. Статистика
echo -e "${GREEN}8. Статистика уведомлений:${NC}"
curl -s "${BASE_URL}/api/notifications/stats" | jq '.'
echo -e "\n"

echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}Тестирование завершено!${NC}"
echo -e "${BLUE}================================${NC}"