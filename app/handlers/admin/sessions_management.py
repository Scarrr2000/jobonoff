from datetime import timedelta
from typing import List

import pytz
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.markdown import hbold

from app.db import models
from app.db import queries
from app.keyboards import inlines
from app.misc import utils
from app.misc.config import private_logger

router = Router()

ITEMS_PER_PAGE = 15  # Количество элементов на странице


@router.callback_query(F.data == 'sessions_management')
async def sessions_management(callback: CallbackQuery):
    """
    Обработчик для кнопки "Управление сессиями".
    Выводит список сессий с пагинацией.
    """

    await list_sessions(callback)


async def list_sessions(callback: CallbackQuery, page: int = 1):
    """
    Функция для вывода списка сессий с пагинацией.
    """
    try:
        sessions: List[models.WorkSession] = await queries.get_all_sessions(page=page, per_page=ITEMS_PER_PAGE)
        total_sessions: int = await queries.get_sessions_count()
        max_page: int = (total_sessions + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE  # общее количество страниц

        if not sessions:
            await callback.answer("Нет сессий для отображения.")
            return

        keyboard = await generate_sessions_keyboard(sessions, page, max_page, callback.bot)

        await callback.message.edit_text(
            text=hbold("Список сессий:"),
            reply_markup=keyboard
        )
        await callback.answer()  # Убираем "ожидание"
    except Exception as e:
        await callback.answer("Произошла ошибка при выводе списка сессий.")
        private_logger.error(f'Ошибка при получении списка сессий: {e}')


async def generate_sessions_keyboard(sessions: List[models.WorkSession], page: int,
                                     max_page: int, bot: Bot) -> InlineKeyboardMarkup:
    """
    Функция для генерации клавиатуры со списком сессий и кнопками пагинации.
    """
    keyboard_buttons = []
    for session in sessions:
        session_date = (session.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
        chat = await bot.get_chat(session.worker.telegram_id)
        button_text = f"@{chat.username} | Сессия от: {session_date}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"session_info:{session.id}")])

    # Кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(text="Назад", callback_data=f"sessions_page:0:{page - 1}"))
    if page < max_page:
        pagination_buttons.append(InlineKeyboardButton(text="Вперед", callback_data=f"sessions_page:0:{page + 1}"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons + [pagination_buttons])
    return keyboard


@router.callback_query(F.data.startswith("sessions_page:"))
async def sessions_pagination_handler(callback: CallbackQuery):
    """
    Обработчик для кнопок пагинации сессий.
    """
    page: int = int(callback.data.split(":")[2])  # sessions_page:page -> page
    await list_sessions(callback, page)


@router.callback_query(F.data.startswith("session_info:"))
async def session_info_handler(callback: CallbackQuery):
    """
    Обработчик для кнопок с информацией о сессии.
    Выводит информацию о сессии: дата начала, дата окончания, сумма к выплате.
    """
    session_id: int = int(callback.data.split(":")[1])  # session_info:123 -> 123

    # Получить сессию из базы данных через queries
    session_obj: models.WorkSession = await queries.get_session_by_id(session_id)
    if not session_obj:
        await callback.answer("Сессия не найдена.")
        return

    # Получить сумму к выплате
    payment = await queries.get_session_payment(session_obj)
    days, hours, minutes, seconds = await queries.get_session_time(session_obj)
    payment_rub: float = payment / 100  # Перевести в рубли

    # Сформировать текст сообщения
    start_date = (session_obj.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    end_date = (session_obj.ended_date + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S") if session_obj.ended_date else "Еще не закончена"
    text = (
        f"Информация о сессии:\n"
        f"Дата начала: {hbold(start_date)}\n"
        f"Дата окончания: {hbold(end_date)}\n"
    )

    text += f'Время работы: '
    text += f' {days} дней' if days else ''
    text += f' {hours} часов' if hours else ''
    text += f' {minutes} минут' if minutes else ''
    text += f'{seconds} секунд' if not any([hours, days, minutes]) else ''
    text += (
        f'\nАдрес: {utils.get_address(session_obj.geolocation_latitude, session_obj.geolocation_longitude)}\n'
        f'Место / позиция: {session_obj.work_position}')

    if session_obj.hour_kopecks_rate:
        # Ставка за минуту * кол-во отработанных минут. Всё это округлённое до 2 знаков после запятой
        text += (f'\nИндивидуальная ставка: {(session_obj.hour_kopecks_rate / 100):.2f} ₽ / час'
                 f'\nИтого заработано: {payment_rub} ₽')

    await callback.message.edit_text(text=text, reply_markup=inlines.edit_session_kb(session_id,
                                                                                     session_obj.worker.telegram_id))
    await callback.answer()
