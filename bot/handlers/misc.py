import idna
import ujson
import aiohttp
import logging
from aiogram import Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot import models, variables, schemas

logger = logging.getLogger( __name__ )

class MiscController:

    bot: variables.Bot = None
    router: Router = None

    def __init__( self, bot: variables.Bot, dispatcher: Dispatcher ) -> None:
        self.bot = bot
        self.router = Router()
        self.router.message.register( self.sites_command, Command( commands='sites' ) )
        self.router.message.register( self.uid_command, Command( commands='uid' ) )
        dispatcher.include_router( self.router )
    
    async def get_sites_list( self ):
        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot.CNF.queue_host + 'sites/active', verify_ssl=False ) as response:
                if response.status == 200:
                    data = await response.json( loads=ujson.loads )
                    res = schemas.SiteListResponse( **data )
                    return res.sites

    async def sites_command( self, message: types.Message ) -> None:
        sites_list = await self.get_sites_list()

        await self.bot.send_message( chat_id=message.chat.id, text=f"Список поддерживаемых сайтов:\n\n" + ( '\n'.join( [idna.decode(x) for x in sites_list] ) ), reply_markup=None )

    async def uid_command( self, message: types.Message ) -> None:

        await self.bot.send_message( chat_id=message.chat.id, text=f"Ваш ID: \n" + str( message.from_user.id ), reply_markup=None )