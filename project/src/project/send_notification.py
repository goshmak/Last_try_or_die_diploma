import logging
from typing import Any

import httpx

from config import settings
from create_content import ContentBuilder
from models import ChannelType, NotificationRequest, NotificationType

logger = logging.getLogger("notification_module.send_notification")


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

# Sends notification emails via SMTP using aiosmtplib.
class EmailSender:

    async def send(
        self, *, to_address: str, subject: str, body_html: str, body_text: str
    ) -> None:
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            logger.warning(
                "[STUB] Email not configured. Would send to=%s subject='%s'",
                to_address,
                subject,
            )
            return

        try:
            import aiosmtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = (
                f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            )
            message["To"] = to_address
            message.attach(MIMEText(body_text, "plain", "utf-8"))
            message.attach(MIMEText(body_html, "html", "utf-8"))

            if settings.SMTP_USE_SSL:
                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    use_tls=True,
                    username=settings.SMTP_USERNAME,
                    password=settings.SMTP_PASSWORD,
                )
            else:
                await aiosmtplib.send(
                    message,
                    hostname=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    start_tls=True,
                    username=settings.SMTP_USERNAME,
                    password=settings.SMTP_PASSWORD,
                )

            logger.info("Email sent | to=%s | subject='%s'", to_address, subject)

        except Exception as exc:
            logger.error("Email delivery failed | to=%s | error=%s", to_address, exc)
            raise


# ---------------------------------------------------------------------------
# VK sender
# ---------------------------------------------------------------------------

#Sends messages via the VK Bots API (messages.send method).
class VKSender:

    VK_API_URL = "https://api.vk.com/method/messages.send"

    async def send(self, *, vk_user_id: str, message_text: str) -> None:
        if not settings.VK_API_TOKEN or not settings.VK_GROUP_ID:
            logger.warning(
                "[STUB] VK not configured. Would send to user_id=%s message='%s...'",
                vk_user_id,
                message_text[:60],
            )
            return

        import random

        params = {
            "user_id": vk_user_id,
            "message": message_text,
            "random_id": random.randint(0, 2**31),
            "access_token": settings.VK_API_TOKEN,
            "v": settings.VK_API_VERSION,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.VK_API_URL, data=params)
                response.raise_for_status()
                data = response.json()

            if "error" in data:
                error = data["error"]
                raise RuntimeError(
                    f"VK API error {error.get('error_code')}: {error.get('error_msg')}"
                )

            logger.info("VK message sent | user_id=%s", vk_user_id)

        except Exception as exc:
            logger.error("VK delivery failed | user_id=%s | error=%s", vk_user_id, exc)
            raise


# ---------------------------------------------------------------------------
# API Gateway client (fetches user/assignment data when not in request)
# ---------------------------------------------------------------------------

# === Lightweight HTTP client for querying the API Gateway ===
class GatewayClient:

    async def get_user(self, recipient_id: str) -> dict[str, Any]:
        url = f"{settings.API_GATEWAY_BASE_URL}/users/{recipient_id}"
        try:
            async with httpx.AsyncClient(timeout=settings.API_GATEWAY_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning(
                "Could not fetch user data from gateway | recipient_id=%s | error=%s",
                recipient_id,
                exc,
            )
            return {}

    async def get_assignment(self, assignment_id: str) -> dict[str, Any]:
        url = f"{settings.API_GATEWAY_BASE_URL}/assignments/{assignment_id}"
        try:
            async with httpx.AsyncClient(timeout=settings.API_GATEWAY_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning(
                "Could not fetch assignment from gateway | assignment_id=%s | error=%s",
                assignment_id,
                exc,
            )
            return {}


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

# === Orchestrates content building and multi-channel delivery ===
class NotificationRouter:
    """
    Steps:
      1. Build subject + HTML + plain-text content via ContentBuilder.
      2. Resolve which channels to use.
      3. Call EmailSender and/or VKSender.
    """

    def __init__(self) -> None:
        self.email_sender = EmailSender()
        self.vk_sender = VKSender()
        self.content_builder = ContentBuilder()
        self.gateway = GatewayClient()

    # === Main entry point called by the queue worker ===
    # Raises on unrecoverable errors; caller handles retry logic.
    async def route(self, *, task_id: str, request: NotificationRequest) -> None:
        logger.info(
            "Routing | task_id=%s | type=%s | channel=%s",
            task_id,
            request.notification_type,
            request.channel,
        )

        # === Build notification content ===
        content = self.content_builder.build(request)
        subject: str = content["subject"]
        body_html: str = content["body_html"]
        body_text: str = content["body_text"]
        vk_text: str = content["vk_text"]

        # === Resolve channels ===
        channels = await self._resolve_channels(request)

        # === Deliver ===
        errors: list[str] = []

        if ChannelType.EMAIL in channels:
            email_address = self._get_email(request)
            if email_address:
                try:
                    await self.email_sender.send(
                        to_address=email_address,
                        subject=subject,
                        body_html=body_html,
                        body_text=body_text,
                    )
                except Exception as exc:
                    errors.append(f"email:{exc}")
            else:
                logger.warning(
                    "No email address for recipient_id=%s, skipping email channel.",
                    request.recipient_id,
                )

        if ChannelType.VK in channels:
            vk_user_id = self._get_vk_user_id(request)
            if vk_user_id:
                try:
                    await self.vk_sender.send(
                        vk_user_id=vk_user_id,
                        message_text=vk_text,
                    )
                except Exception as exc:
                    errors.append(f"vk:{exc}")
            else:
                logger.warning(
                    "No VK user ID for recipient_id=%s, skipping VK channel.",
                    request.recipient_id,
                )

        if errors:
            raise RuntimeError(f"Delivery errors: {'; '.join(errors)}")

    # === Channel resolution helpers ===
    async def _resolve_channels(self, request: NotificationRequest) -> list[ChannelType]:
        """
        Determine the target channel list.
        If channel == ALL, query user settings; otherwise use the explicit choice.
        """
        if request.channel != ChannelType.ALL:
            return [request.channel]

        # Query user preferences from the database
        from database import get_db_session
        from models import NotificationSettings
        from sqlalchemy import select

        async with get_db_session() as session:
            stmt = select(NotificationSettings).where(
                NotificationSettings.recipient_id == request.recipient_id
            )
            result = await session.execute(stmt)
            prefs = result.scalar_one_or_none()

        channels: list[ChannelType] = []
        if prefs is None or prefs.email_enabled:
            channels.append(ChannelType.EMAIL)
        if prefs is None or prefs.vk_enabled:
            channels.append(ChannelType.VK)

        return channels or [ChannelType.EMAIL]  # Default to email if both disabled

    # === Contact detail helpers ===
    def _get_email(self, request: NotificationRequest) -> str | None:
        """Extract email from the request payload (student or teacher)."""
        if request.student and request.student.email:
            return request.student.email
        if request.teacher and request.teacher.email:
            return request.teacher.email
        return None

    def _get_vk_user_id(self, request: NotificationRequest) -> str | None:
        """Extract VK user ID from the request payload."""
        if request.student and request.student.vk_user_id:
            return request.student.vk_user_id
        if request.teacher and request.teacher.vk_user_id:
            return request.teacher.vk_user_id
        return None
