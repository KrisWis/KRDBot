from aiogram import types
from InstanceBot import router
from aiogram.fsm.context import FSMContext
from utils import userWhatsNewTexts, adminWhatIsNewTexts, globalTexts
from keyboards import adminKeyboards
from database.orm import AsyncORM
from helpers import sendPaginationMessage, mediaGroupSend, albumInfoProcess, deleteSendedMediaGroup
from states.Admin import WhatIsNewStates
from RunBot import logger
import datetime
from aiogram.filters import StateFilter
from InstanceBot import bot
import re


'''Что нового?'''
# Отправка сообщения со меню выбора "Что нового?"
async def send_what_is_new_selection_menu(call: types.CallbackQuery, state: FSMContext) -> None:
    
    await deleteSendedMediaGroup(state, call.from_user.id)

    await call.message.edit_text(userWhatsNewTexts.what_is_new_choice_text,
    reply_markup=await adminKeyboards.what_is_new_selection_menu_kb())


# Отправка сообщения со всеми новостями команды
async def send_team_news(call: types.CallbackQuery, state: FSMContext) -> None:
    team_news = await AsyncORM.get_team_news()
    prefix = "admin_team_news"

    async def getTeamNewsButtonsAndAmount():
        team_news = await AsyncORM.get_team_news()

        buttons = [[types.InlineKeyboardButton(
        text=team_news_item.name,
        callback_data=f'{prefix}|{team_news_item.id}')] for team_news_item in team_news]

        return [buttons, len(team_news)]
    
    await sendPaginationMessage(call, state, team_news, getTeamNewsButtonsAndAmount,
    prefix, userWhatsNewTexts.team_news_text, 10, [await adminKeyboards.get_kb_addButton('team_news'), 
    await adminKeyboards.get_team_news_kb_backToSelectionMenuButton()])


# Отправка сообщения о том, чтобы администратор прислал название новости
async def wait_team_news_item_name(call: types.CallbackQuery, state: FSMContext) -> None:
    await call.message.edit_text(adminWhatIsNewTexts.wait_team_news_name_text)

    await state.set_state(WhatIsNewStates.wait_name)


# Ожидание названия новости команды. Отправка сообщения о том, чтобы администратор прислал информацию о новости
async def wait_team_news_item_info(message: types.Message, state: FSMContext):
    team_news_item_name = message.text

    if team_news_item_name:
        team_news_item = await AsyncORM.get_team_news_item_by_name(team_news_item_name)

        if not team_news_item:
            await state.update_data(team_news_item_name=team_news_item_name)

            await message.answer(adminWhatIsNewTexts.wait_team_news_info_text)

            await state.set_state(WhatIsNewStates.wait_info)

        else:
            await message.answer(globalTexts.adding_data_error_text)
    else:
        await message.answer(globalTexts.data_isInvalid_text)


# Ожидание информации новости команды. Добавление новости в базу данных
async def add_team_news_item(message: types.Message, album: list[types.Message] = [], state: FSMContext = None):
    result = await albumInfoProcess(WhatIsNewStates.wait_info, state, message, album)

    if not result:
        await message.answer(globalTexts.data_isInvalid_text)
        return

    user_text = result[0]
    photo_file_ids = result[1]
    video_file_ids = result[2]
    now = datetime.datetime.now()
    data = await state.get_data()

    if "team_news_item_replace_id" in data:
        team_news_item_replace_id = int(data["team_news_item_replace_id"])

        await AsyncORM.change_team_news_item_info(team_news_item_replace_id,
        user_text, photo_file_ids, video_file_ids)

        team_news_item = await AsyncORM.get_team_news_item_by_id(team_news_item_replace_id)

        await message.answer(adminWhatIsNewTexts.change_team_news_success_text
        .format(team_news_item.name), reply_markup=await adminKeyboards.back_to_admin_menu_kb())
    else:
        try:
            await AsyncORM.add_team_news_item(data["team_news_item_name"], now, user_text, photo_file_ids, video_file_ids)

            await message.answer(adminWhatIsNewTexts.add_team_news_success_text,
            reply_markup=await adminKeyboards.back_to_admin_menu_kb())
        except Exception as e:
            logger.info(e)
            await message.answer(globalTexts.adding_data_error_text)

    await state.clear()


# Отправка сообщения с информацией о новости и возможностью удаления/изменения информации
async def show_team_news_item(call: types.CallbackQuery, state: FSMContext) -> None:
    user_id = call.from_user.id
    message_id = call.message.message_id

    await bot.delete_message(user_id, message_id)

    temp = call.data.split("|")

    team_news_item_id = int(temp[1])

    team_news_item = await AsyncORM.get_team_news_item_by_id(team_news_item_id)

    if team_news_item:
        await mediaGroupSend(call, state, team_news_item.photo_file_ids, team_news_item.video_file_ids)

        answer_message_text = userWhatsNewTexts.show_team_news_withoutText_text.format(team_news_item.name)

        if team_news_item.text:
            if not team_news_item.photo_file_ids and not team_news_item.video_file_ids:
                answer_message_text = userWhatsNewTexts.show_team_news_text.format(team_news_item.name, team_news_item.text)
            else:
                answer_message_text = userWhatsNewTexts.show_team_news_withImages_text.format(team_news_item.name, team_news_item.text)

        await call.message.answer(answer_message_text,
        reply_markup=await adminKeyboards.actions_kb(team_news_item.id, 'team_news'))
    else:
        await call.message.answer(globalTexts.data_notFound_text)


# Обработка изменения/удаления информации о новости команды
async def team_news_item_actions(call: types.CallbackQuery, state: FSMContext) -> None:

    temp = call.data.split("|")

    team_news_item_id = int(temp[1])

    action = temp[2]

    team_news_item = await AsyncORM.get_team_news_item_by_id(team_news_item_id)

    if not team_news_item:
        await call.message.answer(globalTexts.data_notFound_text)
        return
    
    if action == "replace":
        await call.message.edit_text(adminWhatIsNewTexts.team_news_actions_edit_text)
        await state.update_data(team_news_item_replace_id=team_news_item_id)

        await state.set_state(WhatIsNewStates.wait_info)

    elif action == "delete":
        await call.message.edit_text(adminWhatIsNewTexts.team_news_actions_delete_confirmation_text.
        format(team_news_item.name),
        reply_markup=await adminKeyboards.delete_confirmation_kb(team_news_item.id, 'team_news'))


# Обработка подтверждения/отклонения удаления информации о новости команды
async def team_news_item_delete_confirmation(call: types.CallbackQuery) -> None:

    temp = call.data.split("|")

    team_news_item_id = int(temp[1])

    action = temp[3]

    team_news_item = await AsyncORM.get_team_news_item_by_id(team_news_item_id)

    if not team_news_item:
        await call.message.answer(globalTexts.data_notFound_text)
        return
    
    if action == "yes":
        await AsyncORM.delete_team_news_item(team_news_item_id)

        await call.message.edit_text(adminWhatIsNewTexts.team_news_actions_delete_confirmation_yes_text.
        format(team_news_item.name), reply_markup=await adminKeyboards.back_to_selection_menu_kb('what_is_new'))

    elif action == "no":
        await call.message.edit_text(adminWhatIsNewTexts.team_news_actions_delete_confirmation_no_text.
        format(team_news_item.name), reply_markup=await adminKeyboards.back_to_selection_menu_kb('what_is_new'))
'''/Что нового?/'''


def hand_add():
    '''Что нового?'''
    router.callback_query.register(send_what_is_new_selection_menu, lambda c: c.data == 'admin|what_is_new')

    router.callback_query.register(send_team_news, lambda c: c.data == 'admin|what_is_new|team_news')
    
    router.callback_query.register(wait_team_news_item_name, lambda c: c.data == 'admin|team_news|add')

    router.message.register(wait_team_news_item_info, StateFilter(WhatIsNewStates.wait_name))

    router.message.register(add_team_news_item, StateFilter(WhatIsNewStates.wait_info))

    router.callback_query.register(show_team_news_item, lambda c: 
    re.match(r"^admin_team_news\|(?P<team_news_item_id>\d+)$", c.data))

    router.callback_query.register(team_news_item_actions, lambda c: 
    re.match(r"^team_news\|(?P<team_news_item_id>\d+)\|(?P<action>replace|delete)$", c.data))

    router.callback_query.register(team_news_item_delete_confirmation, lambda c: 
    re.match(r"^team_news\|(?P<team_news_item_id>\d+)\|delete\|(?P<choice>yes|no)$", c.data))
    '''/Что нового?/'''