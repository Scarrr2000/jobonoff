from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from app.db import queries
from app.keyboards import replies
from app.misc.config import settings

router = Router()


@router.message(CommandStart())
@router.message(F.text == 'Отменить')
async def cmd_start(message: Message, state: FSMContext):
    # Очищаем состояние на всякий случай
    await state.clear()

    await message.answer(
        hbold(f'Добро пожаловать, {message.from_user.full_name}!') +
        f'\n\nНажмите на кнопку {hbold('"Начать работу"')} или введите команду /work для того, чтобы приступить к '
        f'выполнению работы.',
        reply_markup=replies.worker_menu(message.from_user.id))

    if message.from_user.id in settings.ADMIN_IDS:
        await message.answer('Вы авторизовались как Администратор')

    await queries.set_user(message.from_user.id)
