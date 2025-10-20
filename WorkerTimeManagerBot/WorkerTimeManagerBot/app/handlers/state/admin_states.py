from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.db import queries
from app.handlers.state.groups import AdminStates
from app.misc.config import private_logger

router = Router()


@router.message(AdminStates.waiting_for_start_time)
async def process_start_time(message: types.Message, state: FSMContext):
    new_start_time = message.text
    data = await state.get_data()
    session_id = data.get('session_id')
    try:
        await queries.update_session_start_time(session_id, new_start_time)
        await message.answer("Время начала сессии успешно изменено.")
        private_logger.info(f'Администратор {message.from_user.id} '
                            f'изменил время начала сессии ID{session_id} на {new_start_time}')
    except Exception as e:
        await message.answer(f"Ошибка при изменении времени")
        private_logger.error(f'Ошибка при изменении времени: {e}')
    await state.clear()


@router.message(AdminStates.waiting_for_end_time)
async def process_end_time(message: types.Message, state: FSMContext):
    new_end_time = message.text
    data = await state.get_data()
    session_id = data.get('session_id')
    try:
        await queries.update_session_end_time(session_id, new_end_time)
        await message.answer("Время конца сессии успешно изменено.")
        private_logger.info(f'Администратор {message.from_user.id} '
                            f'изменил время конца сессии ID{session_id} на {new_end_time}')
    except Exception as e:
        await message.answer(f"Ошибка при изменении времени")
        private_logger.error(f'Ошибка при изменении времени: {e}')
    await state.clear()
