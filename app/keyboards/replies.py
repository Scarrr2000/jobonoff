from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from app.misc.config import settings

'''
is_persistent - не убирается после нажатия на кнопку, остаётся статичной всегда
resize_keyboard - уменьшает размер клавиатуры
input_field_placeholder - то, что будет отображаться в поле ввода сообщения (указывать в кавычках "" / '')
'''

send_geolocation = ReplyKeyboardMarkup(keyboard=[
    # Запрашиваем местоположение
    [KeyboardButton(text='Отправить местоположение', request_location=True)]
], is_persistent=True, resize_keyboard=True, input_field_placeholder=None)

ends_work = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Завершить работу')]
], is_persistent=True, resize_keyboard=True, input_field_placeholder=None)

# Отмена при ручном вводе позиции
decline_work_starts = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Отменить')]
], is_persistent=True, resize_keyboard=True, input_field_placeholder=None)


def worker_menu(user_id: int | None = None):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='Начать работу')]
    ], is_persistent=True, resize_keyboard=True, input_field_placeholder=None)

    if user_id in settings.ADMIN_IDS:
        kb.keyboard.append([KeyboardButton(text='Административная панель')])

    return kb


back_action = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Отменить действие')]
], is_persistent=True, resize_keyboard=True, input_field_placeholder=None)
