import time
from typing import Callable, Any, Awaitable

import cachetools
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.dispatcher.flags import get_flag
from aiogram.exceptions import TelegramAPIError

from .config import settings
import asyncio


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, time_limit: float = 0.5):
        self.limit = cachetools.TTLCache(maxsize=10_000, ttl=time_limit)

    async def __call__(self,
                       handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: Message | CallbackQuery,
                       data: dict[str, Any]
                       ):
        chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
        if chat_id in self.limit:
            return None
        self.limit[chat_id] = None
        return await handler(event, data)


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки админа."""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any]
    ) -> Any:
        """Выполняется для каждого события."""
        user = event.from_user

        if user and user.id in settings.ADMIN_IDS:
            data["is_admin"] = True
            return await handler(event, data)
        return None
