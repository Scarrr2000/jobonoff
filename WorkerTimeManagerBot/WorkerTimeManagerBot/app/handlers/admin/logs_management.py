import os.path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

router = Router()


@router.callback_query(F.data == 'get_txt_private_logs')
async def get_txt_private_logs(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer_document(FSInputFile(path=os.path.abspath('private_logs.txt'),
                                                       filename='private_logs.txt'))