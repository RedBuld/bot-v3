import os
import json
import traceback
import logging
import asyncio
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import Insert as insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from bot import variables, models

logger = logging.getLogger(__name__)

class DBE(object):
    _engine: AsyncEngine
    _async_session: async_sessionmaker[AsyncSession]

    __server: str = ""

    def __init__(self):
        self._engine = None
        self._async_session = None
        return
    
    async def Start(self) -> None:
        if self._engine:
            return

        while True:
            logger.info('DB: started')
            try:
                if not self._engine:
                    self._engine = create_async_engine(
                        self.__server,
                        pool_size=5, max_overflow=5, pool_recycle=60, pool_pre_ping=True
                    )
                    self._async_session = async_sessionmaker(self._engine, expire_on_commit=False)

                await self.createDB()
                return
            except:
                await asyncio.sleep(1)
                continue
    
    async def Stop(self) -> None:
        if self._engine:
            logger.info('DB: finished')
            await self._engine.dispose()
            self._engine = None
            self._async_session = None

    async def createDB(self) -> None:
        if self._engine:
            logger.info('DB: validate database')
            async with self._engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all, checkfirst=True)
                await conn.commit()
    
    async def updateConfig(self, config_file: str | os.PathLike) -> None:

        if not os.path.exists(config_file):
            raise FileNotFoundError(config_file)

        with open(config_file,'r') as _config_file:
            _config = _config_file.read()

            try:
                data = json.loads(_config)
                self.__server = data['server'] if 'server' in data else ""
            except:
                traceback.print_exc()
        
        if self._engine:
            await self.Stop()
            await self.Start()

    async def saveUser(self, user: models.User) -> None:
        try:
            async with self._async_session() as session:
                try:
                    session.add(user)
                    await session.commit()
                finally:
                    await session.close()
        except IntegrityError:
            pass
        except asyncio.CancelledError as e:
            pass
        except:
            traceback.print_exc()

    async def getUser( self, user_id: int ) -> models.User:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.User).where(models.User.id==user_id))
                    result = query.scalars().one_or_none()
                    if not result:
                        return None
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUser( user_id=user_id )

    async def getUserSetuped( self, user_id: int ) -> int:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.User.setuped).where(models.User.id==user_id))
                    result = query.scalars().one_or_none()
                    session.expunge_all()
                    return result == 1
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUserSetuped( user_id=user_id )

    async def getUserInteractMode( self, user_id: int ) -> int:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.User.interact_mode).where(models.User.id==user_id))
                    result = query.scalars().one_or_none()
                    session.expunge_all()
                    return result == 1
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUserInteractMode( user_id=user_id )
    
    async def getUserAuthedSites( self, user_id: int ) -> list[models.UserAuth]:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.UserAuth.site).distinct().where(models.UserAuth.user_id==user_id))
                    result = query.scalars().all()
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUserAuthedSites( user_id=user_id )

    async def getUserAuthsForSite( self, user_id: int, site: str ) -> list[models.UserAuth]:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.UserAuth).where(models.UserAuth.user_id==user_id, models.UserAuth.site==site))
                    result = query.scalars().all()
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUserAuthsForSite( user_id=user_id, site=site )

    async def saveUserAuth( self, user_id: int, site: str, login: str, password: str ) -> models.UserAuth:
        try:
            async with self._async_session() as session:
                try:
                    auth = models.UserAuth()
                    auth.user_id = user_id
                    auth.site = site
                    auth.login = login
                    auth.password = password
                    session.add(auth)
                    await session.commit()
                    session.expunge(auth)
                    return auth
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.saveUserAuth( user_id=user_id, site=site, login=login, password=password )

    async def deleteUserAuth( self, user_id: int, auth_id: int ) -> None:
        try:
            async with self._async_session() as session:
                try:
                    await session.execute(
                        delete(models.UserAuth)\
                            .where(
                                models.UserAuth.user_id==user_id,
                                models.UserAuth.id==auth_id
                            )
                        )
                    await session.commit()
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.deleteUserAuth( user_id, user_id=user_id, auth_id=auth_id )

    async def getUserAuth( self, user_id: int, auth_id: int ) -> models.UserAuth:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.UserAuth).where(models.UserAuth.user_id==user_id, models.UserAuth.id==auth_id))
                    result = query.scalars().one_or_none()
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getUserAuth( user_id=user_id, auth_id=auth_id )

    async def getUserUsage( self, user_id: int ) -> int:
        return 0

    async def updateUserStat(self, result: dict) -> None:
        pass
        # try:
        #     async with self._engine.begin() as conn:
        #         ss = {
        #             'site': result['site'],
        #             'day': datetime.today(),
        #             'success': success,
        #             'failure': failure,
        #             'orig_size': result['orig_size'],
        #             'oper_size': result['oper_size'],
        #         }
        #         await conn.execute(
        #             insert(models.SiteStat.__table__).values(**ss).on_conflict_do_update(
        #                 index_elements=[models.SiteStat.site, models.SiteStat.day],
        #                 set_={
        #                     'success': models.SiteStat.success + success,
        #                     'failure': models.SiteStat.failure + failure,
        #                     'orig_size': models.SiteStat.orig_size + result['orig_size'],
        #                     'oper_size': models.SiteStat.oper_size + result['oper_size'],
        #                 }
        #             )
        #         )
        #         await conn.commit()
        #         await conn.close()
        # except asyncio.CancelledError as e:
        #     raise e
        # except:
        #     traceback.print_exc()
        #     await asyncio.sleep(1)
        #     return await self.updateSiteStat(result)
    
    async def saveInlineDownloadRequest(self, request: models.InlineDownloadRequest) -> models.InlineDownloadRequest:
        try:
            async with self._async_session() as session:
                try:
                    session.add(request)
                    await session.commit()
                    session.expunge(request)
                    return request
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.saveInlineDownloadRequest( request=request )
    
    async def getInlineDownloadRequest(self, user_id: int, chat_id: int, message_id: int) -> models.InlineDownloadRequest | None:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(
                        select(models.InlineDownloadRequest)\
                            .where(
                                models.InlineDownloadRequest.user_id==user_id,
                                models.InlineDownloadRequest.chat_id==chat_id,
                                models.InlineDownloadRequest.message_id==message_id
                            )
                        )
                    result = query.scalars().one_or_none()
                    if not result:
                        return None
                    session.expunge(result)
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getInlineDownloadRequest(user_id=user_id, chat_id=chat_id, message_id=message_id)

    async def deleteInlineDownloadRequest(self, user_id: int, chat_id: int, message_id: int) -> None:
        try:
            async with self._async_session() as session:
                try:
                    await session.execute(
                        delete(models.InlineDownloadRequest)\
                            .where(
                                models.InlineDownloadRequest.user_id==user_id,
                                models.InlineDownloadRequest.chat_id==chat_id,
                                models.InlineDownloadRequest.message_id==message_id
                            )
                        )
                    await session.commit()
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.deleteInlineDownloadRequest( user_id=user_id, chat_id=chat_id, message_id=message_id )