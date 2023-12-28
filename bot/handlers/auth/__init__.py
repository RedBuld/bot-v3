import idna
import logging
import ujson
import aiohttp
from aiogram import Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import variables, schemas

from .window import WindowAuthController
from .inline import InlineAuthController
from .existent import ExistentAuthController

logger = logging.getLogger( __name__ )

class AuthController:
    
    bot: variables.Bot = None
    router: Router = None

    wac: WindowAuthController
    iac: InlineAuthController
    eac: ExistentAuthController

    def __init__( self, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.router = Router()
        #
        self.wac = WindowAuthController(self, bot, dispatcher)
        self.iac = InlineAuthController(self, bot, dispatcher)
        self.eac = ExistentAuthController(self, bot, dispatcher)
        #
        self.router.message.register( self._init, Command( commands='auth' ) )
        self.router.callback_query.register( self._cancel, F.data=='auth:cancel' )
        self.router.callback_query.register( self._setup_site, F.data.startswith('auth:') )
        #
        dispatcher.include_router( self.router )
    
    async def get_sites_with_auth( self ) -> bool:
        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot.CNF.queue_host + 'sites/auths', verify_ssl=False ) as response:
                if response.status == 200:
                    data = await response.json( loads=ujson.loads )
                    res = schemas.SiteListResponse( **data )
                    return res.sites
    
    #
    
    async def _cancel( self, callback_query: types.CallbackQuery, state: FSMContext ):
        await callback_query.answer()

        auth = await state.get_data()
        if auth and 'base_message' in auth and auth['base_message']:    
            try:
                await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=auth['base_message'] )
            except:
                pass
        if auth and 'last_message' in auth and auth['last_message']:
            try:
                await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=auth['last_message'] )
            except:
                pass

        await state.clear()

        try:
            await self.bot.delete_message( chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id )
        except:
            pass


    async def _init( self, message: types.Message, state: FSMContext ):

        actual_state = await state.get_state()
        if actual_state and actual_state.startswith( 'AuthForm' ):
            await self.bot.send_message( chat_id=message.chat.id, text="Отмените или завершите предыдущую авторизацию" )
        
        sites_with_auth = await self.get_sites_with_auth()

        if len(sites_with_auth) > 0:
            builder = InlineKeyboardBuilder()

            for site in sites_with_auth:
                builder.button( text=idna.decode(site), callback_data=f"auth:{site}" )

            builder.adjust(1, repeat=True)

            await state.set_state(variables.AuthForm.site)

            msg = await self.bot.send_message( chat_id=message.chat.id, text="Выберите сайт", reply_markup=builder.as_markup() )
            await state.update_data( base_message=msg.message_id )
        else:
            await state.clear()
            await self.bot.send_message( chat_id=message.chat.id, text="Нет сайтов доступных для авторизации", reply_markup=None )


    async def _setup_site( self, callback_query: types.CallbackQuery, state: FSMContext ) -> None:
        await callback_query.answer()

        site = callback_query.data.split('auth:')[1]

        await state.update_data(site=site)

        user = await self.bot.DB.getUser( user_id=callback_query.from_user.id )

        await self.iac._init( callback_query.message, user, site, state )
        # if user.interact_mode == 0:
        #     await self.iac._init( callback_query.message, user, site, state )
        # elif user.interact_mode == 1:
        #     await self.wac._init( callback_query.message, user, site )