# -*- coding: utf-8 -*-
import os
import time
import ujson
import asyncio
import logging
import redis.asyncio as redis
from cryptography.fernet import Fernet
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from aiogram import Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from bot import schemas, variables
from bot.db import DBE
from bot.handlers import *

####

logging.basicConfig(
    # filename="C:\\Users\\RedBuld\\Pictures\\log.txt",
    format='\x1b[32m%(levelname)s\x1b[0m:     %(name)s[%(process)d] %(asctime)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def request_validation_error_exception_handler( request: Request, exc: RequestValidationError ):
    print( exc )
    validation_errors = exc.errors()
    return JSONResponse(
        status_code = 500,
        content =     { "detail": [ str( err ) for err in validation_errors ] }
    )

async def response_validation_error_exception_handler( request: Request, exc: ResponseValidationError ):
    print( exc )
    validation_errors = exc.errors()
    return JSONResponse(
        status_code = 500,
        content =     { "detail": [ str( err ) for err in validation_errors ] }
    )

async def base_error_exception_handler( request: Request, exc: Exception ):
    print( exc )
    return JSONResponse(
        status_code = 500,
        content =     { "detail": str( exc ) }
    )

####

RD = redis.Redis( host='192.168.1.151', port=6379, db=0, protocol=3, decode_responses=True )
DB = DBE()

bot = variables.Bot()
bot.DB = DB
bot.RD = RD

storage = MemoryStorage()
dispatcher = Dispatcher( bot=bot, storage=storage )

sc = SetupController( bot, dispatcher )
dc = DownloadsController( bot, dispatcher )
ac = AuthController( bot, dispatcher )
mc = MiscController( bot, dispatcher )

@dispatcher.update()
async def message_handler(update: types.Update) -> None:
    print('update not handled')
    print(update)


@asynccontextmanager
async def lifespan( app: FastAPI ):
    await update_config()
    await db_start()
    await bot_start()
    yield
    await bot_stop()
    await db_stop()

app = FastAPI( lifespan=lifespan )

tdir = os.path.join(os.path.dirname(__file__), "web")
templates = Jinja2Templates(directory=tdir)
app.mount("/web", StaticFiles(directory=tdir), name="static")

async def update_config():
    await db_update_config()
    await bot_update_config()

#UPDATE CONFIG
async def db_update_config():
    database_config_file = os.path.join( os.path.dirname( __file__ ), 'configs', 'database.json' )
    await DB.updateConfig( database_config_file )

async def bot_update_config():
    bot_config_file = os.path.join( os.path.dirname( __file__ ), 'configs', 'bot.json' )
    await bot.updateConfig( bot_config_file )

# START
async def db_start():
    await DB.Start()

async def bot_start() -> None:
    wh = await bot.set_webhook( bot.CNF.bot_host, drop_pending_updates=False )
    logger.info( 'wh -> ' + bot.CNF.bot_host + ' -> ' +  str( wh ) )

# STOP
async def db_stop():
    await DB.Stop()

async def bot_stop() -> None:
    await bot.delete_webhook()
    await bot.session.close()

#

@app.get('/auth/setup', response_class=HTMLResponse)
async def download_setup_start( request: Request, payload: str ):
    f = Fernet(bot.EncryptKey)
    try:
        decoded = f.decrypt( payload.encode('utf-8') )
        temp = ujson.loads( decoded )
        decoded = temp
    except Exception:
        decoded = False
    return templates.TemplateResponse("auth/index.html", {"request":request, "payload": decoded})

#

@app.get('/download/setup', response_class=HTMLResponse)
async def download_setup_start( request: Request, payload: str ):
    f = Fernet(bot.EncryptKey)
    try:
        decoded = f.decrypt( payload.encode('utf-8') )
        temp = ujson.loads( decoded )
        decoded = temp
    except Exception:
        decoded = False
    if decoded:
        named_formats = {}
        if 'formats' in decoded:
            for x in decoded['formats']:
                if x in bot.CNF.formats:
                    named_formats[x] = bot.CNF.formats[x]
        decoded['host'] = bot.CNF.bot_host
    else:
        named_formats = {}
    return templates.TemplateResponse("download/index.html", {"request":request, "payload": decoded, "named_formats":named_formats})

@app.post('/download/setup')
async def handle_download( payload: schemas.DownloadSetupRequest ):
    await dc.wdc._start( payload )
    return {'status':True}

@app.post('/download/status')
async def download_status( status: schemas.DownloadStatus ) -> bool:
    return JSONResponse(
        status_code = 200 if await dc.download_status( status ) else 500,
        content = ''
    )

@app.post('/download/done')
async def download_done( result: schemas.DownloadResult ) -> bool:
    return JSONResponse(
        status_code = 200 if await dc.download_done( result ) else 500,
        content = ''
    )

#

@app.post('/')
async def bot_handle( update: dict ) -> None:
    asyncio.create_task( dispatcher.feed_raw_update( bot=bot, update=update ) )
    print(update)
    return ''