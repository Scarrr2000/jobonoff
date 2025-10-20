import asyncio
from datetime import timedelta
from typing import List

import pytz
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.markdown import hbold

from app.db import models
from app.db import queries
from app.keyboards import inlines, replies
from app.misc import utils
from app.misc.config import private_logger

router = Router()


@router.message(F.text == 'Отменить действие')
async def back_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Действие отменено')


class UserManagementStates(StatesGroup):
    """
    FSM States для управления пользователями
    """
    waiting_for_telegram_id = State()
    waiting_for_rate = State()
    waiting_for_username = State()  # Ожидание ввода юзернейма


ITEMS_PER_PAGE = 15  # Количество элементов на странице


@router.message(F.text == 'Административная панель')
async def admin_panel_utils(message: Message):
    await message.answer(hbold(message.text), reply_markup=inlines.admin_panel)


@router.callback_query(F.data == 'workers_management')
async def worker_management(callback: CallbackQuery):
    """
    Обработчик для кнопки "Управление работниками".
    Выводит список пользователей с пагинацией.
    """
    await list_users(callback)


async def list_users(callback: CallbackQuery, page: int = 1):
    """
    Функция для вывода списка пользователей с пагинацией.
    """
    try:
        users: List[models.User] = await queries.get_all_users(page=page, per_page=ITEMS_PER_PAGE)
        total_users: int = await queries.get_all_users_count()
        max_page: int = (total_users + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE  # общее количество страниц

        if not users:
            await callback.answer("Нет пользователей для отображения.")
            return

        keyboard = await generate_users_keyboard(users, page, max_page, callback.bot)

        await callback.message.edit_text(
            text=hbold("Список пользователей:"),
            reply_markup=keyboard
        )
        await callback.answer()  # Убираем "ожидание"
    except Exception as e:
        private_logger.error(f"Ошибка при выводе списка пользователей: {e}")
        await callback.answer("Произошла ошибка при выводе списка пользователей.")


async def generate_users_keyboard(users: List[models.User], page: int, max_page: int, bot: Bot) ->(
        InlineKeyboardMarkup):
    """
    Функция для генерации клавиатуры со списком пользователей и кнопками пагинации.
    """
    keyboard_buttons = []
    for user in users:
        session_count: int = await queries.get_user_session_count(user.id)
        chat = await bot.get_chat(user.telegram_id)
        button_text = f"ID: {user.telegram_id} | @{chat.username} | Сессий: {session_count}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"user:{user.telegram_id}")])

    # Кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(InlineKeyboardButton(text="Назад", callback_data=f"page:{page - 1}"))
    if page < max_page:
        pagination_buttons.append(InlineKeyboardButton(text="Вперед", callback_data=f"page:{page + 1}"))

    # Кнопка для поиска пользователя
    search_button = [InlineKeyboardButton(text="Поиск пользователя", callback_data="search_user")]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons + [pagination_buttons, search_button])
    return keyboard


@router.callback_query(F.data == "search_user")
async def search_user(callback: CallbackQuery, state: FSMContext):
    """
    Начинает процесс поиска пользователя, предлагая выбрать тип поиска
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="По Telegram ID", callback_data="search_by_id")],
        [InlineKeyboardButton(text="По Username", callback_data="search_by_username")]
    ])
    await callback.message.edit_text("Выберите способ поиска пользователя:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "search_by_id")
async def search_by_id(callback: CallbackQuery, state: FSMContext):
    """
    Начинает поиск пользователя по Telegram ID
    """
    await state.set_state(UserManagementStates.waiting_for_telegram_id)
    await callback.message.answer("Введите Telegram ID пользователя:", reply_markup=replies.back_action)
    await callback.answer()


@router.callback_query(F.data == "search_by_username")
async def search_by_username(callback: CallbackQuery, state: FSMContext):
    """
    Начинает поиск пользователя по Username
    """
    await state.set_state(UserManagementStates.waiting_for_username)
    await callback.message.answer("Введите Username пользователя:", reply_markup=replies.back_action)
    await callback.answer()


@router.message(F.text, UserManagementStates.waiting_for_telegram_id)
async def get_telegram_id(message: Message, state: FSMContext):
    """
    Получает telegram_id от пользователя для поиска
    """
    try:
        telegram_id = int(message.text)
        user: models.User = await queries.get_user_by_telegram_id(telegram_id)
        if user:
            await show_user_info(message, user.telegram_id)  # вызываем функцию для показа информации о пользователе
        else:
            await message.answer("Пользователь с таким telegram_id не найден")
        await state.clear()

    except ValueError:
        await message.answer("Некорректный telegram_id. Введите число")


@router.message(F.text, UserManagementStates.waiting_for_username)
async def get_username(message: Message, state: FSMContext):
    """
    Получает username от пользователя для поиска
    """
    username = message.text
    if username.startswith('@'):
        username = username[1:]
    users = await queries.get_all_users(None)

    _user = None
    for user in users:
        chat = await message.bot.get_chat(user.telegram_id)
        if chat.username == username:
            _user = await queries.get_user(chat.id)

    if _user:
        await show_user_info(message, _user.telegram_id)  # вызываем функцию для показа информации о пользователе
    else:
        await message.answer("Пользователь с таким username не найден")
    await state.clear()


@router.callback_query(F.data.startswith("page:"))
async def pagination_handler(callback: CallbackQuery):
    """
    Обработчик для кнопок пагинации.
    """
    page: int = int(callback.data.split(":")[1])  # page:2 -> 2
    await list_users(callback, page)


@router.callback_query(F.data.startswith("user:"))
async def user_info_handler(callback: CallbackQuery):
    """
    Обработчик для кнопок с информацией о пользователе.
    Выводит информацию о пользователе и кнопки управления.
    """
    telegram_id: int = int(callback.data.split(":")[1])  # user:12345 -> 12345
    await show_user_info(callback.message, telegram_id)
    await callback.answer()


async def show_user_info(message: Message, telegram_id: int):
    """
    Функция для повторного вывода информации о пользователе
    """
    user: models.User = await queries.get_user_by_telegram_id(telegram_id)

    if not user:
        await message.answer("Пользователь не найден.")
        return

    session_count: int = await queries.get_user_session_count(user.id)

    chat = await message.bot.get_chat(user.telegram_id)

    text = (
        f"Информация о пользователе:\n"
        f"Username: @{chat.username}\n"
        f"Telegram ID: {hbold(user.telegram_id)}\n"
        f"Количество сессий: {hbold(session_count)}\n"
    )

    keyboard = inlines.worker_user_editor(user.telegram_id)

    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    finally:
        await message.answer(text=text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("change_rate:"))
async def change_rate_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик для кнопки "Изменить ставку".
    Запрашивает новое значение ставки у пользователя.
    """
    session_id: int = int(callback.data.split(":")[1])  # change_rate:12345 -> 12345
    await state.update_data(session_id=session_id)
    await state.set_state(UserManagementStates.waiting_for_rate)
    await callback.message.answer("Пожалуйста, введите новую ставку в рублях:", reply_markup=replies.back_action)
    await callback.answer()


@router.message(UserManagementStates.waiting_for_rate)
async def get_new_rate(message: Message, state: FSMContext):
    """
    Получает новое значение ставки от пользователя и сохраняет его в базе данных.
    """
    try:
        rate_rub: float = float(message.text)
        rate_kopecks: int = int(rate_rub * 100)
        data = await state.get_data()
        session_id: int = data.get("session_id")
        user_session: models.WorkSession = await queries.get_session_by_id(session_id)

        if not user_session:
            await message.answer("Сессия не найдена.")
            await state.clear()
            return

        await queries.update_user_session_rate(session_id, rate_kopecks)

        if user_session.old_message_id:
            try:
                await message.bot.delete_message(user_session.worker.telegram_id, user_session.old_message_id)
            except TelegramBadRequest:
                pass

        await message.bot.send_message(user_session.worker.telegram_id, (
            f'Ваша ставка изменилась, отправляю отчёт по сессии №{user_session.id}\n'
            f'{await get_sessions_all_information(user_session)}'
        ))


        private_logger.info(f'Администратор {message.from_user.id} изменил ставку '
                            f'{user_session.worker.telegram_id} на {rate_rub} руб')

        await message.answer(f"Ставка пользователя {user_session.worker.telegram_id} "
                             f"успешно изменена на {rate_rub} руб.")
        await state.clear()

        # Обновляем информацию о пользователе
        await show_user_info(message, user_session.worker.telegram_id)
        # Функция для повторного вывода информации о пользователе
    except ValueError:
        await message.answer("Некорректный формат ставки. Пожалуйста, введите число.")
    except Exception as e:
        private_logger.error(f"Ошибка при обновлении ставки пользователя: {e}")
        await message.answer("Произошла ошибка при обновлении ставки.")


@router.callback_query(F.data.startswith("user_sessions:"))
async def user_sessions_handler(callback: CallbackQuery):
    """
    Обработчик для кнопки "Сессии пользователя".
    Выводит список сессий пользователя с пагинацией.
    """
    telegram_id: int = int(callback.data.split(":")[1])  # user_sessions:12345 -> 12345
    user: models.User = await queries.get_user_by_telegram_id(telegram_id)

    if not user:
        await callback.answer("Пользователь не найден.")
        return

    await list_user_sessions(callback, user.id)


async def list_user_sessions(callback: CallbackQuery, user_id: int, page: int = 1):
    """
    Функция для вывода списка сессий пользователя с пагинацией.
    """
    try:
        sessions: List[models.WorkSession] = await queries.get_user_sessions(user_id=user_id, page=page,
                                                                             per_page=ITEMS_PER_PAGE)
        total_sessions: int = await queries.get_user_session_count(user_id)
        max_page: int = (total_sessions + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        if not sessions:
            await callback.answer("Нет сессий для отображения.")
            return

        keyboard = await generate_sessions_keyboard(sessions, user_id, page, max_page)

        await callback.message.edit_text(
            text=hbold("Сессии пользователя:"),
            reply_markup=keyboard
        )
        await callback.answer()  # Убираем "ожидание"
    except Exception as e:
        private_logger.error(f"Ошибка при выводе списка сессий пользователя {user_id}: {e}")
        await callback.answer("Произошла ошибка при выводе списка сессий пользователя.")


async def generate_sessions_keyboard(sessions: List[models.WorkSession], user_id: int, page: int,
                                     max_page: int) -> InlineKeyboardMarkup:
    """
    Функция для генерации клавиатуры со списком сессий и кнопками пагинации.
    """
    keyboard_buttons = []
    for session in sessions:
        # Обрезаем дату создания для краткости
        session_date = (session.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
        button_text = f"Сессия от: {session_date}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"session_info:{session.id}")])

    # Кнопки пагинации
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="Назад", callback_data=f"sessions_page:{user_id}:{page - 1}"))
    if page < max_page:
        print(user_id, page, f"sessions_page:{user_id}:{page + 1}")
        pagination_buttons.append(
            InlineKeyboardButton(text="Вперед", callback_data=f"sessions_page:{user_id}:{page + 1}"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons + [pagination_buttons])
    return keyboard


# @router.callback_query(F.data.startswith("sessions_page:"))
# async def sessions_pagination_handler(callback: CallbackQuery):
#     """
#     Обработчик для кнопок пагинации сессий.
#     """
#     print(callback.data)
#     data = callback.data.split(":")  # sessions_page:user_id:page
#     print(data)
#     user_id: int = int(data[1])
#     page: int = int(data[2])
#     await list_user_sessions(callback, user_id, page)


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
    text = f"Информация о сессии:\n" + await get_sessions_all_information(session_obj)


    await callback.message.edit_text(text=text, reply_markup=inlines.edit_session_kb(session_id,
                                                                                     session_obj.worker.telegram_id))
    await callback.answer()


async def get_sessions_all_information(session_obj: queries.models.WorkSession):

    # Получить сумму к выплате
    payment = await queries.get_session_payment(session_obj)
    days, hours, minutes, seconds = await queries.get_session_time(session_obj)
    payment_rub: float = payment / 100  # Перевести в рубли

    # Сформировать текст сообщения
    start_date = (session_obj.created_at + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    end_date = (session_obj.ended_date + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")\
        if session_obj.ended_date else "Еще не закончена"

    text = (f"Дата начала: {hbold(start_date)}\n"
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
    # Скобки для читабельности
        text += (f'\nИндивидуальная ставка: {(session_obj.hour_kopecks_rate / 100):.2f} ₽ / час'
    f'\nИтого заработано: {payment_rub} ₽')

    return text
