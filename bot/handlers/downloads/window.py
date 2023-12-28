import logging
import ujson
import urllib
import traceback
from typing import Any
from cryptography.fernet import Fernet
from aiogram import Dispatcher, Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas, models

logger = logging.getLogger( __name__ )

class WindowDownloadsController:

    bot: variables.Bot = None
    router: Router = None
    core: Any

    def __init__( self, core: Any, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.core = core
        self.router = Router()
        #
        self.router.callback_query.register( self._cancel, F.data=='wdc:cancel' )
        self.router.message.register( self._pre_start, lambda message: message.content_type == 'web_app_data' and 'web_app_download' in message.web_app_data.data )
        #
        dispatcher.include_router( self.router )


    async def _cancel( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()
        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )


    async def _init( self, message: types.Message, user: models.User, link: str, site: str, site_parameters: list[str], site_formats: list[str] ) -> None:

        use_paging = False
        use_auth = {}
        use_images = False
        force_images = False

        if "auth" in site_parameters:
            uas = await self.bot.DB.getUserAuthsForSite( user_id=user.id, site=site )
            demo_login = True if site in self.bot.CNF.demo else False
            if uas:
                for ua in uas:
                    use_auth[ str(ua.id) ] = ua.get_name()
            if demo_login:
                use_auth[ 'anon' ] = 'Анонимные доступы'
            use_auth[ 'none' ] = 'Без авторизации'

        if "paging" in site_parameters:
            use_paging = True

        if "images" in site_parameters:
            use_images = True

        if "force_images" in site_parameters:
            force_images = True
            use_images = False
        
        _format = user.format
        if not _format or _format not in site_formats:
            _format = None

        data = {
            'user_id': message.from_user.id,
            'chat_id': message.chat.id,
            'link': link,
            'site': site,
			'formats': site_formats,
			'format': _format,
			'images': user.images,
            'force_images': force_images,
			'cover': user.cover,
			'use_auth': use_auth,
			'use_paging': use_paging,
			'use_images': use_images,
			'use_cover': True,
        }


        builder = InlineKeyboardBuilder()
        builder.button( text="Скачать", callback_data="_" )
        builder.button( text="Отмена", callback_data="_" )
        builder.adjust(1, repeat=True)

        # initial message
        resp = await self.bot.send_message( chat_id=message.chat.id, reply_to_message_id=message.message_id, text='Подготовка к скачиванию\n\nНажмите "Скачать" или "Отмена"', reply_markup=builder.as_markup() )

        data[ 'message_id' ] = resp.message_id
        fernet = Fernet( self.bot.EncryptKey )
        encrypted = fernet.encrypt( ujson.dumps(data).encode('utf-8') )
        web_app = types.WebAppInfo( url=self.bot.CNF.bot_host + 'download/setup?payload=' + urllib.parse.quote_plus( encrypted.decode('utf-8') ) )

        builder = InlineKeyboardBuilder()
        builder.button( text="Скачать", web_app=web_app )
        builder.button( text="Отмена", callback_data="wdc:cancel" )
        builder.adjust(1, repeat=True)

        # final message
        await self.bot.edit_message_reply_markup( chat_id=resp.chat.id, message_id=resp.message_id, reply_markup=builder.as_markup() )

    async def _pre_start( self, message: types.Message ) -> None:
        data = ujson.loads( message.web_app_data.data )
        data['user_id'] = message.from_user.id
        data['chat_id'] = message.chat.id
        payload = schemas.DownloadSetupRequest( **data )

        await self._start(payload)

    async def _start( self, payload: schemas.DownloadSetupRequest ) -> None:
        login = None
        password = None

        if payload.auth == 'anon':
            if payload.site in self.bot.CNF.demo:
                demo_login = self.bot.CNF.demo[ payload.site ]
                login = demo_login[ 'login' ]
                password = demo_login[ 'password' ]
        elif payload.auth != 'none':
            uas = await self.bot.DB.getUserAuth( user_id=payload.user_id, auth_id=int( payload.auth ) )
            login = uas.login
            password = uas.password

        req = schemas.DownloadRequest(
            bot_id = "test",
            user_id = payload.user_id,
            chat_id = payload.chat_id,
            message_id = payload.message_id,
            site = payload.site,
            url = payload.link,
            start = payload.start,
            end = payload.end,
            format = payload.format,
            images = payload.images,
            cover = payload.cover,
            login = login,
            password = password,
            proxy = ""
        )

        try:
            await self.core.pass_to_queue( req )
        except:
            traceback.print_exc()