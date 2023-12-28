# -*- coding: utf-8 -*-
# pylint: disable=C0103,R0903
from __future__ import annotations
from dataclasses import dataclass, field

import os
import asyncio
import traceback
import logging
import ujson
import redis.asyncio as redis
from datetime import datetime, timedelta
from multiprocessing import Process
from dacite import from_dict, Config as dConfig
from typing import Callable, Optional, List, Dict
from aiogram import Bot as aBot
from aiogram.fsm.state import State, StatesGroup
from bot import models, variables
from bot.db import DBE

logger = logging.getLogger(__name__)

####

class Bot(aBot):
    DB:  DBE
    RD:  redis.Redis
    CNF: BotConfig
    EncryptKey: bytes = b'haCWnY-UmoMMxqiiBUIZFHgRbET436SxR45W4r4aqno='

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(token='0000000000:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', *args, **kwargs)
    
    def __escape_md__( self, text: str ) -> str:
        text = text\
            .replace('_', '\\_')\
            .replace('*', '\\*')\
            .replace('[', '\\[')\
            .replace(']', '\\]')\
            .replace('(', '\\(')\
            .replace(')', '\\)')\
            .replace('~', '\\~')\
            .replace('`', '\\`')\
            .replace('>', '\\>')\
            .replace('#', '\\#')\
            .replace('+', '\\+')\
            .replace('-', '\\-')\
            .replace('=', '\\=')\
            .replace('|', '\\|')\
            .replace('{', '\\{')\
            .replace('}', '\\}')\
            .replace('.', '\\.')\
            .replace('!', '\\!')
        return text

    async def updateConfig(self, config_file: str | os.PathLike) -> None:
        if not os.path.exists(config_file):
            raise FileNotFoundError(config_file)

        with open(config_file,'r',encoding='utf-8') as _config_file:
            _config = _config_file.read()

            try:
                data = ujson.loads(_config)
                config = from_dict(data_class=variables.BotConfig, data=data, config=dConfig(check_types=False))
                
                self.CNF = config
                self.__token = self.CNF.token
            except Exception:
                traceback.print_exc()

###

class AuthForm(StatesGroup):
    base_message = State()
    last_message = State()
    site = State()
    login = State()
    password = State()

####

@dataclass
class BotConfig():
    bot_host:   str
    queue_host: str
    token:      str
    free_limit: int = 10
    formats:    Dict[str,str] = field(default_factory=dict)
    demo:       Dict[str,str] = field(default_factory=dict)

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