# -*- coding: utf-8 -*-
import os
import asyncio
import logging
import redis.asyncio as rds
from app import schemas
from app.db import DBE
from app.dqueue import DownloadsQueue

logging.basicConfig(
    # filename="C:\\Users\\RedBuld\\Pictures\\log.txt",
    format='\x1b[32m%(levelname)s\x1b[0m:     %(name)s[%(process)d] %(asctime)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

DB = DBE()
RD = rds.Redis( host='192.168.1.151', port=6379, db=0, protocol=3, decode_responses=True )
DQ = DownloadsQueue(RD)

async def db_update_config():
    database_config_file = os.path.join( os.path.dirname(__file__), 'configs', 'database.json' )
    await DB.updateConfig( database_config_file )

async def dq_update_config():
    queue_config_file = os.path.join( os.path.dirname(__file__), 'configs', 'queue.json' )
    await DQ.updateConfig( queue_config_file )

async def _test():
    request = schemas.DownloadRequest(
        bot_id = "test",
        user_id = 123,
        chat_id = 456,
        message_id = 789,
        site = 'author.today',
        url = 'https://author.today/work/305489',
        start = 0,
        end = 0,
        format = 'fb2',
        images = False,
        cover = False,
        login = '',
        password = '',
        proxy = ""
    )
    db_request = await DB.saveRequest( request.model_dump() )
    await DQ.AddTask( db_request )

async def _start():
    await db_update_config()
    await dq_update_config()
    await DB.Start()
    await DQ.Start()
    await _test()

if __name__ == '__main__':
    loop = asyncio.new_event_loop()

    loop.create_task( _start() )

    loop.run_forever()