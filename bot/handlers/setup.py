import os
import logging
from aiogram import Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import models, variables, schemas

logger = logging.getLogger( __name__ )

class SetupController:

    bot: variables.Bot = None
    router: Router = None

    def __init__( self, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.router = Router()
        self.router.message.register( self.start_command, Command( commands='start' ) )
        self.router.message.register( self.setup_command, Command( commands='setup' ) )
        self.router.callback_query.register( self._setup_start, F.data=='setup:start' )
        self.router.callback_query.register( self._setup_cancel, F.data=='setup:cancel' )
        #
        self.router.callback_query.register( self._setup_mode, F.data=='setup:mode' )
        self.router.callback_query.register( self._setup_format, F.data=='setup:format' )
        self.router.callback_query.register( self._setup_cover, F.data=='setup:cover' )
        self.router.callback_query.register( self._setup_images, F.data=='setup:images' )
        #
        self.router.callback_query.register( self._setup_mode_save, F.data.startswith('setup:mode:') )
        self.router.callback_query.register( self._setup_format_save, F.data.startswith('setup:format:') )
        self.router.callback_query.register( self._setup_cover_save, F.data.startswith('setup:cover:') )
        self.router.callback_query.register( self._setup_images_save, F.data.startswith('setup:images:') )
        #
        dispatcher.include_router( self.router )

    async def start_command( self, message: types.Message ) -> None:

        if message.from_user.is_bot != False:
            return

        user = await self.bot.DB.getUser( message.from_user.id )

        uname = message.from_user.username
        if not uname:
            uname = message.from_user.first_name

        if not user:
            user = models.User(
                id=message.from_user.id,
                username=uname
            )
            await self.bot.DB.saveUser(user)
        user = await self.bot.DB.getUser( message.from_user.id )

        if not user:
            logger.info('\n\n\nstart')
            logger.info(message)
            logger.info('\n\n\n')
            return await self.bot.send_message( chat_id=message.chat.id, text="Ошибка: пользователь не найден, нажмите /start, нажмите /start" )

        uname = self.bot.__escape_md__(uname)
        text = f"Привет, {uname}\. Проведем настройку\?"
        if not user.setuped:
            text += "\n\n_В первый раз необходимо завершить настройку до конца_"

        builder = InlineKeyboardBuilder()
        builder.button( text="Да", callback_data=f"setup:start" )
        builder.button( text="Нет", callback_data=f"setup:cancel" )
        builder.adjust(1, repeat=True)

        await self.bot.send_message( chat_id=message.chat.id, text=text, parse_mode='MarkdownV2', reply_markup=builder.as_markup() )
    
    async def setup_command( self, message: types.Message ) -> None:

        text = "Что настроим?"

        builder = InlineKeyboardBuilder()
        builder.button( text="Режим взаимодействия", callback_data="setup:mode" )
        builder.button( text="Формат", callback_data="setup:format" )
        builder.button( text="Обложка", callback_data="setup:cover" )
        builder.button( text="Изображения", callback_data="setup:images" )
        builder.adjust(1, repeat=True)

        await self.bot.send_message( chat_id=message.chat.id, text=text, reply_markup=builder.as_markup() )


    # callbacks


    async def _setup_cancel( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )


    async def _setup_start( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )
        
        await self._setup_mode_start( callback_query.message.chat.id )


    async def _setup_mode( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )

        await self._setup_mode_start( callback_query.message.chat.id )


    async def _setup_format( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )

        await self._setup_format_start( callback_query.message.chat.id )


    async def _setup_cover( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )

        await self._setup_cover_start( callback_query.message.chat.id )


    async def _setup_images( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )

        await self._setup_images_start( callback_query.message.chat.id )


    # savers


    async def _setup_mode_save( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )

        user = await self.bot.DB.getUser( callback_query.from_user.id )
        if not user:
            logger.info('mode_save')
            logger.info(callback_query)
            return await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Ошибка: пользователь не найден, нажмите /start" )

        _mode = callback_query.data.split('setup:mode:')[1]
        if _mode == 'inline':
            user.interact_mode = 0
        if _mode == 'windowed':
            user.interact_mode = 1

        await self.bot.DB.saveUser(user)
        
        if not user.setuped:
            await self._setup_format_start( callback_query.message.chat.id )


    async def _setup_format_save( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )
        
        user = await self.bot.DB.getUser( callback_query.from_user.id )
        if not user:
            logger.info('format_save')
            logger.info(callback_query)
            return await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Ошибка: пользователь не найден, нажмите /start" )
        user.format = callback_query.data.split('setup:format:')[1]
        await self.bot.DB.saveUser(user)

        if not user.setuped:
            await self._setup_cover_start( callback_query.message.chat.id )


    async def _setup_cover_save( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )
        
        user = await self.bot.DB.getUser( callback_query.from_user.id )
        if not user:
            logger.info('cover_save')
            logger.info(callback_query)
            return await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Ошибка: пользователь не найден, нажмите /start" )
        _cover = callback_query.data.split('setup:cover:')[1]
        if _cover == 'yes':
            user.cover = True
        if _cover == 'no':
            user.cover = False
        await self.bot.DB.saveUser(user)

        if not user.setuped:
            await self._setup_images_start( callback_query.message.chat.id )


    async def _setup_images_save( self, callback_query: types.CallbackQuery ) -> None:
        await callback_query.answer()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            await self.bot.send_message( chat_id=callback_query.message.chat.id, reply_to_message_id=callback_query.message.message_id, text="Ошибка: Не могу удалить сообщение" )
        
        user = await self.bot.DB.getUser( callback_query.from_user.id )
        if not user:
            logger.info('images_save')
            logger.info(callback_query)
            return await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Ошибка: пользователь не найден, нажмите /start" )
        _images = callback_query.data.split('setup:images:')[1]
        if _images == 'yes':
            user.images = True
        if _images == 'no':
            user.images = False
        await self.bot.DB.saveUser(user)

        if not user.setuped:
            user.setuped = True
            await self.bot.DB.saveUser(user)
        
            await self.bot.send_message( chat_id=callback_query.message.chat.id, text="Настройка завершена" )
        


    # renderers


    async def _setup_mode_start( self, chat_id: int ) -> None:

        text = "Выберите режим взаимодействия"
        image = os.path.join( os.path.dirname(__file__), '..','assets','bot_mode.jpg')

        builder = InlineKeyboardBuilder()
        builder.button( text="В чате", callback_data=f"setup:mode:inline" )
        builder.button( text="Отдельные окна", callback_data=f"setup:mode:windowed" )
        builder.adjust(1, repeat=True)

        await self.bot.send_photo( chat_id=chat_id, photo=types.FSInputFile( image ), caption=text, reply_markup=builder.as_markup() )


    async def _setup_format_start( self, chat_id: int ) -> None:

        text = "Выберите формат (по умолчанию)"

        builder = InlineKeyboardBuilder()
        for format in self.bot.CNF.formats:
            builder.button( text=self.bot.CNF.formats[format], callback_data='setup:format:'+str(format))
        builder.adjust(1, repeat=True)

        await self.bot.send_message( chat_id=chat_id, text=text, reply_markup=builder.as_markup() )


    async def _setup_cover_start( self, chat_id: int ) -> None:

        text = "Скачивать обложки отдельным файлом (по умолчанию)?"

        builder = InlineKeyboardBuilder()
        builder.button( text="Да", callback_data='setup:cover:yes')
        builder.button( text="Нет", callback_data='setup:cover:no')
        builder.adjust(1, repeat=True)

        await self.bot.send_message( chat_id=chat_id, text=text, reply_markup=builder.as_markup() )


    async def _setup_images_start( self, chat_id: int ) -> None:

        text = "Скачивать изображения (по умолчанию)?"

        builder = InlineKeyboardBuilder()
        builder.button( text="Да", callback_data='setup:images:yes')
        builder.button( text="Нет", callback_data='setup:images:no')
        builder.adjust(1, repeat=True)

        await self.bot.send_message( chat_id=chat_id, text=text, reply_markup=builder.as_markup() )