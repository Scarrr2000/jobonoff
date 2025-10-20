from datetime import datetime, UTC

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold

from app.db import queries
from ..state.groups import AdminStates
from ...keyboards import replies
from ...misc import utils
from ...misc.config import private_logger

router = Router()


@router.callback_query(lambda call: call.data.startswith('edit_sis_starts_time:'))
async def handle_edit_start_time(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    session_id = int(call.data.split(':')[1])
    await state.set_state(AdminStates.waiting_for_start_time)
    await state.update_data(session_id=session_id)
    await call.message.answer("Пожалуйста, введите новое время начала сессии в формате 'YYYY-MM-DD HH:MM'.",
                              reply_markup=replies.back_action)


@router.callback_query(lambda call: call.data.startswith('edit_sis_end_time:'))
async def handle_edit_end_time(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    session_id = int(call.data.split(':')[1])
    await state.set_state(AdminStates.waiting_for_end_time)
    await state.update_data(session_id=session_id)
    await call.message.answer("Пожалуйста, введите новое время конца сессии в формате 'YYYY-MM-DD HH:MM'.",
                              reply_markup=replies.back_action)


@router.callback_query(lambda call: call.data.startswith('delete_session:'))
async def handle_delete_session(call: types.CallbackQuery):
    await call.answer()
    session_id = int(call.data.split(':')[1])
    try:
        await queries.delete_session(session_id)
        await call.message.answer("Сессия успешно удалена.")
        private_logger.info(f'Администратор {call.from_user.id} удалил сессию ID{session_id}')
    except Exception as e:
        await call.message.answer(f"Ошибка при удалении сессии")
        private_logger.error(f"Ошибка при удалении сессии: {e}")


@router.callback_query(F.data.startswith('end_work_session:'))
async def end_work_session(call: CallbackQuery):
    await call.answer()
    session_id = int(call.data.split(':')[1])
    session: queries.models.WorkSession = await queries.get_session_by_id(session_id)

    try:
        await queries.end_worker_active_session(session.user_id, datetime.now(UTC))
        await call.message.answer("Сессия успешно остановлена.")
        private_logger.info(f'Администратор {call.from_user.id} остановил сессию ID{session_id}')

        # Извлечение компонентов с использованием divmod
        total_earned = await queries.get_session_payment(session) / 100
        days, hours, minutes, seconds = await queries.get_session_time(session)

        text = f'{hbold('Вашу смену завершил администратор!')}\n'
        text += f'Время работы: '
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

        await call.bot.send_message(session.worker.telegram_id, text, reply_markup=replies.worker_menu(
            session.worker.telegram_id
        ))
    except Exception as e:
        await call.message.answer(f"Ошибка при остановке сессии")
        private_logger.error(f"Ошибка при остановке сессии: {e}")
