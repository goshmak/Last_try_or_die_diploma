import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

# VK конфигурация
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_API_URL = "https://api.vk.com/method/"


class VKBot:
    def __init__(self, access_token: str, api_version: str = VK_API_VERSION):
        self.access_token = access_token
        self.api_version = api_version
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def send_message(self, user_id: str, message: str) -> bool:
        """Отправка сообщения пользователю ВКонтакте"""
        try:
            session = await self._get_session()
            
            # Ограничение длины сообщения VK (максимум 4096 символов)
            if len(message) > 4096:
                message = message[:4093] + "..."

            params = {
                "user_id": user_id,
                "message": message,
                "random_id": 0,  # Можно генерировать уникальный ID
                "access_token": self.access_token,
                "v": self.api_version
            }

            async with session.get(f"{VK_API_URL}messages.send", params=params) as resp:
                result = await resp.json()
                
                if "error" in result:
                    logger.error(f"VK API error: {result['error']}")
                    return False
                
                logger.info(f"VK message sent to {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to send VK message to {user_id}: {e}")
            return False

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """Получение информации о пользователе ВК"""
        try:
            session = await self._get_session()
            
            params = {
                "user_ids": user_id,
                "fields": "first_name,last_name,verified",
                "access_token": self.access_token,
                "v": self.api_version
            }

            async with session.get(f"{VK_API_URL}users.get", params=params) as resp:
                result = await resp.json()
                
                if "error" in result:
                    logger.error(f"VK API error: {result['error']}")
                    return None
                
                if result.get("response"):
                    return result["response"][0]
                
                return None

        except Exception as e:
            logger.error(f"Failed to get VK user info for {user_id}: {e}")
            return None

    async def check_user_exists(self, user_id: str) -> bool:
        """Проверка существования пользователя ВК"""
        user_info = await self.get_user_info(user_id)
        return user_info is not None

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()


# Глобальный экземпляр бота
vk_bot = VKBot(VK_ACCESS_TOKEN) if VK_ACCESS_TOKEN else None


async def send_vk_notification(vk_id: str, message: str) -> bool:
    """Отправка VK уведомления"""
    try:
        if not vk_bot:
            logger.error("VK bot not initialized")
            return False

        return await vk_bot.send_message(vk_id, message)
        
    except Exception as e:
        logger.error(f"Failed to send VK message to {vk_id}: {e}")
        return False


async def close_vk_bot():
    """Закрытие соединения с VK API"""
    if vk_bot:
        await vk_bot.close()