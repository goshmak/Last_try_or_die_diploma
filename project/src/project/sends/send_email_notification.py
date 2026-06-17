import aiosmtplib
import logging
import os

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

# Email конфигурация
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


async def send_email_notification(
    to_email: str, subject: str, body: str, html_body: Optional[str] = None
):
    """Отправка email уведомления"""
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = SMTP_USER
        message["To"] = to_email

        # Добавление текстовой версии
        part1 = MIMEText(body, "plain")
        message.attach(part1)

        # Добавление HTML версии, если есть
        if html_body:
            part2 = MIMEText(html_body, "html")
            message.attach(part2)

        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(message)

        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
