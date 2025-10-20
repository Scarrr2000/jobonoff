# Этот файл является модульным представлением всех групп состояний для их удобного хранения и использования

from aiogram.fsm.state import StatesGroup, State


class ProcessWorkerSession(StatesGroup):
    GET_GEOLOCATION = State()  # Aiogram location type -> int + int (latitude, longitude)
    GET_EXACT_POSITION_MANUALLY = State()  # Ручной ввод позиции местоположения


class AdminStates(StatesGroup):
    waiting_for_start_time = State()
    waiting_for_end_time = State()
