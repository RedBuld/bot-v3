import os
import json
import traceback
import logging
import asyncio
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import Insert as insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from app import variables, models

logger = logging.getLogger(__name__)

class DBE(object):
    _engine: AsyncEngine
    _async_session: async_sessionmaker[AsyncSession]

    __server: str = "postgresql+asyncpg://postgres:secret@localhost:5432/download-center"

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

        with open(config_file,'r',encoding='utf-8') as _config_file:
            _config = _config_file.read()

            try:
                data = json.loads(_config)
                self.__server = data['server'] if 'server' in data else ""
            except:
                traceback.print_exc()
        
        if self._engine:
            await self.Stop()
            await self.Start()

    async def saveRequest(self, request: dict) -> models.DownloadRequest:
        try:
            async with self._async_session() as session:
                try:
                    result = models.DownloadRequest(**request)
                    session.add(result)
                    await session.commit()
                    session.expunge(result)
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.saveRequest(request)
    
    async def getRequest(self, task_id: int) -> models.DownloadRequest | None:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.DownloadRequest).where(models.DownloadRequest.task_id==task_id))
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
            return await self.getRequest(task_id)
    
    async def getAllRequests(self) -> list[models.DownloadRequest]:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.DownloadRequest))
                    result = query.scalars()
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getAllRequests()
    
    async def deleteRequest(self, task_id: int) -> None:
        try:
            async with self._async_session() as session:
                try:
                    await session.execute(delete(models.DownloadRequest).where(models.DownloadRequest.task_id==task_id))
                    await session.commit()
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.deleteRequest(task_id)

    async def saveResult(self, _result: dict) -> models.DownloadResult:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.DownloadResult).where(models.DownloadResult.task_id==_result['task_id']))
                    result = query.scalars().one_or_none()
                    if not result:
                        result = models.DownloadResult(**_result)
                    session.add(result)
                    await session.commit()
                    session.expunge(result)
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.saveResult(_result)
    
    async def getResult(self, task_id: int) -> models.DownloadResult | None:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.DownloadResult).where(models.DownloadResult.task_id==task_id))
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
            return await self.getResult(task_id)
    
    async def getAllResults(self) -> list[models.DownloadResult]:
        try:
            async with self._async_session() as session:
                try:
                    query = await session.execute(select(models.DownloadResult))
                    result = query.scalars()
                    session.expunge_all()
                    return result
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.getAllResults()
    
    async def deleteResult(self, task_id: int) -> None:
        try:
            async with self._async_session() as session:
                try:
                    await session.execute(delete(models.DownloadResult).where(models.DownloadResult.task_id==task_id))
                    await session.commit()
                finally:
                    await session.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.deleteResult(task_id)
    
    async def updateSiteStat(self, result: dict) -> None:

        if result['status'] == variables.DownloaderStep.CANCELLED:
            return

        success = 1 if result['status'] == variables.DownloaderStep.DONE else 0
        failure = 1 if result['status'] == variables.DownloaderStep.ERROR else 0

        try:
            async with self._engine.begin() as conn:
                ss = {
                    'site': result['site'],
                    'day': datetime.today(),
                    'success': success,
                    'failure': failure,
                    'orig_size': result['orig_size'],
                    'oper_size': result['oper_size'],
                }
                await conn.execute(
                    insert(models.SiteStat.__table__).values(**ss).on_conflict_do_update(
                        index_elements=[models.SiteStat.site, models.SiteStat.day],
                        set_={
                            'success': models.SiteStat.success + success,
                            'failure': models.SiteStat.failure + failure,
                            'orig_size': models.SiteStat.orig_size + result['orig_size'],
                            'oper_size': models.SiteStat.oper_size + result['oper_size'],
                        }
                    )
                )
                await conn.commit()
                await conn.close()
        except asyncio.CancelledError as e:
            raise e
        except:
            traceback.print_exc()
            await asyncio.sleep(1)
            return await self.updateSiteStat(result)