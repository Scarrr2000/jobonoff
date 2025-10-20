import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand
from pydantic.v1 import ValidationError

from app.db.models import create_tables
from app.handlers import routers
from app.misc.config import settings, BOT_COMMANDS, private_logger
from app.misc.middlewares import ThrottlingMiddleware

# Нежелательно использовать из других модулей
_dp = Dispatcher()


async def main():
    # Устанавливаем уровень логирования: рекомендую "INFO" (стоит по умолчанию)
    logging.basicConfig(level=settings.LOGGING_LEVEL)

    # Создаём БД / Таблицы (если ещё не созданы). Можно удалить, ибо всё равно управляется через alembic
    await create_tables()

    # DefaultBotProperties неизменчивы, ибо в текущей конфигурации смысла настраивать управление столь мелкими деталями
    # нет, это лишь увеличит объёмы кода и усложнит задачу
    bot = Bot(settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands([BotCommand(command=cmd, description=desc) for cmd, desc in BOT_COMMANDS.items()])

    _dp.include_routers(*routers)
    _dp.message.middleware(ThrottlingMiddleware())
    _dp.callback_query.middleware(ThrottlingMiddleware())
    await _dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except ValidationError as e:
        private_logger.error(
            f'Непредвиденная ошибка при попытке подгрузить данные из конфигурации (убедитесь, что все данные в .env '
            f'заданы верно и строго своему назначению: {e}'
        )
    except TelegramAPIError as e:
        private_logger.error(f'Ошибка установки бота после получения токена (перепроверьте его корректность): {e}')
    except Exception as e:
        private_logger.error(f'Неизвестная ошибка при инициализации бота: {e}')