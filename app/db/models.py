from datetime import datetime, UTC

from sqlalchemy import BigInteger, DateTime, func, ForeignKey, String, Float, Boolean
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship

from app.misc.config import settings

engine = create_async_engine(settings.DATABASE_URL)
session = async_sessionmaker(engine)

# В UTC для независимого подсчёта времени
utcnow = datetime.now(UTC)


class Base(AsyncAttrs, DeclarativeBase):
    # "Integer" здесь необязателен, ибо поле, итак, по умолчанию byte-типа
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


# Или же Worker
class User(Base):
    __tablename__ = 'users'

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    # В копейках, так как Float не лучший выбор для вычислений, если None - то ставка берется из os (или не берётся etc)

    work_sessions: Mapped['WorkSession | None'] = relationship(back_populates="worker", cascade="all, delete-orphan")


"""
Заметка для понимания про ondelete='CASCADE' и cascade="all, delete-orphan"
Первое означает, что мы привязываем столбец таблицы к инструменту для взаимодействий между таблицами one to many CASCADE
CASCADE позволяет удалять все связанные столбцы в отношениях при удалении ключевого столбца, на который ссылается второй
Второе уже описывает само поведение (то, как будет вести себя CASCADE), all - удалить ВСЕ связанные, delete-orphan - 
прервать ВСЕ операции (добавление, удаление и т.д.)

Это обезопасит нашу БД от нежелательных ошибок, если мы захотим удалить какого-то пользователя вручную (не знаю зачем 
нам это, но добавил чисто ради безопасности, пусть может и излишней).
"""


# Сессии работников в виде отдельной таблицы для возможного масштабирования в будущем
class WorkSession(Base):
    __tablename__ = 'work_sessions'

    # Получаем время старта работы
    created_at: Mapped[datetime] = mapped_column(DateTime(True), server_default=func.now())
    hour_kopecks_rate: Mapped[int | None] = mapped_column()

    # Unique=true - у одного пользователя может быть только одна сессия
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete='CASCADE'))
    worker: Mapped["User"] = relationship(back_populates="work_sessions", uselist=False)

    geolocation_latitude: Mapped[float] = mapped_column(Float)  # Широта
    geolocation_longitude: Mapped[float] = mapped_column(Float)  # Долгота

    # 255 - разумное ограничение, которое навряд ли когда-либо нужно будет увеличивать
    work_position: Mapped[str] = mapped_column(String(255))

    # Для возможности сортировать и проверять на наличие активной сессии
    is_ended: Mapped[bool] = mapped_column(Boolean, default=False)
    ended_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Если ставки не было и нужно будет удалить сообщение
    old_message_id: Mapped[int] = mapped_column(nullable=True)


# Обычно не используется, но добавил для удобства
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
