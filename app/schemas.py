from __future__ import annotations

import os
from pydantic import BaseModel
from app import variables, models
from typing import Callable, Optional, Type, Any, List, Dict

class SiteCheckRequest(BaseModel):
    site: str

class SiteCheckResponse(BaseModel):
    allowed: bool
    parameters: list[str]
    formats: list[str]

class SiteListResponse(BaseModel):
    sites: list[str]

class DownloadRequest(BaseModel):
    task_id:    int | None = None
    user_id:    int
    bot_id:     str
    chat_id:    int
    message_id: int
    site:       str
    url:        str
    start:      int | None = 0
    end:        int | None = 0
    format:     str | None = "fb2"
    login:      str | None = ""
    password:   str | None = ""
    images:     bool | None = False
    cover:      bool | None = False
    proxy:      str | None = ""

    class Config:
        from_attributes = True

class DownloadResponse(BaseModel):
    status:  bool = False
    message: str = ""
    task_id: int | None = None

class DownloadCancel(BaseModel):
    task_id:    int

class DownloadResult(BaseModel):
    task_id:    int
    user_id:    int
    bot_id:     str
    chat_id:    int
    message_id: int
    status:     int
    site:       str
    text:       str
    cover:      str | os.PathLike
    files:      list[str | os.PathLike]
    orig_size:  int
    oper_size:  int

    class Config:
        from_attributes = True

class DownloadStatus(BaseModel):
    task_id:    int
    user_id:    int
    bot_id:     str
    chat_id:    int
    message_id: int
    text:       str
    status:     int