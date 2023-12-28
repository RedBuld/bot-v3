import logging
import ujson
import urllib
import traceback
from typing import Any
from cryptography.fernet import Fernet
from aiogram import Dispatcher, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas, models

logger = logging.getLogger( __name__ )

class WindowAuthController:

    bot: variables.Bot = None
    router: Router = None
    core: Any

    def __init__( self, core: Any, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.core = core
        self.router = Router()
        #
        self.router.callback_query.register( self._cancel, F.data=='wac:cancel' )
        self.router.message.register( self._pre_save, lambda message: message.content_type == 'web_app_data' and 'web_app_auth' in message.web_app_data.data )
        #
        dispatcher.include_router( self.router )


    async def _cancel( self, callback_query: types.CallbackQuery, state: FSMContext ) -> None:
        await callback_query.answer()
        await state.clear()
        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )


    async def _init( self, message: types.Message, user: models.User, site: str ) -> None:

        data = {
            'site': site,
        }

        fernet = Fernet( self.bot.EncryptKey )
        encrypted = fernet.encrypt( ujson.dumps(data).encode('utf-8') )
        web_app = types.WebAppInfo( url=self.bot.CNF.bot_host + 'auth/setup?payload=' + urllib.parse.quote_plus( encrypted.decode('utf-8') ) )

        builder = InlineKeyboardBuilder()
        builder.button( text="Добавить", web_app=web_app )
        builder.button( text="Отмена", callback_data="wac:cancel" )
        builder.adjust(1, repeat=True)

        await self.bot.edit_message_text( chat_id=message.chat.id, message_id=message.message_id, text=f'Добавление авторизации для сайта {site}', reply_markup=builder.as_markup() )


    async def _pre_save( self, message: types.Message ) -> None:
        data = ujson.loads( message.web_app_data.data )
        payload = schemas.AuthRequest( **data )

        print( payload )