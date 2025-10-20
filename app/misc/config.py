import logging

from dotenv import load_dotenv
from pydantic.v1 import Field
from pydantic_settings import BaseSettings

load_dotenv()

BOT_COMMANDS = {
    'start': 'Перезапуск',
    'work': 'Начать / завершить работу'
}


# Конфигурационный класс для подгрузки данных из окружения (необязателен, но принято использовать для безопасности)
class Settings(BaseSettings):
    DATABASE_URL: str = Field('sqlite+aiosqlite:///database.sqlite3')
    LOGGING_LEVEL: str | int = Field('INFO')
    BOT_TOKEN: str = Field()
    ADMIN_IDS: list[int] = Field()


settings = Settings()

# Необязательно и редко используется в подобных проектах, но если брать в учёт, что бот может масштабироваться,
# то почему бы и нет. По-моему, очень даже удобно для отслеживания полезных данных
private_logger = logging.getLogger('LOCAL-PROJECT-PROCESS')  # Или любое другое название
handler = logging.StreamHandler()
file_handler = logging.FileHandler('private_logs.txt', encoding='utf-8')
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
private_logger.addHandler(handler)
private_logger.addHandler(file_handler)
private_logger.propagate = False
