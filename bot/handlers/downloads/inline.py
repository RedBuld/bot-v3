import logging
import traceback
from typing import Any
from aiogram import Dispatcher, Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas, models

logger = logging.getLogger( __name__ )

class InlineDownloadsController:

    bot: variables.Bot = None
    router: Router = None
    core: Any

    def __init__( self, core: Any, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.core = core
        self.router = Router()
        #
        self.router.callback_query.register( self._cancel, F.data=='idc:cancel' )
        self.router.callback_query.register( self._start, F.data=='idc:download' )
        #
        self.router.callback_query.register( self._setup_cover, F.data=='idc:cover' )
        self.router.callback_query.register( self._setup_images, F.data=='idc:images' )
        self.router.callback_query.register( self._setup_format, F.data=='idc:format' )
        self.router.callback_query.register( self._setup_format_apply, F.data.startswith('idc:format:') )
        self.router.callback_query.register( self._setup_auth, F.data=='idc:auth' )
        self.router.callback_query.register( self._setup_auth_apply, F.data.startswith('idc:auth:') )
        self.router.callback_query.register( self._setup_paging, F.data=='idc:paging' )
        self.router.message.register( self._setup_paging_apply, lambda message: message.reply_to_message is not None )
        #
        dispatcher.include_router( self.router )


    async def _cancel( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()
        await self.bot.DB.deleteInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )


    async def _init( self, message: types.Message, user: models.User, link: str, site: str, site_parameters: list[str], site_formats: list[str] ) -> None:
        request = models.InlineDownloadRequest()
        
        request.user_id = message.from_user.id
        request.chat_id = message.chat.id

        if "auth" in site_parameters:
            request.use_auth = True
            uas = await self.bot.DB.getUserAuthsForSite( user_id=user.id, site=site )
            if uas and len(uas) > 0:
                for ua in uas:
                    request.auth = str(ua.id)
                    break
            elif site in self.bot.CNF.demo:
                request.auth = 'anon'
            else:
                request.auth = 'none'
        else:
            request.auth = 'none'

        if "paging" in site_parameters:
            request.use_paging = True

        if "images" in site_parameters:
            request.use_images = True

        if "force_images" in site_parameters:
            request.force_images = True
            request.use_images = False
        
        request.link = link
        request.site = site

        request.format = user.format
        if not request.format or request.format not in site_formats:
            request.format = site_formats[0]

        request.cover = user.cover
        request.images = user.images

        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.send_message( chat_id=message.chat.id, text="Произошла ошибка" )
            return

        # initial message
        resp = await self.bot.send_message( chat_id=message.chat.id, reply_to_message_id=message.message_id, text='Подготовка к скачиванию' )
        request.message_id = resp.message_id

        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.edit_message_text( chat_id=message.chat.id, message_id=resp.message_id, text="Произошла ошибка" )
            return

        await self._update_inline(request)


    async def _start( self, callback_query: types.CallbackQuery ) -> None:
        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return

        login = None
        password = None

        if request.auth == 'anon':
            if request.site in self.bot.CNF.demo:
                demo_login = self.bot.CNF.demo[ request.site ]
                login = demo_login[ 'login' ]
                password = demo_login[ 'password' ]
        elif request.auth != 'none':
            uas = await self.bot.DB.getUserAuth( user_id=request.user_id, auth_id=int( request.auth ) )
            login = uas.login
            password = uas.password

        req = schemas.DownloadRequest(
            bot_id = "test",
            user_id = request.user_id,
            chat_id = request.chat_id,
            message_id = request.message_id,
            site = request.site,
            url = request.link,
            start = request.start,
            end = request.end,
            format = request.format,
            images = request.images,
            cover = request.cover,
            login = login,
            password = password,
            proxy = ""
        )

        # await self.bot.delete_message( chat_id=request.chat_id, message_id=request.message_id )
        try:
            await self.core.pass_to_queue( req )
        except:
            traceback.print_exc()


    async def _setup_cover( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        request.cover = not request.cover
        
        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка" )
            return

        await self._update_inline(request)


    async def _setup_images( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        request.images = not request.images
        
        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка" )
            return

        await self._update_inline(request)


    async def _setup_auth( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        demo_login = True if request.site in self.bot.CNF.demo else False
        uas = await self.bot.DB.getUserAuthsForSite( user_id=request.user_id, site=request.site )

        builder = InlineKeyboardBuilder()
        for ua in uas:
            builder.button( text=ua.get_name(), callback_data='idc:auth:'+str(ua.id))
        if demo_login:
            builder.button( text='Анонимные доступы', callback_data='idc:auth:anon')
        builder.button( text='Без авторизации', callback_data='idc:auth:none')
        
        builder.adjust( 1, repeat=True )

        await self.bot.edit_message_text( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text="Выберите доступы", reply_markup=builder.as_markup() )


    async def _setup_auth_apply( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        auth = callback_query.data.split('idc:auth:')[1]

        request.auth = auth
        
        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка" )
            return

        await self._update_inline(request)


    async def _setup_format( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        site_allowed, site_parameters, site_formats = await self.core.get_site_data( request.site )

        builder = InlineKeyboardBuilder()
        for site_format in site_formats:
            if site_format in self.bot.CNF.formats:
                builder.button( text=self.bot.CNF.formats[site_format], callback_data='idc:format:'+str(site_format))
        
        builder.adjust( 1, repeat=True )

        await self.bot.edit_message_text( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text="Выберите доступы", reply_markup=builder.as_markup() )


    async def _setup_format_apply( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return
        
        format = callback_query.data.split('idc:format:')[1]

        request.format = format
        
        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка" )
            return

        await self._update_inline(request)


    async def _setup_paging( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        request = await self.bot.DB.getInlineDownloadRequest(user_id=callback_query.from_user.id,chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        if not request:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Произошла ошибка: запрос не найден", reply_markup=None )
            return

        await self.bot.edit_message_text( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id, text="Отправьте ПАРУ ЧИСЕЛ через пробел _ответом_ на данное сообшение\\.\n`0 0` \\- для отмены\n\nПример: `0 0`, `0 150`, `-30 0`, `0 -50`", parse_mode="MarkdownV2" )

    async def _setup_paging_apply( self, message: types.Message ) -> None:
        await self.bot.delete_message( chat_id=message.chat.id, message_id=message.message_id )

        request = await self.bot.DB.getInlineDownloadRequest(user_id=message.from_user.id,chat_id=message.reply_to_message.chat.id, message_id=message.reply_to_message.message_id)
        if not request:
            await self.bot.send_message( chat_id=message.reply_to_message.chat.id, text="Произошла ошибка: запрос не найден. Возможно вы пытаетесь ответить не на свое сообщение", reply_markup=None )
            return

        numbers = message.text

        err = False

        try:
            numbers = numbers.split(None,2)
            request.start = int( numbers[0] )
            request.end = int( numbers[1] )
        except:
            err = True
            pass

        try:
            request = await self.bot.DB.saveInlineDownloadRequest(request)
        except:
            await self.bot.edit_message_text( chat_id=message.reply_to_message.chat.id, message_id=message.reply_to_message.message_id, text="Произошла ошибка" )
            return

        if not err:
            await self._update_inline(request)


    async def _update_inline( self, request: models.InlineDownloadRequest ) -> None:
        builder = InlineKeyboardBuilder()
        # ❎ ✅ 🟩 ☐ ☑
        builder.button( text="Обложка: Да" if request.cover else "Обложка: Нет", callback_data="idc:cover" )

        if request.use_images:
            builder.button( text="Картинки: Да" if request.images else "Картинки: Нет", callback_data="idc:images" )

        if request.use_auth:
            auth = ''
            if request.auth == 'none':
                auth = 'Без авторизации'
            elif request.auth == 'anon':
                auth = 'Анонимные доступы'
            elif request.auth:
                uas = await self.bot.DB.getUserAuth( user_id=request.user_id, auth_id=int( request.auth ) )
                if uas:
                    auth = uas.get_name()
            builder.button( text='Авторизация: ' + auth, callback_data="idc:auth" )
        
        if request.format in self.bot.CNF.formats:
            builder.button( text='Формат: '+ self.bot.CNF.formats[request.format], callback_data="idc:format" )

        if request.use_paging:
            if request.start == 0 and request.end == 0:
                paging = 'Скачивать все главы'
            else:
                _humane = await self.__human_chapters(request.start,request.end)
                paging = f'Скачивать {_humane}'
            builder.button( text=paging, callback_data="idc:paging" )

        builder.button( text="Скачать", callback_data="idc:download" )
        builder.button( text="Отмена", callback_data="idc:cancel" )
        
        builder.adjust( 1, repeat=True )

        await self.bot.edit_message_text( chat_id=request.chat_id, message_id=request.message_id, text='Подготовка к скачиванию', reply_markup=builder.as_markup() )
    

    async def __human_chapters(self, _start:int, _end:int) -> str:
        res = ''
        if _start and _end:
            if _start > 0 and _end > 0:
                res = f'с {_start} главы до {_end} главы'
            elif _start > 0 and _end < 0:
                if _end == -1:
                    res = f'с {_start} главы, без последней главы'
                else:
                    res = f'с {_start} главы, без последних {abs(_end)} глав'
        elif _start and not _end:
            if _start > 0:
                res = f'с {_start} главы и до конца'
            else:
                if _start == -1:
                    res = f'последнюю главу'
                else:
                    res = f'последние {abs(_start)} глав'
        elif _end and not _start:
            if _end > 0:
                res = f'с начала, до {_end} главы'
            else:
                if _end == -1:
                    res = f'с начала, без последней главы'
                else:
                    res = f'с начала, без последних {abs(_end)} глав'
        return res