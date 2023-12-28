import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import BigInteger, Boolean, String, Text, UniqueConstraint, Date
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import relationship

class Base(AsyncAttrs, DeclarativeBase):
    pass

class SiteStat(Base):
    __tablename__ = 'sites_stats'
    __table_args__ = ( UniqueConstraint("site", "day", name="site_day_index"), )

    id: Mapped[int] =        mapped_column('id', BigInteger, primary_key=True)
    site: Mapped[str] =      mapped_column('site', String(100), nullable=False)
    day: Mapped[datetime] =  mapped_column('day', Date, default=datetime.today)
    success: Mapped[int] =   mapped_column('success', BigInteger, default=1)
    failure: Mapped[int] =   mapped_column('failure', BigInteger, default=1)
    orig_size: Mapped[int] = mapped_column('orig_size', BigInteger, default=0)
    oper_size: Mapped[int] = mapped_column('oper_size', BigInteger, default=0)

class DownloadRequest(Base):
    __tablename__ = "download_requests"

    task_id: Mapped[int] =    mapped_column('task_id', BigInteger, primary_key=True)
    user_id: Mapped[int] =    mapped_column('user_id', BigInteger, default=0)
    bot_id: Mapped[str] =     mapped_column('bot_id', String(10), default="")
    chat_id: Mapped[int] =    mapped_column('chat_id', BigInteger, default=0)
    message_id: Mapped[int] = mapped_column('message_id', BigInteger, default=0)
    site: Mapped[str] =       mapped_column('site', String(100), default="")
    url: Mapped[str] =        mapped_column('url', Text, default="")
    start: Mapped[int] =      mapped_column('start_chapter', BigInteger, default=0)
    end: Mapped[int] =        mapped_column('end_chapter', BigInteger, default=0)
    format: Mapped[str] =     mapped_column('format', String(20), default="fb2")
    login: Mapped[str] =      mapped_column('login', Text, default="")
    password: Mapped[str] =   mapped_column('password', Text, default="")
    images: Mapped[bool] =    mapped_column('images', Boolean, default=True)
    cover: Mapped[bool] =     mapped_column('cover', Boolean, default=False)
    proxy: Mapped[str] =      mapped_column('proxy', Text, default="")

    def __repr__(self) -> str:
        return str({
            'task_id':    self.task_id,
            'user_id':    self.user_id,
            'bot_id':     self.bot_id,
            'chat_id':    self.chat_id,
            'message_id': self.message_id,
            'site':       self.site,
            'url':        self.url,
            'start':      self.start,
            'end':        self.end,
            'format':     self.format,
            'login':      self.login,
            'password':   self.password,
            'images':     self.images,
            'cover':      self.cover,
            'proxy':      self.proxy,
        })

class DownloadResult(Base):
    __tablename__ = "download_results"

    secure: str =             ""
    task_id: Mapped[int] =    mapped_column('task_id', BigInteger, primary_key=True)
    user_id: Mapped[int] =    mapped_column('user_id', BigInteger, default=0)
    bot_id: Mapped[str] =     mapped_column('bot_id', String(10), default="")
    chat_id: Mapped[int] =    mapped_column('chat_id', BigInteger, default=0)
    message_id: Mapped[int] = mapped_column('message_id', BigInteger, default=0)
    status: Mapped[int] =     mapped_column('status', BigInteger, default=1)
    site: Mapped[str] =       mapped_column('site', String(100), default="")
    text: Mapped[str] =       mapped_column('text', Text, default="")
    cover: Mapped[str] =      mapped_column('cover', Text, default="")
    _files: Mapped[str] =     mapped_column('files', Text, default="")
    orig_size: Mapped[int] =  mapped_column('orig_size', BigInteger, default=0)
    oper_size: Mapped[int] =  mapped_column('oper_size', BigInteger, default=0)

    @property
    def files(self):
        return json.loads(self._files)

    @files.setter
    def files(self, value):
        self._files = json.dumps(value)