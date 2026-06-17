# from files
from models import (
    AssignmentNotification,
    DeadlineNotification,
    TeacherDeadlineNotification,
    CheckedAssignmentNotification,
)


# Функции для создания контента уведомлений
def create_new_assignment_content(assignment: AssignmentNotification) -> tuple:
    """Создание контента для уведомления о новом задании"""
    subject = f"Новое задание: {assignment.assignment_number}"

    body = f"""
    Уважаемый студент!
    
    Появилось новое задание:
    
    Номер задания: {assignment.assignment_number}
    Предмет: {assignment.subject_name}
    Описание: {assignment.assignment_description or "Нет описания"}
    Дедлайн: {assignment.deadline}
    
    Пожалуйста, проверьте задание в системе.
    """

    html_body = f"""
    <html>
    <body>
        <h2>Новое задание</h2>
        <p>Уважаемый студент!</p>
        <p>Появилось новое задание:</p>
        <ul>
            <li><strong>Номер задания:</strong> {assignment.assignment_number}</li>
            <li><strong>Предмет:</strong> {assignment.subject_name}</li>
            <li><strong>Описание:</strong> {assignment.assignment_description or "Нет описания"}</li>
            <li><strong>Дедлайн:</strong> {assignment.deadline}</li>
        </ul>
        <p>Пожалуйста, проверьте задание в системе.</p>
    </body>
    </html>
    """

    return subject, body, html_body


def create_deadline_student_content(notification: DeadlineNotification) -> tuple:
    """Создание контента для уведомления студента о дедлайне"""
    subject = f"Напоминание о дедлайне: {notification.assignment_number}"

    body = f"""
    Уважаемый(ая) {notification.student_name}!
    
    Напоминаем о приближении дедлайна по заданию:
    
    Номер задания: {notification.assignment_number}
    Предмет: {notification.subject_name}
    Группа: {notification.group_name}
    Дедлайн: {notification.deadline}
    
    Пожалуйста, сдайте задание вовремя!
    """

    html_body = f"""
    <html>
    <body>
        <h2>Напоминание о дедлайне</h2>
        <p>Уважаемый(ая) {notification.student_name}!</p>
        <p>Напоминаем о приближении дедлайна по заданию:</p>
        <ul>
            <li><strong>Номер задания:</strong> {notification.assignment_number}</li>
            <li><strong>Предмет:</strong> {notification.subject_name}</li>
            <li><strong>Группа:</strong> {notification.group_name}</li>
            <li><strong>Дедлайн:</strong> {notification.deadline}</li>
        </ul>
        <p>Пожалуйста, сдайте задание вовремя!</p>
    </body>
    </html>
    """

    return subject, body, html_body


def create_deadline_teacher_content(notification: TeacherDeadlineNotification) -> tuple:
    """Создание контента для уведомления преподавателя о дедлайне"""
    subject = f"Отчет по дедлайну: {notification.assignment_number}"

    students_list = "\n".join(
        [
            f"  • {student['student_name']} - {'Сдано' if student.get('submitted') else 'Не сдано'}"
            for student in notification.students
        ]
    )

    body = f"""
    Уважаемый преподаватель!
    
    Дедлайн по заданию {notification.assignment_number} ({notification.subject_name}) для группы {notification.group_name} наступил {notification.deadline}.
    
    Статус сдачи заданий студентами:
    
    {students_list}
    
    Всего студентов: {len(notification.students)}
    Сдало: {sum(1 for s in notification.students if s.get("submitted"))}
    Не сдало: {sum(1 for s in notification.students if not s.get("submitted"))}
    """

    html_body = f"""
    <html>
    <body>
        <h2>Отчет по дедлайну</h2>
        <p>Уважаемый преподаватель!</p>
        <p>Дедлайн по заданию <strong>{notification.assignment_number}</strong> ({notification.subject_name}) для группы <strong>{notification.group_name}</strong> наступил {notification.deadline}.</p>
        
        <h3>Статус сдачи заданий студентами:</h3>
        <ul>
        {"".join([f"<li>{'✅' if student.get('submitted') else '⏳'} {student['student_name']} - {'Сдано' if student.get('submitted') else 'Не сдано'}</li>" for student in notification.students])}
        </ul>
        
        <p><strong>Всего студентов:</strong> {len(notification.students)}<br>
        <strong>Сдало:</strong> {sum(1 for s in notification.students if s.get("submitted"))}<br>
        <strong>Не сдало:</strong> {sum(1 for s in notification.students if not s.get("submitted"))}</p>
    </body>
    </html>
    """

    return subject, body, html_body


def create_checked_assignment_content(
    notification: CheckedAssignmentNotification,
) -> tuple:
    """Создание контента для уведомления о проверенном задании"""
    subject = f"Задание проверено: {notification.assignment_number}"

    body = f"""
    Уважаемый(ая) {notification.student_name}!
    
    Ваше задание {notification.assignment_number} проверено!
    
    Дата проверки: {notification.checked_at}
    """

    if notification.grade:
        body += f"Оценка: {notification.grade}\n"

    if notification.feedback:
        body += f"\nОтзыв преподавателя:\n{notification.feedback}\n"

    html_body = f"""
    <html>
    <body>
        <h2>Задание проверено</h2>
        <p>Уважаемый(ая) {notification.student_name}!</p>
        <p>Ваше задание <strong>{notification.assignment_number}</strong> проверено!</p>
        <p><strong>Дата проверки:</strong> {notification.checked_at}</p>
        {f"<p><strong>Оценка:</strong> {notification.grade}</p>" if notification.grade else ""}
        {f"<p><strong>Отзыв преподавателя:</strong><br>{notification.feedback}</p>" if notification.feedback else ""}
    </body>
    </html>
    """

    return subject, body, html_body