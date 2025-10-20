# app/db/queries.py

from datetime import datetime, timedelta, UTC
from typing import List

import pytz
from sqlalchemy import select, update, func
from sqlalchemy.orm import Mapped, selectinload

from app.db import models
from app.misc.config import private_logger


async def set_user(telegram_id: int) -> models.User | None:
    """
    Устанавливаем пользователя в базе данных, если ещё не установлен.
    :param telegram_id: Внутренний Telegram ID пользователя со стороны серверов Telegram
    :return: models User type (для удобства и пере использования в будущем)
    """

    try:
        async with models.session() as session:
            user = await session.scalar(select(models.User).where(models.User.telegram_id == telegram_id))

            if not user:
                user = models.User(telegram_id=telegram_id)
                session.add(user)

                await session.commit()
                # Refresh позволяет обновить информацию о поле в таблице согласно текущей установке
                await session.refresh(user)

            return user
    except Exception as e:
        private_logger.error(f'Ошибка при инициализации пользователя {telegram_id}: {e}')
        return None


async def get_user(telegram_id: int) -> models.User | None:
    # Не советую использовать внутри queries, так как session у каждого разный, что значит использование queries методов
    # внутри тех же queries методов может потенциально привести к ошибкам

    try:
        async with models.session() as session:
            user = await session.scalar(select(models.User).where(models.User.telegram_id == telegram_id))
            return user
    except Exception as e:
        private_logger.error(f'Ошибка получения пользователя {telegram_id}: {e}')
        return None


# Только для получения, опять же таки, взаимодействовать как-либо ещё строго не рекомендую
async def get_active_worker_session(primary_key_id: int | Mapped[int]):
    try:
        async with models.session() as session:
            # Eager Loading для избежания ошибок при попытке обратиться к worker
            return await session.scalar(select(models.WorkSession)
                                        .where(models.WorkSession.user_id == primary_key_id)
                                        .where(models.WorkSession.is_ended == False)
                                        .options(selectinload(models.WorkSession.worker)))
    except Exception as e:
        private_logger.error(f'Ошибка получения пользователя PRIMARY_KEY={primary_key_id}: {e}')
        return None


async def end_worker_active_session(worker_primary_key_id: int, ended_date: datetime):
    """
    Завершает сессию, позволяя работнику начать новую при желании
    :param ended_date: Дата окончания
    :param worker_primary_key_id: Worker ID (НЕ Telegram)
    :return: None
    """
    try:
        async with models.session() as session:
            worker_session: models.WorkSession = await session.scalar(select(models.WorkSession)
                                                  .where(models.WorkSession.user_id == worker_primary_key_id)
                                                  .where(models.WorkSession.is_ended == False))
            if worker_session:
                worker_session.is_ended = True
                worker_session.ended_date = ended_date
                await session.commit()
    except Exception as e:
        private_logger.error(f'Ошибка завершения сессии пользователя PRIMARY_KEY={worker_primary_key_id}: {e}')


async def add_worker_session(
        telegram_id: int,
        latitude: float,
        longitude: float,
        work_position: str
) -> models.WorkSession | None:
    """
    Добавляем сессию пользователя. Проверяем нет ли сессии и добавляем её
    :param telegram_id: Внутренний Telegram ID пользователя со стороны серверов Telegram
    :param latitude: Широта геолокации
    :param longitude: Долгота геолокации
    :param work_position: Введённая вручную работников позиция на должности
    :return: models WorkerSession type (для масштабирования в будущем)
    """

    try:
        # Использую, ибо уверен, что не буду взаимодействовать с ним, а лишь просматривать
        user = await get_user(telegram_id)

        async with models.session() as session:
            worker_session = await get_active_worker_session(user.id)

            if not worker_session:
                worker_session = models.WorkSession(user_id=user.id, geolocation_latitude=latitude,
                                                    geolocation_longitude=longitude, work_position=work_position)
                session.add(worker_session)

                await session.commit()
                # Refresh позволяет обновить информацию о поле в таблице согласно текущей установке
                await session.refresh(worker_session)

            return await session.scalar(select(models.WorkSession).where(models.WorkSession.id == worker_session.id)
                                        .options(selectinload(models.WorkSession.worker)))
    except Exception as e:
        private_logger.error(f'Ошибка при установке сессии работника {telegram_id}, Долгота: {longitude},'
                             f'Широта: {latitude}, Позиция: {work_position}: {e}')
        return None


async def get_user_sessions(user_id: int, page: int | None = 1, per_page: int | None  = 15)\
        -> List[models.WorkSession]:
    """
    Получение списка сессий пользователя с пагинацией.
    :param user_id: ID пользователя.
    :param page: номер страницы (по умолчанию 1).
    :param per_page: количество сессий на странице (по умолчанию 15).
    :return: Список объектов WorkSession.
    """
    try:
        async with models.session() as session:
            result = (
                select(models.WorkSession)
                .where(models.WorkSession.user_id == user_id)
                .order_by(models.WorkSession.created_at.desc())  # Сортировка по дате создания
                .options(selectinload(models.WorkSession.worker))
            )

            if (page and per_page) is not None:
                result = (result
                .offset((page - 1) * per_page)
                .limit(per_page))

            return (await session.execute(result)).scalars().all()
    except Exception as e:
        private_logger.error(f'Ошибка при получении сессий пользователя {user_id}: {e}')
        return []


async def update_user_session_rate(session_id: int, rate: int):
    """
    Обновление индивидуальной ставки пользователя.
    :param session_id: ID пользователя.
    :param rate: ставка в копейках.
    :return: None
    """
    try:
        async with models.session() as session:
            user = await session.execute(
                update(models.WorkSession)
                .where(models.WorkSession.id == session_id)
                .values(hour_kopecks_rate=rate)
            )
            await session.commit()
    except Exception as e:
        private_logger.error(f'Ошибка при обновлении ставки сессии {session}: {e}')


async def get_user_session_count(user_id: int) -> int:
    """
    Получение общего количества сессий пользователя.
    :param user_id: ID пользователя.
    :return: Количество сессий.
    """
    try:
        async with models.session() as session:
            result = await session.execute(
                select(func.count(models.WorkSession.id))
                .where(models.WorkSession.user_id == user_id)
            )
            return result.scalar_one()
    except Exception as e:
        private_logger.error(f'Ошибка при получении количества сессий пользователя {user_id}: {e}')
        return 0


async def get_all_users(page: int | None = 1, per_page: int | None = 15) -> List[models.User]:
    """
    Получение списка всех пользователей с пагинацией.
    :param page: номер страницы (по умолчанию 1).
    :param per_page: количество пользователей на странице (по умолчанию 15).
    :return: Список объектов User.
    """
    try:
        async with models.session() as session:
            result = (select(models.User).order_by(models.User.telegram_id))  # Сортировка по Telegram ID

            if (page and per_page) is not None:
                result = (result
                          .offset((page - 1) * per_page)
                          .limit(per_page))

            return (await session.execute(result)).scalars().all()
    except Exception as e:
        private_logger.error(f'Ошибка при получении списка пользователей: {e}')
        return []


async def get_all_users_count() -> int:
    """
    Получение общего количества пользователей.
    :return: Количество пользователей.
    """
    try:
        async with models.session() as session:
            result = await session.execute(
                select(func.count(models.User.id))
            )
            return result.scalar_one()
    except Exception as e:
        private_logger.error(f'Ошибка при получении количества пользователей: {e}')
        return 0


async def get_session_payment(session: models.WorkSession) -> int:
    """
    Рассчитывает сумму к выплате за сессию.
    :param session: Объект WorkSession.
    :return: Сумма к выплате в копейках.
    """
    try:
        user = session.worker
        rate = session.hour_kopecks_rate

        if rate is None:
            # Если ставка не установлена, возвращаем 0 или другое значение по умолчанию
            return 0

        # Используем provided пример кода
        current_date = pytz.utc.localize(session.ended_date) if session.ended_date else datetime.now(UTC)
        work_time: timedelta = current_date - pytz.utc.localize(session.created_at)

        total_seconds = work_time.total_seconds()
        payment = (rate * total_seconds) / 3600

        return int(payment)
    except Exception as e:
        private_logger.error(f"Ошибка при расчете выплаты за сессию {session.id}: {e}")
        return 0


async def get_session_time(session: models.WorkSession) -> tuple[int, int, int, int]:
    """
        Рассчитывает кол-во дней, часов, минут и секунд.
        :param session: Объект WorkSession.
        :return: Время.
        """
    try:
        user = session.worker

        # Используем provided пример кода
        current_date = pytz.utc.localize(session.ended_date) if session.ended_date else datetime.now(UTC)
        work_time: timedelta = current_date - pytz.utc.localize(session.created_at)

        # Извлечение компонентов с использованием divmod
        days = work_time.days
        hours, rem = divmod(work_time.seconds, 3600)
        minutes, seconds = divmod(rem, 60)

        total_seconds = work_time.total_seconds()

        return int(days), int(hours), int(minutes), int(seconds)
    except Exception as e:
        private_logger.error(f"Ошибка при расчете времени за сессию {session.id}: {e}")
        return 0, 0, 0, 0


async def get_user_by_telegram_id(telegram_id: int) -> models.User | None:
    """
    Получение пользователя по telegram_id
    """
    try:
        async with models.session() as session:
            result = await session.execute(
                select(models.User)
                .where(models.User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        private_logger.error(f'Ошибка при получении пользователя по telegram_id {telegram_id}: {e}')
        return None


async def get_session_by_id(session_id: int) -> models.WorkSession | None:
    """
    Получение сессии по ID.
    :param session_id: ID сессии.
    :return: Объект WorkSession или None.
    """
    try:
        async with models.session() as session:
            session_obj = await session.scalar(
                select(models.WorkSession)
                .where(models.WorkSession.id == session_id)
                .options(selectinload(models.WorkSession.worker))
            )
            return session_obj
    except Exception as e:
        private_logger.error(f"Ошибка при получении сессии по ID {session_id}: {e}")
        return None


async def get_all_sessions(page: int | None = 1, per_page: int | None = 15) -> List[models.WorkSession]:
    """
    Получение списка всех сессий с пагинацией.
    :param page: номер страницы (по умолчанию 1).
    :param per_page: количество сессий на странице (по умолчанию 15).
    :return: Список объектов WorkSession.
    """
    try:
        async with models.session() as session:
            result = (select(models.WorkSession)
                      .order_by(models.WorkSession.created_at.desc()))  # Сортировка по дате создания

            if (page and per_page) is not None:
                result = (result
                          .offset((page - 1) * per_page)
                          .limit(per_page)
                          .options(selectinload(models.WorkSession.worker)))

            return (await session.execute(result)).scalars().all()
    except Exception as e:
        private_logger.error(f'Ошибка при получении списка сессий: {e}')
        return []


async def update_session_start_time(session_id: int, new_start_time: str):
    """Обновляет время начала сессии."""
    async with models.session() as session:
        try:
            date_object = datetime.strptime(f'{new_start_time}:00', "%Y-%m-%d %H:%M:%S")
            date_object = date_object - timedelta(hours=3) # MSC to UTC
        except Exception:
            date_object = datetime.strptime(f'{new_start_time}', "%Y-%m-%d %H:%M:%S")
        await session.execute(
            update(models.WorkSession)
            .where(models.WorkSession.id == session_id)
            .values(created_at=date_object)
        )
        await session.commit()


async def update_session_end_time(session_id: int, new_end_time: str):
    """Обновляет время конца сессии."""
    async with models.session() as session:
        date_object = datetime.strptime(new_end_time, "%Y-%m-%d %H:%M:%S")
        await session.execute(
            update(models.WorkSession)
            .where(models.WorkSession.id == session_id)
            .values(ended_date=date_object)
        )
        await session.commit()


async def delete_session(session_id: int):
    """Удаляет сессию."""
    async with models.session() as session:
        sis = await session.scalar(
            select(models.WorkSession)
            .where(models.WorkSession.id == session_id)
        )
        await session.delete(sis)
        await session.commit()


async def set_old_message_id_to_session(session_id: int, message_id: int):
    async with models.session() as session:
        session_obj: models.WorkSession = await session.scalar(
            select(models.WorkSession)
            .where(models.WorkSession.id == session_id)
        )

        session_obj.old_message_id = message_id
        await session.commit()


async def get_sessions_count():
    return len(await get_all_sessions(None, None))
