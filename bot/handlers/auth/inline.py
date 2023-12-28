import logging
import traceback
from typing import Any
from aiogram import Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas, models

logger = logging.getLogger( __name__ )

class InlineAuthController:

    bot: variables.Bot = None
    router: Router = None
    core: Any

    def __init__( self, core: Any, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.core = core
        self.router = Router()
        #
        self.router.message.register( self._login, variables.AuthForm.login )
        self.router.message.register( self._password, variables.AuthForm.password )
        #
        dispatcher.include_router( self.router )


    async def _init( self, message: types.Message, user: models.User, site: str, state: FSMContext ) -> None:
        await state.set_state(variables.AuthForm.login)

        builder = InlineKeyboardBuilder()
        builder.button( text="Отмена", callback_data=f"auth:cancel" )
        builder.adjust(1, repeat=True)

        await self.bot.edit_message_text( chat_id=message.chat.id, message_id=message.message_id, text=f'Выбран сайт {site}\n\n!!!ВХОД ЧЕРЕЗ СОЦ. СЕТИ НЕВОЗМОЖЕН!!!', reply_markup=builder.as_markup())

        msg = await self.bot.send_message( chat_id=message.chat.id, text=f'Отправьте сообщением логин')
        await state.update_data(last_message=msg.message_id)

    async def _login( self, message: types.Message, state: FSMContext ) -> None:

        login = message.text.strip()

        await self.bot.delete_message( chat_id=message.chat.id, message_id=message.message_id )

        if not login.startswith('/') and not login.startswith('http:') and not login.startswith('https:'):

            await state.update_data(login=login)
        
            auth = await state.get_data()
            await self.bot.delete_message( chat_id=message.chat.id, message_id=auth['last_message'] )

            await state.set_state(variables.AuthForm.password)

            msg = await self.bot.send_message( chat_id=message.chat.id, text=f'Отправьте сообщением пароль' )
            await state.update_data(last_message=msg.message_id)

    async def _password( self, message: types.Message, state: FSMContext ) -> None:

        password = message.text #.strip()

        await self.bot.delete_message( chat_id=message.chat.id, message_id=message.message_id )

        if not password.startswith('/') and not password.startswith('http:') and not password.startswith('https:'):

            await state.update_data(password=password)
        
            auth = await state.get_data()
            await self.bot.delete_message( chat_id=message.chat.id, message_id=auth['last_message'] )

            await state.clear()

            if auth and 'base_message' in auth and auth['base_message']:    
                try:
                    await self.bot.delete_message( chat_id=message.chat.id, message_id=auth['base_message'] )
                except:
                    pass

            if auth and 'last_message' in auth and auth['last_message']:
                try:
                    await self.bot.delete_message( chat_id=message.chat.id, message_id=auth['last_message'] )
                except:
                    pass

            await self.bot.DB.saveUserAuth( user_id=message.from_user.id, site=auth['site'], login=auth['login'], password=auth['password'] )

            await self.bot.send_message( chat_id=message.chat.id, text=f'Авторизация для сайта {auth["site"]} сохранена', reply_markup=None)