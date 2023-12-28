import os
import sys
import asyncio
import orjson
import logging
import traceback
import markdownify
import shutil
import subprocess
from multiprocessing import Value
from multiprocessing import Queue
from typing import Dict, Any
from app import models, schemas, variables

logger = logging.getLogger('downloader-process')

def start_downloader(
        request:      models.DownloadRequest,
        downloader:   variables.QueueConfigDownloaderExec = None,
        save_folder:  str | os.PathLike = "",
        exec_folder:  str | os.PathLike = "",
        temp_folder:  str | os.PathLike = "",
        compression:  Dict[ str, str | os.PathLike ] = {},
        cancelled:    Value = None,
        statuses:     Queue = None,
        results:      Queue = None
    ):
    downloader = Downloader(
        request =      request,
        downloader =   downloader,
        save_folder =  save_folder,
        exec_folder =  exec_folder,
        temp_folder =  temp_folder,
        compression =  compression,
        cancelled =    cancelled,
        statuses =     statuses,
        results =      results
    )
    downloader.Start()

class Downloader(variables.DownloaderBase):
    done: bool = False
    step: int = variables.DownloaderStep.IDLE
    prev_step: int = variables.DownloaderStep.IDLE
    message: str = ""
    prev_message: str = ""
    res: Queue = None

    proc: asyncio.subprocess.Process
    temp: Dict[str, Any]
    
    def __repr__(self) -> str:
        return str({
            'cancelled': self.cancelled,
            'request': self.request,
            'downloader':  self.downloader,
            'save_folder': self.save_folder,
            'exec_folder': self.exec_folder,
            'temp_folder': self.temp_folder,
            'compression': self.compression,
            'step': self.step,
            'prev_step': self.prev_step,
            'message': self.message,
            'prev_message': self.prev_message,
            'proc': self.proc,
            'temp': self.temp,
        })


    def __escape_err__( self, text: str ) -> str:
        text = text\
            .replace('`', '\\`')\
            .replace('\\', '\\\\')
        return text


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


    def __is_step__(self, check_step: int) -> bool:
        return self.step == check_step


    def __set_step__(self, new_step: int) -> None:
        self.prev_step = self.step
        self.step = new_step


    def __set_message__(self, new_message: str) -> None:
        self.prev_message = self.message
        self.message = new_message


    def Start(self) -> None:
        self.step = variables.DownloaderStep.IDLE
        self.prev_step = variables.DownloaderStep.IDLE
        self.message = ""
        self.prev_message = ""

        self._folder = os.path.join( self.save_folder, str(self.request.task_id) )

        self.proc = None
        self.temp = {
            'text':      "",
            'cover':     "",
            'file':      "",
            'files':     [],
            'chapters':  0,
            'orig_size': 0,
            'oper_size': 0,
        }

        self.done = False
        # self.decoder = 'cp1251' if os.name == 'nt' else 'utf-8'
        self.decoder = 'utf-8'
        self.file_limit = 49_000_000
        # 
        logging.basicConfig(
            # filename="C:\\Users\\RedBuld\\Pictures\\log.txt",
            format='\x1b[32m%(levelname)s\x1b[0m:     %(name)s[%(process)d] %(asctime)s - %(message)s',
            level=logging.INFO
        )
        logger.info('Downloader: Start')
        self.__set_step__(variables.DownloaderStep.WAIT)
        self.__set_message__('Загрузка начата')
        asyncio.get_event_loop().run_until_complete( self.start() )


    def Stop(self) -> None:
        if self.__is_step__(variables.DownloaderStep.CANCELLED):
            return

        self.done = True

        logger.info('Downloader: Stop')
        self.__set_step__(variables.DownloaderStep.CANCELLED)
        self.__set_message__('Загрузка отменена')
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
        
    ###

    async def start(self) -> None:
        asyncio.create_task( self.pulse() )
        await asyncio.sleep(0)

        self.__set_step__(variables.DownloaderStep.INIT)

        try:
            await self.download() # can raise error
            await self.process() # can't raise error
        except Exception as e:
            traceback.print_exc()
            self.done = True
            await self._error(e)
        finally:
            self.done = True
            await self._result()

    async def pulse(self) -> None:
        while not self.done:
            await self._status()
            await asyncio.sleep(5)

    async def download(self) -> None:
        try:
            shutil.rmtree( self._folder )
        except:
            pass
        os.makedirs(self._folder, exist_ok=True)

        args: list[str] = []

        args.append('--save')
        args.append(f'{self._folder}')

        if self.request.url:
            args.append('--url')
            args.append(f'{self.request.url}')

        if self.request.format:
            args.append('--format')
            args.append(f'{self.request.format},json_lite')
        else:
            args.append('--format')
            args.append(f'fb2,json_lite')

        if self.request.start:
            args.append('--start')
            args.append(f'{self.request.start}')

        if self.request.end:
            args.append('--end')
            args.append(f'{self.request.end}')

        if self.request.proxy:
            args.append('--proxy')
            args.append(f'{self.request.proxy}')
            args.append('--timeout')
            args.append('120')
        else:
            args.append('--timeout')
            args.append('60')

        if self.request.cover:
            args.append('--cover')

        if self.request.images == '0':
            args.append('--no-image')

        if self.request.login and self.request.password:

            if  not self.request.login.startswith('/') and not self.request.login.startswith('http:/') and not self.request.login.startswith('https:/')\
                and\
                not self.request.password.startswith('/') and not self.request.password.startswith('http:/') and not self.request.password.startswith('https:/'):
                args.append('--login')
                args.append(f'{self.request.login}')
                args.append('--password')
                args.append(f'{self.request.password}')

        self.proc = await asyncio.create_subprocess_exec(
            os.path.join(self.exec_folder, self.downloader.folder, self.downloader.exec),
            *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.__set_step__(variables.DownloaderStep.RUNNING)
        
        while self.proc.returncode is None and not self.cancelled.value:
            _msg = ''
            new_line = await self.proc.stdout.readline()
            if new_line:
                _msg = new_line.strip().decode(self.decoder, errors='replace')
                if _msg.startswith('Загружена картинка'):
                    _msg = ''
                elif _msg.startswith('Начинаю сохранение книги'):
                    _msg = 'Сохраняю файлы'
                elif 'успешно сохранена' in _msg:
                    _msg = 'Сохраняю файлы'
            if _msg:
                self.__set_message__(_msg)
            await asyncio.sleep(0)
        
        if self.cancelled.value:
            return self.Stop()
        
        if self.proc.returncode != 0:
            raise ProcessLookupError('Process force-killed')
        
        t = os.listdir(self._folder)
        if len(t) == 0:
            raise FileExistsError('No files found')
    
    async def process(self) -> None:

        if self.cancelled.value:
            return self.Stop()

        self.__set_step__(variables.DownloaderStep.PROCESSING)
        self.__set_message__('Обработка файлов')

        await self.check_files()

        if self.cancelled.value:
            return self.Stop()

        await self.rename_files()

        if self.cancelled.value:
            return self.Stop()

        await self.process_files()

        if self.cancelled.value:
            return self.Stop()

        self.__set_step__(variables.DownloaderStep.DONE)
        self.__set_message__('Выгрузка файлов')

    async def check_files(self) -> None:

        trash = []
        
        files = os.listdir(self._folder)
        for file in files:
            fname, extension = os.path.splitext(file)
            extension = extension[1:]

            if extension == 'json':
                _json = os.path.join(self._folder, file)
                self.temp['text'] = await self.process_caption( _json )
                trash.append( _json )

            elif extension == self.request.format:
                self.temp['file'] = os.path.join(self._folder, file)

            elif extension in ['jpg','jpeg','png','gif'] and fname.endswith('_cover'):
                self.temp['cover'] = os.path.join(self._folder, file)

            else:
                trash.append( os.path.join(self._folder, file) )

        for file in trash:
            os.remove(file)
    
    async def rename_files(self) -> None:

        suffix = ''
        if self.request.start or self.request.end:
            _chapters = self.temp['chapters']
            if _chapters > 0:
                _start = self.request.start
                _end = self.request.end

                if _start and _end:
                    _start = int(_start)
                    _end = int(_end)
                    if _start > 0 and _end > 0:
                        suffix = f'-parted-from-{_start}-to-{_end}'
                    elif _start > 0 and _end < 0:
                        __end = _start+_chapters
                        suffix = f'-parted-from-{_start}-wo-last-{__end}'
                elif _start and not _end:
                    _start = int(_start)
                    if _start > 0:
                        __end = _start+_chapters
                        suffix = f'-parted-from-{_start}-to-{__end}'
                    else:
                        if abs(_start) >= _chapters:
                            suffix = f'-parted-last-{_start}'
                elif _end and not _start:
                    _end = int(_end)
                    if _end > 0:
                        suffix = f'-parted-from-1-to-{_chapters}'
                    else:
                        _end = abs(_end)
                        if _end >= _chapters:
                            suffix = f'-parted-from-1-to-{_chapters}'
                        else:
                            suffix = f'-parted-wo-last-{_end}'

        if suffix != '':
            original_file = self.temp['file']

            path, file = os.path.split(original_file)
            old_name, extension = os.path.splitext(file)

            new_name = old_name+suffix+extension
            new_file = os.path.join(path, new_name)

            os.rename(original_file, new_file)

            self.temp['file'] = new_file

    async def process_files(self) -> None:

        if self.temp['file']:
            result_files = []
            original_file = self.temp['file']

            self.temp['orig_size'] = os.path.getsize(original_file)
            file_limit = self.file_limit

            if self.temp['orig_size'] < file_limit:
                self.temp['files'] = [original_file]
                self.temp['file'] = None
            else:
                self.__set_message__('Архивация файлов')

                file = os.path.basename(original_file)
                file_name, _ = os.path.splitext(file)

                splitted_folder = os.path.join(self._folder, 'splitted')
                os.makedirs(splitted_folder, exist_ok=True)

                zip_file = os.path.join(splitted_folder, f'{file_name}.zip')

                for key, executable in self.compression.items():
                    if os.path.exists( executable ):
                        if key == 'winrar':
                            sfs = int(file_limit / 1000 / 1000)
                            _sfs = f'{sfs}m'
                            args = ['a', '-afzip', f'-v{_sfs}', '-ep', '-m0', zip_file, original_file]
                        if key == '7z':
                            sfs = int(file_limit / 1000 / 1000)
                            _sfs = f'{sfs}m'
                            args = ['a', '-tzip', f'-v{_sfs}', '-mx0', zip_file, original_file]

                        self.proc = await asyncio.create_subprocess_exec(
                            executable,
                            *args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        await self.proc.wait()

                        if self.proc.returncode == 0:
                            try:
                                os.unlink(file)
                            except:
                                pass

                            t = os.listdir(splitted_folder)
                            for x in t:
                                part_file = os.path.join(splitted_folder, x)
                                result_files.append( part_file )
                                self.temp['oper_size'] += os.path.getsize(part_file)

                        if len(result_files) > 0:
                            self.temp['files'] = result_files
                            self.temp['file'] = None
    
    async def process_caption(self, filepath: str) -> str:
        book_title: str = ""
        book_url: str = ""
        seria_name: str = ""
        seria_url: str = ""
        authors: list[str] = []
        chapters: str = ""

        with open(filepath, "r") as f:
            _raw: str = f.read()
            try:
                _json: Dict[str, Any] = orjson.loads(_raw)
            except:
                return ''

            if 'Title' in _json and _json['Title']:
                book_title = _json['Title']
                book_title = self.__escape_md__( book_title )

            if 'Url' in _json and _json['Url']:
                book_url = _json['Url']

            if 'Author' in _json:
                if 'Name' in _json['Author']:
                    _a_name: str = _json['Author']['Name']
                    # _a_name = self.__escape_md__( _a_name )
                    if 'Url' in _json['Author']:
                        _a_url: str = _json['Author']['Url']
                        authors.append( f'<a href="{_a_url}">{_a_name}</a>' )
                    else:
                        authors.append( _a_name )

            if 'CoAuthors' in _json and _json['CoAuthors']:
                for _author in _json['CoAuthors']:
                    if 'Name' in _author:
                        _c_name: str = _author['Name']
                        # _c_name = self.__escape_md__( _c_name )
                        if 'Url' in _author:
                            _c_url: str = _author['Url']
                            authors.append( f'<a href="{_c_url}">{_c_name}</a>' )
                        else:
                            authors.append( _c_name )

            if 'Seria' in _json and _json['Seria']:
                if 'Name' in _json['Seria']:
                    seria_name = _json['Seria']['Name']
                    seria_name = self.__escape_md__( seria_name )
                    if 'Number' in _json['Seria']:
                        seria_name += ' \#' + str(_json['Seria']['Number'])
                    if 'Url' in _json['Seria']:
                        seria_url = _json['Seria']['Url']

            if 'Chapters' in _json and _json['Chapters']:
                total_chapters: int = 0
                valid_chapters: int = 0
                first_chapter: str = ''
                last_chapter: str = ''
                if len(_json['Chapters']) > 0:
                    for chapter in _json['Chapters']:
                        if chapter['Title']:
                            total_chapters += 1
                            if chapter['IsValid']:
                                valid_chapters += 1
                                if not first_chapter:
                                    first_chapter = chapter['Title']
                                last_chapter = chapter['Title']
                    first_chapter = self.__escape_md__( first_chapter )
                    last_chapter = self.__escape_md__( last_chapter )
                    if first_chapter and last_chapter:
                        if self.request.start or self.request.end:
                            chapters = f'Глав {valid_chapters} из {total_chapters}, с "{first_chapter}" по "{last_chapter}"'
                        else:
                            chapters = f'Глав {valid_chapters} из {total_chapters}, по "{last_chapter}"'
                    else:
                        chapters = f'Глав {valid_chapters} из {total_chapters}'
                self.temp['chapters'] = total_chapters

        result = ""
        if book_title and book_url:
            result += f'<a href="{book_url}">{book_title}</a><br>'
        elif book_title:
            result += f'{book_title}<br>'
        
        if len(authors) > 0:
            _a: str = ', '.join(authors)
            if len(authors) > 1:
                result += f'Авторы: {_a}<br>'
            else:
                result += f'Автор: {_a}<br>'
        
        if seria_name and seria_url:
            result += f'Серия: <a href="{seria_url}">{seria_name}</a><br>'
        elif seria_name:
            result += f'Серия: {seria_name}<br>'
        
        if chapters:
            result += "<br>"
            result += f'{chapters}'

        return markdownify.markdownify(result)

    # external data transfer

    async def _status(self):


        if self.message == self.prev_message:
            return

        status = schemas.DownloadStatus(
            task_id =    self.request.task_id,
            user_id =    self.request.user_id,
            bot_id =     self.request.bot_id,
            chat_id =    self.request.chat_id,
            message_id = self.request.message_id,
            text =       self.message,
            status =     self.step,
        )

        self.statuses.put( status.model_dump() )

        self.__set_message__(self.message)

    async def _error(self, err: Exception):
        if self.__is_step__(variables.DownloaderStep.CANCELLED):
            return

        self.__set_step__(variables.DownloaderStep.ERROR)
        self.temp['text'] = 'Произошла ошибка'
        proc_err = False
        if getattr(self,'proc'):
            error = await self.proc.stderr.read(-1)
            if error:
                error = error.strip().decode(self.decoder, errors='ignore')
                if error:
                    proc_err = True
                    self.temp['text'] = self.temp['text'] + ' ```\n'+ self.__escape_err__( error ) +'\n```'
        if err and not proc_err:
            self.temp['text'] = self.temp['text'] + ' ```\n'+ self.__escape_err__( str(err) ) +'\n```'

    async def _result(self):

        if self.step == variables.DownloaderStep.ERROR or self.step == variables.DownloaderStep.CANCELLED:
            try:
                shutil.rmtree( self._folder )
            except:
                pass
            self.temp['cover'] = ""
            self.temp['files'] = []
        
        result = schemas.DownloadResult(
            task_id =    self.request.task_id,
            user_id =    self.request.user_id,
            bot_id =     self.request.bot_id,
            chat_id =    self.request.chat_id,
            message_id = self.request.message_id,
            status =     self.step,
            site =       self.request.site,
            text =       self.temp['text'],
            cover =      self.temp['cover'],
            files =      self.temp['files'],
            orig_size =  self.temp['orig_size'],
            oper_size =  self.temp['oper_size'],
        )

        self.results.put( result.model_dump() )

        sys.exit(0)