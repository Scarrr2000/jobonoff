from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Управление работниками', callback_data='workers_management')],
    [InlineKeyboardButton(text='Управление сессиями', callback_data='sessions_management')],
    [InlineKeyboardButton(text='Получить .txt логов', callback_data='get_txt_private_logs')],
])


def edit_session_kb(session_id: int, telegram_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить ставку работника", callback_data=f"change_rate:{session_id}")],
        [InlineKeyboardButton(text='Изменить время начала', callback_data=f'edit_sis_starts_time:{session_id}')],
        [InlineKeyboardButton(text='Изменить время конца', callback_data=f'edit_sis_end_time:{session_id}')],
        [InlineKeyboardButton(text='Завершить сессию', callback_data=f'end_work_session:{session_id}')],
        [InlineKeyboardButton(text='Удалить сессию навсегда', callback_data=f'delete_session:{session_id}')],
    ])


def worker_user_editor(telegram_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сессии пользователя", callback_data=f"user_sessions:{telegram_id}")]
    ])


def worker_editor_panel(session_id: int, telegram_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить ставку работника", callback_data=f"change_rate:{session_id}")],
        [InlineKeyboardButton(text='Изменить время начала сессии', callback_data=f'edit_sis_starts_time:{session_id}')],
        [InlineKeyboardButton(text='Завершить сессию', callback_data=f'end_work_session:{session_id}')],
        [InlineKeyboardButton(text='Удалить сессию навсегда', callback_data=f'delete_session:{session_id}')],
    ])
