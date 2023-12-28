import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import Integer, BigInteger, Boolean, String, Text, UniqueConstraint, Date, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import relationship

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] =            mapped_column( 'id', BigInteger, primary_key=True )
    username: Mapped[str] =      mapped_column( 'username', String(100), nullable=False )
    setuped: Mapped[dict] =      mapped_column( 'setuped', Boolean, default=False )
    ask_share: Mapped[dict] =    mapped_column( 'ask_share', Boolean, default=True )
    interact_mode: Mapped[int] = mapped_column( 'interact_mode', Integer, default=0 )
    format: Mapped[dict] =       mapped_column( 'format', String(20), default='fb2' )
    cover: Mapped[dict] =        mapped_column( 'cover', Boolean, default=True )
    images: Mapped[dict] =       mapped_column( 'images', Boolean, default=True )

class UserStat(Base):
    __tablename__ = 'users_stats'
    __table_args__ = ( UniqueConstraint("user_id", "day", name="user_day_index"), )

    id: Mapped[int] =        mapped_column( 'id', BigInteger, primary_key=True )
    user_id: Mapped[int] =   mapped_column( 'user_id', BigInteger, nullable=True )
    day: Mapped[datetime] =  mapped_column( 'day', Date, default=datetime.today )
    downloads: Mapped[int] = mapped_column( 'downloads', Integer, default=0 )
    orig_size: Mapped[int] = mapped_column( 'orig_size', BigInteger, default=0 )
    oper_size: Mapped[int] = mapped_column( 'oper_size', BigInteger, default=0 )

class UserAuth(Base):
	__tablename__ = 'users_auths'

	id: Mapped[int] =              mapped_column( 'id', BigInteger, primary_key=True )
	user_id: Mapped[int] =         mapped_column( 'user_id', BigInteger, nullable=False, index=True )
	site: Mapped[str] =            mapped_column( 'site', String(240), nullable=False, index=True )
	login: Mapped[str] =           mapped_column( 'login', Text, nullable=True )
	password: Mapped[str] =        mapped_column( 'password', Text, nullable=True )
	created_on: Mapped[datetime] = mapped_column( 'created_on', Date, default=datetime.today )

	def get_name(self):
		_r = self.login
		if self.created_on:
			_r = _r+' [от '+str(self.created_on.strftime('%d.%m.%Y'))+']'
		return _r

class InlineDownloadRequest(Base):
	__tablename__ = 'inline_download_requests'

	id: Mapped[int] =              mapped_column( 'id', BigInteger, primary_key=True )
	user_id: Mapped[int] =         mapped_column( 'user_id', BigInteger, nullable=False, index=True )
	chat_id: Mapped[int] =         mapped_column( 'chat_id', BigInteger, nullable=False, index=True )
	message_id: Mapped[int] =      mapped_column( 'message_id', BigInteger, nullable=True, index=True )
	# 
	use_paging: Mapped[bool] =     mapped_column( 'use_paging', Boolean, default=False )
	use_auth: Mapped[bool] =       mapped_column( 'use_auth', Boolean, default=False )
	use_images: Mapped[bool] =     mapped_column( 'use_images', Boolean, default=False )
	use_cover: Mapped[bool] =      mapped_column( 'use_cover', Boolean, default=False )
	force_images: Mapped[bool] =   mapped_column( 'force_images', Boolean, default=False )
	# 
	link: Mapped[str] =            mapped_column( 'link', Text, default='')
	site: Mapped[str] =            mapped_column( 'site', Text, default='')
	auth: Mapped[str] =            mapped_column( 'auth', Text, default='')
	start: Mapped[int] =           mapped_column( 'start', Integer, default=0 )
	end: Mapped[int] =             mapped_column( 'end', Integer, default=0 )
	format: Mapped[str] =          mapped_column( 'format', Text, default='')
	images: Mapped[bool] =         mapped_column( 'images', Boolean, default=True )
	cover: Mapped[bool] =          mapped_column( 'cover', Boolean, default=True )

class ACL(Base):
	__tablename__ = 'acl'
	__table_args__ = ( UniqueConstraint("user_id", "premium", name="user_premium_index"), UniqueConstraint("user_id", "banned", name="user_banned_index") )

	user_id: Mapped[int] =    mapped_column( 'user_id', BigInteger, primary_key=True, nullable=False, index=True )
	premium: Mapped[bool] =   mapped_column( 'premium', Boolean, default=False )
	banned: Mapped[bool] =    mapped_column( 'banned', Boolean, default=False )
	reason: Mapped[str] =     mapped_column( 'reason', Text )
	until: Mapped[datetime] = mapped_column( 'until', DateTime, default=datetime.now )