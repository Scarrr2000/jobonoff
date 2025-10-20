import asyncio
from datetime import timedelta
from os import utime

import pytz
from aiogram import Router, F
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Location
from aiogram.utils.markdown import hbold

from . import groups
from ...db import queries
from ...keyboards import replies, inlines
from ...misc import utils
from ...misc.config import private_logger, settings

router = Router()


# F.location для обработки получения исключительно местоположения
# Любой другой текс / медиа / прочее обработано не будет
@router.message(groups.ProcessWorkerSession.GET_GEOLOCATION, F.location)
async def get_worker_geolocation(message: Message, state: FSMContext):
    await state.update_data(location=message.location)
    await state.set_state(groups.ProcessWorkerSession.GET_EXACT_POSITION_MANUALLY)

    await message.answer(hbold('Успех!') + f' Геолокация успешно получена и сохранена, введите вашу текущую позицию '
                                           f'на должности:', reply_markup=replies.decline_work_starts)


@router.message(groups.ProcessWorkerSession.GET_EXACT_POSITION_MANUALLY, F.text)
async def get_worker_position(message: Message, state: FSMContext):
    # Валидируем размер получаемого текста во избежание лишних ошибок с БД (при масштабировании полезно, но в целом
    # можно убрать, так как SQLite тупо обрезает лишние символы за нас)
    if len(message.text) > 255:
        await message.answer('Текст не должен превышать 255 символов. Повторите попытку:')
        return

    try:
        data = await state.get_data()
        location: Location = data['location']

        session: queries.models.WorkSession = await queries.add_worker_session(message.from_user.id, location.latitude,
                                                   location.longitude, message.text)
        private_logger.info(f'Работник ID{message.from_user.id} запустил свой таймер (приступил к работе).')

        # await message.answer(hbold('Успех!') + '\nВы приступили к работе.'
        #                                        f'\n\nНажмите {hbold('Завершить работу')} для того, чтобы закончить '
        #                                        f'выполнение работы.',
        #                      reply_markup=replies.ends_work)

        await send_notification_about_work_to_admin(message, session, session.worker)
    except Exception as e:
        await message.answer('Непредвиденная ошибка, убедитесь в правильности введённых данных или обратитесь к '
                             'Администратору')

        # Данные не указываем, так как они, итак, передаются в queries при обработке тамошних внутренних ошибок
        private_logger.error(f'Не удалось установить сессию для пользователя по непредвиденной ошибке: {e}')
    finally:
        # Не забываем очистить состояние и его кэш соответственно
        await state.clear()


async def send_notification_about_work_to_admin(message: Message, session: queries.models.WorkSession,
                                                worker: queries.models.User):
    chat = await message.bot.get_chat(worker.telegram_id)
    username = f'@{chat.username}'

    try:
        msg = await message.bot.send_message(worker.telegram_id, text=(
            f'Вы начали работу!\n'
            f'Начало: {(session.created_at  + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")}\n'
            f'Ставка пользователя: Не задана'
            f'\n\nАдрес: {utils.get_address(session.geolocation_latitude, session.geolocation_longitude)}'
            f'\nМесто: {session.work_position}'), reply_markup=replies.ends_work)

        await queries.set_old_message_id_to_session(session.id, msg.message_id)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)

    for admin_id in settings.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text=(
                f'Пользователь {username} ID{chat.id} начал работу\n'
                f'Начало: {(session.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")}\n'
                f'Ставка пользователя: Не задана'
                f'\n\nАдрес: {utils.get_address(session.geolocation_latitude, session.geolocation_longitude)}'
                f'\nМесто: {session.work_position}'
            ), reply_markup=inlines.worker_editor_panel(session.id, worker.telegram_id))
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
