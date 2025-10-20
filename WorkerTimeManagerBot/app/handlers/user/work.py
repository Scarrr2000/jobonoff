import asyncio
from datetime import datetime, UTC, timedelta

import pytz
from aiogram import Router, F
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hitalic

from app.db import queries
from app.handlers.state import groups
from app.keyboards import replies, inlines
from app.misc import utils
from app.misc.config import private_logger, settings

router = Router()


@router.message(Command('work'))
async def redirect_worker(message: Message, state: FSMContext):
    # Если пользователь уже работает, то перенаправляем на второй модуль
    user = await queries.get_user(message.from_user.id)
    if await queries.get_active_worker_session(user.id):
        await end_my_work(message)
    else:
        # Иначе на первый
        await start_my_work(message, state)


@router.message(F.text == 'Начать работу')
async def start_my_work(message: Message, state: FSMContext):
    # Переводим на состояние для хранения всех полученных данных в кэше
    # Также необходимо, чтобы если в будущем, когда бот будет масштабироваться, можно было бы обрабатывать разные
    # хэндлеры для получения местоположения, как отличающиеся друг от друга типы обработчиков
    await state.set_state(groups.ProcessWorkerSession.GET_GEOLOCATION)

    # Если пользователь уже работает, то в сообщении нет смысла. Делаем return
    if await queries.get_active_worker_session(message.from_user.id):
        return

    await message.answer(
        hbold('Отправьте своё местоположение для фиксации:') +
        f'\nНажмите на кнопку {hbold('"Отправить местоположение"')} ниже.'
        f'\n\n{hbold('Очень важно!')} Убедитесь, что у Telegram есть доступ к вашему местоположению '
        f'{hitalic('(у вас включена передача гео локационных данных и у Telegram есть права на просмотр и получение '
                   'этих данных)')}.',
        reply_markup=replies.send_geolocation)


@router.message(F.text == 'Завершить работу')
async def end_my_work(message: Message):
    user = await queries.get_user(message.from_user.id)

    # : queries.models.WorkSession сделал чисто для себя, обычно не принято использовать, но в данном случае это мало на
    # что влияет
    session: queries.models.WorkSession = await queries.get_active_worker_session(user.id)
    if not session:
        # Выходим, если сессии не обнаружено, ибо продолжать нет смысла
        return

    # astimezone, так как sqlite не умеет передавать часовые пояса в код
    current_date = datetime.now(UTC)

    try:
        await message.bot.delete_message(session.worker.telegram_id, session.old_message_id)
    except TelegramBadRequest:
        pass

    text = f'{hbold('Смена завершена!')}\n'

    # Сформировать текст сообщения
    start_date = (session.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    end_date = (current_date + timedelta(hours=3)).strftime(
        "%Y-%m-%d %H:%M:%S") if current_date else "Еще не закончена"
    text += (
        f"\n"
        f"Дата начала: {hbold(start_date)}\n"
        f"Дата окончания: {hbold(end_date)}\n"
    )

    text += f'\n{await get_all_worker_session_info(session)}'
    msg = await message.answer(text, reply_markup=replies.worker_menu(message.from_user.id))
    await queries.end_worker_active_session(session.worker.id, current_date)

    chat = await message.bot.get_chat(session.worker.telegram_id)
    username = f'@{chat.username}'
    for admin_id in settings.ADMIN_IDS:
        try:
            text = f'Отчёт за пользователя {username} ID{chat.id}'

            # Сформировать текст сообщения
            start_date = (session.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
            end_date = (current_date + timedelta(hours=3)).strftime(
                "%Y-%m-%d %H:%M:%S") if current_date else "Еще не закончена"
            text += (
                f"\n"
                f"Дата начала: {hbold(start_date)}\n"
                f"Дата окончания: {hbold(end_date)}\n"
            )

            text += f'\n{await get_all_worker_session_info(session)}'
            await message.bot.send_message(admin_id, text,
            reply_markup=inlines.worker_editor_panel(session.id, session.worker.telegram_id))
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)

    if not session.hour_kopecks_rate:
        await queries.set_old_message_id_to_session(session.id, msg.message_id)

    private_logger.info(f'Работник ID{message.from_user.id} остановил свой таймер (завершил работу).')


async def get_all_worker_session_info(session: queries.models.WorkSession):
    # Извлечение компонентов с использованием divmod
    total_earned = await queries.get_session_payment(session) / 100
    days, hours, minutes, seconds = await queries.get_session_time(session)

    text = f'Время работы: '
    text += f' {days} дней' if days else ''
    text += f' {hours} часов' if hours else ''
    text += f' {minutes} минут' if minutes else ''
    text += f'{seconds} секунд' if not any([hours, days, minutes]) else ''
    text += (
        f'\nАдрес: {utils.get_address(session.geolocation_latitude, session.geolocation_longitude)}\n'
        f'Место / позиция: {session.work_position}')

    if session.hour_kopecks_rate:
        # Ставка за минуту * кол-во отработанных минут. Всё это округлённое до 2 знаков после запятой
        # Скобки для читабельности
        text += (f'\nИндивидуальная ставка: {(session.hour_kopecks_rate / 100):.2f} ₽ / час'
                 f'\nИтого заработано: {total_earned} ₽')

    return text
