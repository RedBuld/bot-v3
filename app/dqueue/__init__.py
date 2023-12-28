import os
import asyncio
import traceback
import logging
import ujson
import aiohttp
import redis.asyncio as rds
from ctypes import c_bool
from multiprocessing import Process, Value, Queue
from dacite import from_dict, Config as dConfig
from typing import List, Dict
from app import variables, schemas
from app.db import DBE
from app.downloader import start_downloader

logger = logging.getLogger(__name__)

class DownloadsQueue(variables.QueueBase):

    RD:       rds.Redis
    DB:       DBE
    statuses: Queue = None
    results:  Queue = None

    def __init__(self, RD: rds.Redis, DB: DBE) -> None:
        super().__init__()
        self.RD = RD
        self.DB = DB

    async def Start(self) -> None:
        self.stop_queue = False
        self.stopped = False
        self.statuses = Queue()
        self.results = Queue()
        try:
            await self.__restore()

            asyncio.create_task( self.__tasks_runner() )
            await asyncio.sleep( 0 )

            asyncio.create_task( self.__results_runner() )
            await asyncio.sleep( 0 )

        except KeyboardInterrupt:
            pass
        except:
            traceback.print_exc()

    async def Stop(self) -> None:
        self.stop_queue = True
        while not self.stopped:
            await asyncio.sleep(0.1)

    ### PUBLIC METHODS

    async def UpdateConfig(self, config_file: str | os.PathLike) -> None:

        if not os.path.exists(config_file):
            raise FileNotFoundError(config_file)

        with open(config_file,'r',encoding='utf-8') as _config_file:
            _config = _config_file.read()

            try:
                data = ujson.loads(_config)
                config = from_dict(data_class=variables.QueueConfig, data=data, config=dConfig(check_types=False))
                
                await self._setup(config)
            except Exception:
                traceback.print_exc()

    async def CheckSite(self, site_name: str) -> (bool, list[str], list[str]):
        if site_name not in self.active:
            return False, [], []

        group_name = await self.site_to_group.Get(site_name)
        if group_name is None:
            return False, [], []

        site_stats = await self.sites_stats.Get(site_name)
        if site_stats is None:
            return True, [], []

        formats = site_stats.formats
        if not formats:
            group = await self.group_stats.Get(group_name)
            if not group:
                return True, [], []
            formats = group.formats

        return True, site_stats.parameters, formats

    async def GetSitesWithAuth(self) -> List[str]:
        return self.auths

    async def GetSitesActive(self) -> List[str]:
        return self.active

    async def AddTask(self, request: schemas.DownloadRequest) -> schemas.DownloadResponse:
        logger.info('DQ: received request:' + str(request))
        
        group_name = await self.site_to_group.Get(request.site)
        if group_name:

            config = await self.sites_stats.Get(request.site)

            if config and config.proxy and not request.proxy:
                request.proxy = config.proxy

            if request.task_id is None: # Maybe restoring task
                try:
                    request = await asyncio.wait_for( self.DB.saveRequest( request.model_dump() ), timeout=5.0 )
                except ( asyncio.TimeoutError, asyncio.CancelledError ):
                    return schemas.DownloadResponse(
                        status =  False,
                        message = "База данных недоступна или перегружена"
                    )


            waiting_task = variables.QueueWaitingTask(
                task_id = request.task_id,
                request = request
            )

            await self.queue_waiting.GroupSetTask(group_name, waiting_task)
        
        
        return schemas.DownloadResponse(
            status =  True,
            message = str(request.task_id)
        )

    async def CancelTask(self, cancel: schemas.DownloadCancel) -> None:
        logger.info('DQ: cancel task:' + str(cancel.model_dump()))
        try:
            task = await self.queue_running.GetTask(cancel.task_id)
            if task is not None:
                task.cancelled.value = True
                # os.kill(task.proc.pid, signal.SIGBREAK)
                # print(task.downloader)
                # task.proc.terminate()
                # task.downloader.Stop()
                return
        except:
            traceback.print_exc()

    ### PRIVATE METHODS
    
    async def __restore(self) -> None:
        requests = await self.DB.getAllRequests()
        for request in requests:
            asyncio.create_task( self.AddTask( schemas.DownloadRequest.model_validate(request) ) )
            await asyncio.sleep( 0 )
        
        results = await self.DB.getAllResults()
        for result in results:
            asyncio.create_task( self.__task_done( schemas.DownloadResult.model_validate(result) ) )
            await asyncio.sleep( 0 )

    async def __results_runner(self) -> None:
        logger.info('DQ: __results_runner started')
        while True:
            # print('__results_runner tick')
            try:
                while not self.results.empty():
                    json_result = self.results.get()

                    result = schemas.DownloadResult( **json_result )

                    await self.__task_done( result=result )

                    if self.stop_queue:
                        break

                while not self.statuses.empty():
                    json_status = self.statuses.get()

                    status = schemas.DownloadStatus( **json_status )

                    await self.__task_status( status=status )

                    if self.stop_queue:
                        break

            except:
                traceback.print_exc()
            if self.stop_queue:
                break
            await asyncio.sleep(0.5)
        
    async def __tasks_runner(self) -> None:
        logger.info('DQ: __tasks_runner started')
        while True:
            # print('__tasks_runner tick')
            try:
                for group_name in self.groups:

                    try:
                        wg_exists = await self.queue_waiting.Exists( group_name )
                        # logger.info('DQ: group "'+group_name+'" '+('exists' if wg_exists else 'missing'))
                        if wg_exists:
                            # preventive skip group
                            if not await self.group_stats.GroupCanStart( group_name ):
                                # logger.info('DQ: group can\'t run')
                                continue
                            # logger.info('DQ: group can run')

                            tasks = await self.queue_waiting.GroupGetTasks( group_name )
                            # logger.info('DQ: group tasks: '+str(tasks))
                            for task in tasks:
                                if not await self.group_stats.GroupCanStart( group_name ):
                                    # logger.info('DQ: group can\'t run')
                                    continue
                                # logger.info('DQ: group can run')

                                site_name = task.request.site
                                if not await self.sites_stats.SiteCanStart( site_name ):
                                    # logger.info('DQ: site can\'t run')
                                    continue
                                # logger.info('DQ: site can run')

                                task_id = task.task_id
                                await self.queue_waiting.GroupRemTask( group_name, task_id )

                                await self.__task_start( task )
                    except:
                        traceback.print_exc()
            except:
                traceback.print_exc()

            if self.stop_queue:
                break
            await asyncio.sleep(0.5)
        self.stopped = True
        logger.info('DQ: runner finished')

    ###

    async def __task_start(self, waiting_task: variables.QueueWaitingTask) -> None:
        logger.info('DQ: __task_start')

        try:
            site_name = waiting_task.request.site
            group_name = await self.site_to_group.Get( site_name )
            if group_name:
                
                running_task = variables.QueueRunningTask(
                    task_id =    waiting_task.task_id,
                    user_id =    waiting_task.request.user_id,
                    site =       waiting_task.request.site,
                    cancelled =  Value(c_bool, False),
                )

                if await self.queue_running.SetTask( running_task ):
                    await self.group_stats.GroupAddRun( group_name )
                    await self.sites_stats.SiteAddRun( site_name )

                    ss = await self.sites_stats.Get(site_name)

                    downloader = self.downloader.downloaders[ ss.downloader ]

                    running_task.proc = Process(
                        target=start_downloader,
                        name="Downloader #"+str(waiting_task.task_id),
                        kwargs={
                            'request':     waiting_task.request,
                            'downloader':  downloader,
                            'save_folder': self.downloader.save_folder,
                            'exec_folder': self.downloader.exec_folder,
                            'temp_folder': self.downloader.temp_folder,
                            'compression': self.downloader.compression,
                            'cancelled':   running_task.cancelled,
                            'statuses':    self.statuses,
                            'results':     self.results,
                        },
                        daemon=True
                    )
                    running_task.proc.start()

                    logger.info('DQ: started '+str(running_task.proc))
        except:
            traceback.print_exc()
    
    #

    async def __task_status(self, status: schemas.DownloadStatus) -> None:
        # logger.info('DQ: __task_status')

        if not await self.queue_running.Exists( status.task_id ):
            return

        async with aiohttp.ClientSession( json_serialize=ujson.dumps ) as session:
            async with session.post( self.bot_host + 'download/status', json=status.model_dump(), verify_ssl=False ) as response:
                pass

    #

    async def __task_done(self, result: schemas.DownloadResult) -> None:
        # logger.info('DQ: __task_done')

        try:
            if await self.queue_running.Exists( result.task_id ):
                await self.queue_running.RemTask( result.task_id )
            
            site_name = result.site
            if site_name:
                group_name = await self.site_to_group.Get( site_name )

                await self.sites_stats.SiteRemoveRun( site_name )
                await self.sites_stats.save( self.RD )

                if group_name:
                    await self.group_stats.GroupRemoveRun( group_name )
                    await self.group_stats.save( self.RD )

        except:
            traceback.print_exc()

        await self.DB.saveResult( result.model_dump() )

        await self.DB.deleteRequest( result.task_id )

        _attempts = 0
        while _attempts < 5:
            async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
                async with session.post( self.bot_host + 'download/done', json=result.model_dump(), verify_ssl=False ) as response:
                    if response.status == 200:
                        await self.DB.deleteResult( result.task_id )
                        print( 'deleted result, task #' + str( result.task_id ) )
                        _attempts = 5
                    else:
                        await asyncio.sleep(1)

        try:
            await self.DB.updateSiteStat( result.model_dump() )
        except:
            traceback.print_exc()
