# -*- coding: utf-8 -*-

import traceback
import asyncio
import logging
import os
import aiohttp
import ujson
import redis.asyncio as rds
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from threading import Thread
from app import schemas
from app.db import DBE
from app.dqueue import DownloadsQueue

logging.basicConfig(
    # filename="C:\\Users\\RedBuld\\Pictures\\log.txt",
    format='\x1b[32m%(levelname)s\x1b[0m:     %(name)s[%(process)d] %(asctime)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger( __name__ )

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

RD = rds.Redis( host='192.168.1.151', port=6379, db=0, protocol=3, decode_responses=True )
DB = DBE()
DQ = DownloadsQueue(RD,DB)

@asynccontextmanager
async def lifespan( app: FastAPI ):
    await update_config()
    await db_start()
    await dq_start()
    yield
    await dq_stop()
    await db_stop()
    if RD is not None:
        await RD.close()

app = FastAPI(
    docs_url=None,
    openapi_url=None,
    exception_handlers={
        RequestValidationError: request_validation_error_exception_handler,
        ResponseValidationError: response_validation_error_exception_handler,
        Exception: base_error_exception_handler
    },
    lifespan=lifespan
)

# UPDATE_CONFIG
async def db_update_config():
    database_config_file = os.path.join( os.path.dirname(__file__), 'configs', 'database.json' )
    await DB.updateConfig( database_config_file )

async def dq_update_config():
    queue_config_file = os.path.join( os.path.dirname(__file__), 'configs', 'queue.json' )
    await DQ.UpdateConfig( queue_config_file )

# START
async def db_start():
    await DB.Start()

async def dq_start():
    await DQ.Start()
    # background_thread = Thread( target=DQ.Start )
    # background_thread.start()

# STOP
async def db_stop():
    await DB.Stop()

async def dq_stop():
    await DQ.Stop()

#

@app.post('/update_config')
async def update_config():
    await db_update_config()
    await dq_update_config()

@app.post('/stop')
async def stop():
    await dq_stop()

@app.post('/start')
async def start():
    await dq_start()

#

@app.post('/sites/check')
async def sites_check( request: schemas.SiteCheckRequest ):
    allowed, parameters, formats = await DQ.CheckSite( request.site )
    resp = schemas.SiteCheckResponse(
        allowed = allowed,
        parameters = parameters,
        formats = formats
    )
    return resp

@app.post('/sites/auths')
async def sites_auths():
    sites = await DQ.GetSitesWithAuth()
    resp = schemas.SiteListResponse(
        sites = sites
    )
    return resp

@app.post('/sites/active')
async def sites_active():
    sites = await DQ.GetSitesActive()
    resp = schemas.SiteListResponse(
        sites = sites
    )
    return resp

@app.post('/download/new')
async def download_new( request: schemas.DownloadRequest ):

    try:
        resp = await asyncio.wait_for( DQ.AddTask( request ), timeout=10.0 )

        if resp.status:
            return JSONResponse(
                status_code = 200,
                content =     resp.message
            )
        else:
            return JSONResponse(
                status_code = 500,
                content =     resp.message
            )
    except:
        return JSONResponse(
            status_code = 500,
            content =     "Произошла ошибка"
        )

@app.post('/download/cancel')
async def download_cancel( download: schemas.DownloadCancel ):
    try:
        await DQ.CancelTask( download )
        return JSONResponse(
            status_code = 200,
            content =     ""
        )
    except:
        return JSONResponse(
            status_code = 500,
            content =     "Произошла ошибка"
        )