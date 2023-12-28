# -*- coding: utf-8 -*-
# pylint: disable=C0103,R0903
from __future__ import annotations
from dataclasses import dataclass, field

import os
import redis.asyncio as rds
from datetime import datetime, timedelta
from multiprocessing import Process, Value, Queue
from typing import Callable, Optional, List, Dict
from app import models
from app.db import DBE

####

@dataclass
class QueueConfig():
    bot_host:           str
    queue_host:         str
    groups:             Dict[ str, QueueConfigGroup ]
    sites:              Dict[ str, QueueConfigSite ]
    downloader:         QueueConfigDownloader
    user_stats_timeout: int = 0
    exec_folder:        str = ""
    save_folder:        str = ""
    Consumer:           Optional[ Callable[ [ models.DownloadResult ], None ] ] = None

#

@dataclass
class QueueConfigGroup():
    per_user:       int = 1
    simultaneously: int = 1
    delay:          int = 0
    formats:        List[ str ] = field(default_factory=list)

#

@dataclass
class QueueConfigSite():
    parameters:     List[ str ] = field(default_factory=list)
    formats:        List[ str ] = field(default_factory=list)
    active:         bool = True
    proxy:          str = ""
    simultaneously: int = 1
    per_user:       int = 1
    group:          str = ""
    delay:          int = 0
    pause_by_user:  int = 1
    downloader:     str = "elib2ebook"

#

@dataclass
class QueueConfigDownloader():
    save_folder:   str | os.PathLike
    exec_folder:   str | os.PathLike
    temp_folder:   str | os.PathLike
    compression:   Dict[ str, str | os.PathLike ]
    downloaders:   Dict[ str, QueueConfigDownloaderExec ]

@dataclass
class QueueConfigDownloaderExec():
    folder:        str
    exec:          str
####

class QueueBase():
    bot_host:      str
    queue_host:    str
    # base
    checkInterval: float = 1.0
    stop_queue:    bool = False
    stopped:       bool = False
    # maps
    active:        List[ str ] = []
    auths:         List[ str ] = []
    groups:        List[ str ] = []
    site_to_group: QueueSiteMap
    # realtime stats
    group_stats:   QueueStatsGroups
    sites_stats:   QueueStatsSites
    # users:       QueueStatsusers
    # tasks
    queue_waiting: QueueWaiting
    queue_running: QueueRunning
    # downloader
    downloader:    QueueDownloaderConfig

    def __init__( self ) -> None:
        self.groups =        []
        self.auths =         []
        self.site_to_group = QueueSiteMap()
        self.group_stats =   QueueStatsGroups()
        self.sites_stats =   QueueStatsSites()
        self.queue_waiting = QueueWaiting()
        self.queue_running = QueueRunning()
        self.downloader =    QueueDownloaderConfig()
        self.stop_queue =    False
        self.stopped =       False

    def __repr__( self ) -> str:
        return '<QueueBase>'

    async def _setup(self, config: QueueConfig) -> None:

        self.bot_host =   config.bot_host
        self.queue_host = config.queue_host

        await self._setupDownloaderConfig(config.downloader)
        await self._setupGroupsStats(config.groups)
        await self._setupSitesStats(config.sites)
    
    #

    async def _setupDownloaderConfig(self, config: QueueConfigDownloader) -> None:
        self.downloader = QueueDownloaderConfig(
            save_folder = config.save_folder,
            exec_folder = config.exec_folder,
            temp_folder = config.temp_folder,
            compression = config.compression,
            downloaders = config.downloaders,
        )
    
    #

    async def _setupGroupsStats(self, groups: Dict[str, QueueConfigGroup]) -> None:
        used_groups: List[str] = []
        for group_name in groups:
            params = groups[group_name]
            stats_group_exists = await self.group_stats.Exists(group_name)

            if not stats_group_exists:
                lr = await self.RD.get(f"sg_{group_name}_last_run")
                if not lr:
                    lr = datetime.now() - timedelta(seconds=params.delay)
                else:
                    lr = datetime.strptime(lr, '%Y-%m-%d %H:%M:%S')
                stats_group = QueueStatsGroup(
                    per_user =       params.per_user,
                    simultaneously = params.simultaneously,
                    delay =          timedelta(seconds=params.delay),
                    last_run =       lr,
                    active =         0,
                    formats =        params.formats
                )
                await self.group_stats.Set(group_name, stats_group)
            else:
                await self.group_stats.GroupSetPerUser(group_name, params.per_user)
                await self.group_stats.GroupSetSimultaneously(group_name, params.simultaneously)
                await self.group_stats.GroupSetFormats(group_name, params.formats)

            waiting_group_exists = await self.queue_waiting.Exists(group_name)
            if not waiting_group_exists:
                waiting_group = QueueWaitingGroup(
                    tasks= {},
                )
                await self.queue_waiting.Set(group_name, waiting_group)

            if group_name not in used_groups:
                used_groups.append(group_name)
        self.groups = used_groups
        pass

    #

    async def _setupSitesStats(self, sites: Dict[str, QueueConfigSite]) -> None:
        self.site_to_group = QueueSiteMap(
            map = {},
        )
        auths = []
        active = []
        for site_name in sites:
            params = sites[site_name]
            stats_site_exists = await self.sites_stats.Exists(site_name)

            if 'auth' in params.parameters:
                auths.append(site_name)

            if params.active:
                active.append(site_name)

            if not stats_site_exists:
                lr = await self.RD.get(f"ss_{site_name}_last_run")
                if not lr:
                    lr = datetime.now() - timedelta(seconds=params.delay)
                else:
                    lr = datetime.strptime(lr, '%Y-%m-%d %H:%M:%S')
                stats_site = QueueStatsSite(
                    per_user =       params.per_user,
                    simultaneously = params.simultaneously,
                    delay =          timedelta(seconds=params.delay),
                    last_run =       lr,
                    active =         0,
                    formats =        params.formats,
                    parameters =     params.parameters,
                    downloader =     params.downloader,
                    proxy =          params.proxy,
                )
                await self.sites_stats.Set(site_name, stats_site)
            else:
                await self.sites_stats.SiteSetDelay(site_name, params.delay)
                await self.sites_stats.SiteSetPerUser(site_name, params.per_user)
                await self.sites_stats.SiteSetSimultaneously(site_name, params.simultaneously)
                await self.sites_stats.SiteSetFormats(site_name, params.formats)
                await self.sites_stats.SiteSetParameters(site_name, params.parameters)
                await self.sites_stats.SiteSetDownloader(site_name, params.downloader)
                await self.sites_stats.SiteSetProxy(site_name, params.downloader)

            await self.site_to_group.Set(site_name, params.group)
        self.auths = auths
        self.active = active

####

class QueueDownloaderConfig():
    save_folder:   str | os.PathLike
    exec_folder:   str | os.PathLike
    temp_folder:   str | os.PathLike
    compression:   Dict[ str, str | os.PathLike ]
    compression:   Dict[ str, QueueConfigDownloaderExec ]

    def __init__( self,
                 save_folder: str | os.PathLike = "",
                 exec_folder: str | os.PathLike = "",
                 temp_folder: str | os.PathLike = "",
                 compression: Dict[ str, str | os.PathLike ] = {},
                 downloaders: Dict[ str, QueueConfigDownloaderExec ] = {},
                ) -> None:
        self.save_folder = save_folder
        self.exec_folder = exec_folder
        self.temp_folder = temp_folder
        self.compression = compression
        self.downloaders = downloaders


class QueueStatsGroups():
    groups: Dict[ str, QueueStatsGroup ] = {}

    def __init__( self ) -> None:
        self.groups = {}

    async def save( self, RD: rds.Redis ) -> None:
        for group_name in self.groups:
            await RD.setex( f"sg_{group_name}_last_run", 3600, datetime.strftime( self.groups[ group_name ].last_run, '%Y-%m-%d %H:%M:%S' ) )
    
    def __repr__( self ) -> str:
        return '<QueueStatsGroups '+str( {
            'groups': self.groups,
        } )+'>'

    async def Exists( self, group_name: str ) -> bool:
        ok: bool = group_name in self.groups
        return ok
    
    async def Get( self, group_name: str ) -> QueueStatsGroup | None:
        ok: bool = group_name in self.groups
        if ok:
            group = self.groups[ group_name ]
            return group
        return None

    async def Set( self, group_name: str, group: QueueStatsGroup ) -> bool:
        self.groups[ group_name ] = group
        return True

    async def GroupCanStart( self, group_name: str ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            group = self.groups[ group_name ]
            group_simultaneously_limit = ( group.active < group.simultaneously ) if group.simultaneously > 0 else True
            group_last_run_limit = group.last_run < ( datetime.now() - group.delay )
            return group_simultaneously_limit and group_last_run_limit
        return ok

    async def GroupAddRun( self, group_name: str ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].active += 1
            self.groups[ group_name ].last_run = datetime.now()
        return ok

    async def GroupRemoveRun( self, group_name: str ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].active -= 1
        return ok
    
    async def GroupSetSimultaneously( self, group_name: str, simultaneously: int ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].simultaneously = simultaneously
        return ok
    
    async def GroupSetPerUser( self, group_name: str, per_user: int ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].per_user = per_user
        return ok
    
    async def GroupSetFormats( self, group_name: str, formats: list[str] ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].formats = formats
        return ok

class QueueStatsGroup():
    per_user:       int = 0
    simultaneously: int = 1
    active:         int = 0
    last_run:       datetime = datetime.now()
    delay:          timedelta = timedelta( seconds=0 )
    formats:        list[str] = []

    def __init__( self,
                 per_user:       int = 0,
                 simultaneously: int = 1,
                 active:         int = 0,
                 last_run:       datetime = datetime.now(),
                 delay:          timedelta = timedelta( seconds=0 ),
                 formats:        list[str] = []
                ):
        self.per_user = per_user
        self.simultaneously = simultaneously
        self.active = active
        self.last_run = last_run
        self.delay = delay
        self.formats = formats

    def __repr__( self ) -> str:
        return '<QueueStatsGroup '+str( {
            'per_user':       self.per_user,
            'simultaneously': self.simultaneously,
            'active':         self.active,
            'last_run':       self.last_run,
            'delay':          self.delay,
            'formats':        self.formats,
        } )+'>'

####

class QueueStatsSites():
    sites: Dict[ str,QueueStatsSite ] = {}

    def __init__( self ) -> None:
        self.sites = {}

    async def save( self, RD: rds.Redis ) -> None:
        for site_name in self.sites:
            await RD.setex( f"ss_{site_name}_last_run", 3600, datetime.strftime( self.sites[ site_name ].last_run, '%Y-%m-%d %H:%M:%S' ) )

    def __repr__( self ) -> str:
        return '<QueueStatsSites>'
    
    async def Exists( self, site_name: str ) -> bool:
        ok: bool = site_name in self.sites
        return ok
    
    async def Get( self, site_name: str ) -> QueueStatsSite | None:
        ok: bool = site_name in self.sites
        if ok:
            site = self.sites[ site_name ]
            return site
        return None

    async def Set( self, site_name: str, site: QueueStatsSite ) -> bool:
        self.sites[ site_name ] = site
        return True

    async def SiteCanStart( self, site_name: str ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            site = self.sites[ site_name ]
            site_simultaneously_limit = ( site.active < site.simultaneously ) if site.simultaneously > 0 else True
            site_last_run_limit = site.last_run < ( datetime.now() - site.delay )
            # print('site_name', site_name)
            # print('site_simultaneously_limit', site_simultaneously_limit)
            # print('site_last_run_limit', site_last_run_limit)
            # print('site.last_run', site.last_run)
            # print('site.last_run_trigger', ( datetime.now() - site.delay ))
            return site_simultaneously_limit and site_last_run_limit
        return ok

    async def SiteAddRun( self, site_name: str ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].active += 1
            self.sites[ site_name ].last_run = datetime.now()
        return ok

    async def SiteRemoveRun( self, site_name: str ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].active -= 1
        return ok

    async def SiteSetDelay( self, site_name: str, delay: int ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].delay = timedelta( seconds=delay )
        return ok

    async def SiteSetSimultaneously( self, site_name: str, simultaneously: int ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].simultaneously = simultaneously
        return ok

    async def SiteSetPerUser( self, site_name: str, per_user: int ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].per_user = per_user
        return ok

    async def SiteSetFormats( self, site_name: str, formats: list[str] ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].formats = formats
        return ok

    async def SiteSetParameters( self, site_name: str, parameters: list[str] ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].parameters = parameters
        return ok

    async def SiteSetDownloader( self, site_name: str, downloader: str ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].downloader = downloader
        return ok

    async def SiteSetProxy( self, site_name: str, proxy: str ) -> bool:
        ok: bool = site_name in self.sites
        if ok:
            self.sites[ site_name ].proxy = proxy
        return ok

class QueueStatsSite():
    per_user:       int = 1
    simultaneously: int = 1
    active:         int = 0
    last_run:       datetime = datetime.now()
    delay:          timedelta = timedelta( seconds=0 )
    downloader:     str = "elib2ebook"
    parameters:     list[str] = []
    formats:        list[str] = []
    proxy:          str = ""
    
    def __init__( self,
                 per_user:       int = 0,
                 simultaneously: int = 1,
                 active:         int = 0,
                 last_run:       datetime = datetime.now(),
                 delay:          timedelta = timedelta( seconds=0 ),
                 downloader:     str = "elib2ebook",
                 parameters:     list[str] = [],
                 formats:        list[str] = [],
                 proxy:          str = "",
                ) -> None:
        self.per_user = per_user
        self.simultaneously = simultaneously
        self.active = active
        self.last_run = last_run
        self.delay = delay
        self.downloader = downloader
        self.parameters = parameters
        self.formats = formats
        self.proxy = proxy

    def __repr__( self ) -> str:
        return '<QueueStatsSite '+str( {
            'per_user':       self.per_user,
            'simultaneously': self.simultaneously,
            'active':         self.active,
            'last_run':       self.last_run,
            'delay':          self.delay,
            'downloader':     self.downloader,
            'parameters':     self.parameters,
            'proxy':          self.proxy,
        } )+'>'

####

class QueueSiteMap():
    map: Dict[ str, str ] = {}

    def __init__( self,
                 map: Dict[ str, str ] = {},
                ) -> None:
        self.map = map

    def __repr__( self ) -> str:
        return '<QueueSiteMap>'
    
    async def AllSites( self ) -> List[str]:
        return self.map.keys()
    
    async def Exists( self, site_name: str ) -> bool:
        ok: bool = site_name in self.map
        return ok
    
    async def Get( self, site_name: str ) -> str | None:
        ok: bool = site_name in self.map
        if ok:
            group_name = self.map[ site_name ]
            return group_name
        return None

    async def Set( self, site_name: str, group_name: str ) -> bool:
        self.map[ site_name ] = group_name
        return True

####

class QueueWaiting():
    groups: Dict[ str, QueueWaitingGroup ] = {}

    def __init__( self,
                 groups: Dict[ str, QueueWaitingGroup ] = {},
                ) -> None:
        self.groups = groups

    def __repr__( self ) -> str:
        return '<QueueWaiting>'
    
    async def Exists( self, group_name: str ) -> bool:
        ok: bool = group_name in self.groups
        return ok
    
    async def Get( self, group_name: str ) -> QueueWaitingGroup | None:
        ok: bool = group_name in self.groups
        if ok:
            group = self.groups[ group_name ]
            return group
        return None

    async def Set( self, group_name: str, group: QueueWaitingGroup ) -> bool:
        self.groups[ group_name ] = group
        return True
    
    async def GroupGetTasks( self, group_name: str ) -> List[ QueueWaitingTask ] | None:
        ok: bool = group_name in self.groups
        if ok:
            return [ task for task_id, task in self.groups[ group_name ].tasks.items() ]
        return None
    
    async def GroupGetTask( self, group_name: str, task_id: int ) -> QueueWaitingTask | None:
        ok: bool = group_name in self.groups
        if ok:
            task_ok: bool = task_id in self.groups[ group_name ].tasks
            if task_ok:
                task: QueueWaitingTask = self.groups[ group_name ].tasks[ task_id ]
                return task
        return None

    async def GroupSetTask( self, group_name: str, task: QueueWaitingTask ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            self.groups[ group_name ].tasks[ task.task_id ] = task
            return True
        return False

    async def GroupRemTask( self, group_name: str, task_id: int ) -> bool:
        ok: bool = group_name in self.groups
        if ok:
            del self.groups[ group_name ].tasks[ task_id ]
            return True
        return False

class QueueWaitingGroup():
    tasks: Dict[ int, QueueWaitingTask ] = {}
    
    def __init__( self,
                 tasks: Dict[ int, QueueWaitingTask ] = {}
                ) -> None:
        self.tasks = tasks

    def __repr__( self ) -> str:
        return '<QueueWaitingGroup>'

class QueueWaitingTask():
    task_id: int = 0
    request: models.DownloadRequest

    def __init__( self,
                 task_id: int,
                 request: models.DownloadRequest,
                ) -> None:
        self.task_id = task_id
        self.request = request

    def __repr__( self ) -> str:
        return '<QueueWaitingTask '+str( {
            'task_id': self.task_id,
            'request': self.request,
        } )+'>'

####

class QueueRunning():
    tasks: Dict[ int, QueueRunningTask ] = {}
    
    def __init__( self,
                 tasks: Dict[ int, QueueRunningTask ] = {}
                ) -> None:
        self.tasks = tasks

    def __repr__( self ) -> str:
        return '<QueueRunning>'

    async def Exists( self, task_id: int ) -> bool:
        ok: bool = task_id in self.tasks
        return ok

    async def GetTask( self, task_id: int ) -> QueueRunningTask | None:
        ok: bool = task_id in self.tasks
        if ok:
            task: QueueRunningTask = self.tasks[ task_id ]
            return task
        return None

    async def SetTask( self, task: QueueRunningTask ) -> bool:
        self.tasks[ task.task_id ] = task
        return True

    async def RemTask( self, task_id: int ) -> bool:
        ok: bool = task_id in self.tasks
        if ok:
            task: QueueRunningTask = self.tasks[ task_id ]
            if task.proc:
                task.proc.terminate()
                task.proc.close()
            del self.tasks[ task_id ]
            return True
        return False

class QueueRunningTask():
    task_id:    int = 0
    user_id:    int = 0
    site:       str = ""
    proc:       Process
    cancelled:  Value

    def __init__( self,
                 task_id:    int = 0,
                 user_id:    int = 0,
                 site:       str = "",
                 cancelled:  Value = False,
                ) -> None:
        self.task_id = task_id
        self.user_id = user_id
        self.site = site
        self.cancelled = cancelled

    def __repr__( self ) -> str:
        return '<QueueWaitingTask>'

####

class DownloaderStep():
	CANCELLED = 99
	ERROR = 98
	IDLE = 0
	WAIT = 1
	INIT = 2
	RUNNING = 3
	PROCESSING = 4
	DONE = 5

class DownloaderBase():
    request:      models.DownloadRequest
    downloader:   QueueConfigDownloaderExec = None,
    save_folder:  str | os.PathLike = ""
    exec_folder:  str | os.PathLike = ""
    temp_folder:  str | os.PathLike = ""
    compression:  Dict[ str, str | os.PathLike ] = {}
    cancelled:    Value
    statuses:     Queue = None
    results:      Queue = None

    def __init__( self,
                 request:      models.DownloadRequest,
                 downloader:   QueueConfigDownloaderExec = None,
                 save_folder:  str | os.PathLike = "",
                 exec_folder:  str | os.PathLike = "",
                 temp_folder:  str | os.PathLike = "",
                 compression:  Dict[ str, str | os.PathLike ] = {},
                 cancelled:    Value = False,
                 statuses:     Queue = None,
                 results:      Queue = None,
                ):
        self.request =      request
        self.downloader =   downloader
        self.save_folder =  save_folder
        self.exec_folder =  exec_folder
        self.temp_folder =  temp_folder
        self.compression =  compression
        self.cancelled =    cancelled
        self.statuses =     statuses
        self.results =      results