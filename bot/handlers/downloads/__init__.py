import os
import asyncio
import logging
import ujson
import aiohttp
import re
import traceback
from aiogram import Dispatcher, Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas

from .window import WindowDownloadsController
from .inline import InlineDownloadsController


logger = logging.getLogger( __name__ )

class DownloadsController:

    bot: variables.Bot = None
    router: Router = None
    mask: re = re.compile("https?:\/\/(www\.|m\.)*(?P<site>[^\/]+)\/.+")

    wdc: WindowDownloadsController
    idc: InlineDownloadsController

    def __init__( self, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.router = Router()
        #
        self.wdc = WindowDownloadsController(self, bot, dispatcher)
        self.idc = InlineDownloadsController(self, bot, dispatcher)
        #
        self.router.message.register( self._init, F.content_type.in_( {'text'} ) & ~F.text.startswith( '/' ) & ( F.text.contains( 'http://' ) | F.text.contains( 'https://' ) ) )
        self.router.callback_query.register( self._cancel, F.data.startswith('cancel_task:') )
        #
        dispatcher.include_router( self.router )


    async def get_site_data( self, site_name: str ):
        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot.CNF.queue_host + 'sites/check', json=schemas.SiteCheckRequest(site = site_name).model_dump(), verify_ssl=False ) as response:
                if response.status == 200:
                    data = await response.json( loads=ujson.loads )
                    res = schemas.SiteCheckResponse( **data )
                    return res.allowed, res.parameters, res.formats


    async def pass_to_queue( self, req: schemas.DownloadRequest ) -> None:
        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot.CNF.queue_host + 'download/new', json=req.model_dump(), verify_ssl=False ) as response:
                if response.status == 200:
                    task_id = await response.json( loads=ujson.loads )
                    builder = InlineKeyboardBuilder()
                    builder.button( text="Отмена", callback_data=f"cancel_task:{task_id}" )
                    await self.bot.edit_message_text( chat_id=req.chat_id, message_id=req.message_id, text='Загрузка добавлена в очередь', reply_markup=builder.as_markup(), disable_web_page_preview=True )
                else:
                    message = await response.json( loads=ujson.loads )
                    await self.bot.edit_message_text( chat_id=req.chat_id, message_id=req.message_id, text=message, reply_markup=None, disable_web_page_preview=True )


    async def _cancel( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()
        task_id = int( callback_query.data.split('cancel_task:')[1] )
        req = schemas.DownloadCancel(
            task_id = task_id
        )
        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot.CNF.queue_host + 'download/cancel', json=req.model_dump(), verify_ssl=False ) as response:
                await session.close()


    async def _init( self, message: types.Message ) -> None:

        user = await self.bot.DB.getUser( user_id=message.from_user.id )

        if not user or not user.setuped:
            await self.bot.send_message( chat_id=message.chat.id, text="Завершите настройку" )
            return

        usage = await self.bot.DB.getUserUsage( user_id=message.from_user.id )
        if usage >= self.bot.CNF.free_limit:
            await self.bot.send_message( chat_id=message.chat.id, text="Лимит загрузок исчерпан" )
            return

        # check_user_banned = await bot.db.check_user_banned(message.from_user.id)
        # if check_user_banned:
        # 	await bot.messages_queue.add( callee='send_message', chat_id=message.chat.id, text=f'Вы были заблокированы. Причина: {check_user_banned.reason}. Срок: {check_user_banned.until}' )
        # 	return

        ##################

        link: str = ''
        site: str = ''
        site_parameters: list[str] = []
        site_formats: list[str] = []

        found_links = False
        for entity in message.entities:
            if entity.type == 'url':
                link = message.text[ entity.offset : entity.length ]
                site_m = self.mask.match( link )
                if site_m:
                    site = site_m.group('site')
                    site_allowed, site_parameters, site_formats = await self.get_site_data( site )
                    if site_allowed:
                        found_links = True
                        break

        if not found_links:
            await self.bot.send_message( chat_id=message.chat.id, text="Не найдено подходящих ссылок" )
            return
        
        if not site_formats:
            logger.info('\n\n\nНет форматов')
            logger.info(site)
            logger.info(site_formats)
            logger.info('\n\n\n')
            await self.bot.send_message( chat_id=message.chat.id, text="Ошибка: не найдены доступные форматы" )
            return

        if user.interact_mode == 0:
            await self.idc._init( message, user, link, site, site_parameters, site_formats )
        elif user.interact_mode == 1:
            await self.wdc._init( message, user, link, site, site_parameters, site_formats )


    # external


    async def download_status( self, status: schemas.DownloadStatus ) -> bool:
        logger.info( 'download_status' + str( status.model_dump() ) )
        reply_markup = None
        if status.status != variables.DownloaderStep.ERROR and status.status != variables.DownloaderStep.CANCELLED and status.status != variables.DownloaderStep.DONE:
            builder = InlineKeyboardBuilder()
            builder.button( text="Отмена", callback_data=f"cancel_task:{status.task_id}" )
            reply_markup = builder.as_markup()
        try:
            await self.bot.edit_message_text( chat_id=status.chat_id, message_id=status.message_id, text=status.text, reply_markup=reply_markup, disable_web_page_preview=True )
        except:
            traceback.print_exc()
            pass
        return True


    async def download_done( self, result: schemas.DownloadResult ) -> bool:
        logger.info( 'download_done' + str( result.model_dump() ) )

        try:
            await self.bot.delete_message( chat_id=result.chat_id, message_id=result.message_id )
        except:
            pass

        try:
            if result.status == variables.DownloaderStep.ERROR or result.status == variables.DownloaderStep.CANCELLED:
                if result.status == variables.DownloaderStep.CANCELLED and result.text == '':
                    result.text = 'Загрузка отменена'
                await self.bot.send_message( chat_id=result.chat_id, text=result.text, parse_mode='MarkdownV2' )
            else:
                if result.cover:
                    try:
                        if os.path.exists(result.cover):
                            await self.bot.send_photo( chat_id=result.chat_id, photo=types.FSInputFile( result.cover ), request_timeout=600000 )
                            await asyncio.sleep( 1 )
                    except:
                        pass
                if result.files:
                    if len(result.files) > 1:
                        await self.bot.send_message( chat_id=result.chat_id, text=result.text, parse_mode='MarkdownV2' )
                        for file in result.files:
                            if os.path.exists(file):
                                await self.bot.send_document( chat_id=result.chat_id, document=types.FSInputFile( file ), request_timeout=600000 )
                                await asyncio.sleep( 1 )
                    else:
                        for file in result.files:
                            if os.path.exists(file):
                                await self.bot.send_document( chat_id=result.chat_id, document=types.FSInputFile( file ), caption=result.text, parse_mode='MarkdownV2', request_timeout=600000 )
                                await asyncio.sleep( 1 )
        except:
            traceback.print_exc()
            return False
        return True