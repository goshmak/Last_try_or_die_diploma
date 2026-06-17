import logging
import json
from typing import Optional, Dict, Any
from uuid import UUID

# from files
from data_base import get_db_connection
from sends.send_email_notification import send_email_notification
from sends.send_vk_notification import send_vk_notification
from sends.create_content import (
    create_new_assignment_content,
    create_deadline_student_content,
    create_deadline_teacher_content,
    create_checked_assignment_content,
)
from models import (
    NotificationType,
    NotificationChannel,
    AssignmentNotification,
    DeadlineNotification,
    TeacherDeadlineNotification,
    CheckedAssignmentNotification,
)


logger = logging.getLogger(__name__)


# Логика отправки уведомлений
async def send_notification(
    user_id: UUID,
    user_type: str,
    notification_type: NotificationType,
    content_data: Dict[str, Any],
    metadata: Optional[Dict] = None,
):
    """Отправка уведомления пользователю"""
    conn = await get_db_connection()

    try:
        # Получение настроек пользователя
        row = await conn.fetchrow(
            """
            SELECT * FROM user_notification_preferences 
            WHERE user_id = $1 AND user_type = $2
            """,
            str(user_id), user_type
        )

        if not row:
            logger.warning(f"No preferences found for user {user_id}")
            return False

        preferences = dict(row)

        # Проверка, включен ли текущий тип уведомлений
        notification_enabled = preferences.get(
            f"{notification_type.value}_enabled", True
        )
        if not notification_enabled:
            logger.info(
                f"Notification type {notification_type} disabled for user {user_id}"
            )
            return False

        # Создание контента в зависимости от типа уведомления
        if notification_type == NotificationType.NEW_ASSIGNMENT:
            assignment = AssignmentNotification(**content_data)
            subject, body, html_body = create_new_assignment_content(assignment)
            title = f"Новое задание: {assignment.assignment_number}"
        elif notification_type == NotificationType.DEADLINE_STUDENT:
            deadline_notif = DeadlineNotification(**content_data)
            subject, body, html_body = create_deadline_student_content(deadline_notif)
            title = f"Дедлайн: {deadline_notif.assignment_number}"
        elif notification_type == NotificationType.DEADLINE_TEACHER:
            teacher_notif = TeacherDeadlineNotification(**content_data)
            subject, body, html_body = create_deadline_teacher_content(teacher_notif)
            title = f"Отчет по дедлайну: {teacher_notif.assignment_number}"
        elif notification_type == NotificationType.ASSIGNMENT_CHECKED:
            checked_notif = CheckedAssignmentNotification(**content_data)
            subject, body, html_body = create_checked_assignment_content(checked_notif)
            title = f"Задание проверено: {checked_notif.assignment_number}"
        else:
            raise ValueError(f"Unknown notification type: {notification_type}")

        # Определение канала/каналов для отправки
        channel = preferences["notification_channel"]
        success = False

        # Сохранение записи о уведомлении
        notification_id = await conn.fetchval(
            """
            INSERT INTO notifications (user_id, user_type, notification_type, title, content, channel, status, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING notification_id
            """,
            str(user_id),
            user_type,
            notification_type.value,
            title,
            body,
            channel,
            "pending",
            json.dumps(metadata) if metadata else None,
        )

        # Отправка уведомления
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH]:
            email_success = await send_email_notification(
                preferences["email"], subject, body, html_body
            )
            if email_success:
                success = True

        if channel in [
            NotificationChannel.VK,
            NotificationChannel.BOTH,
        ] and preferences.get("vk_id"):
            # Для VK используется упрощенная версия (без HTML, используем Markdown VK)
            vk_text = f"🔔 {title}\n\n{body}"
            vk_success = await send_vk_notification(
                preferences["vk_id"], vk_text
            )
            if vk_success:
                success = True

        # Обновление статуса уведомления
        status = "sent" if success else "failed"
        await conn.execute(
            """
            UPDATE notifications 
            SET status = $1, sent_at = CURRENT_TIMESTAMP 
            WHERE notification_id = $2
            """,
            status, notification_id
        )

        return success

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False
    finally:
        await conn.close()