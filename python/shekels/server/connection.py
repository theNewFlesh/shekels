from typing import Any, Optional

from multiprocessing import Pipe, Pool
from multiprocessing.managers import BaseManager
import datetime
import json

import shekels.server.server_tools as svt
# ------------------------------------------------------------------------------


class ConnectionLogger:
    def __init__(self, connection):
        self._connection = connection

    def get_log_dict(
        self,
        process,
        message=None,
        iterator=0,
        total=None,
        data=None,
        status='pending',
    ):
        # type: (str, Optional[str], int, Optional[int], Optional[Any], str) -> str
        '''
        Create a state log dictionary.

        Args:
            process (str): Process being logged.
            message (str, optional): Stateful message. Default: None.
            iterator (int): Current iteration in loop. Default: None.
            total (int, optional): Total iterations. Default: None.
            data (object, optional): Data related to state. Default: None.
            status (str, optional): Status of process. Default: 'pending'.
        '''
        i = iterator + 1
        percent = None
        if total is not None:
            percent = round((i / float(total)) * 100, 2)

        timestamp = datetime.datetime.now().isoformat()

        # create message
        if message is None:
            message = '{process}'
            if total is not None:
                message = '{process} {status} - {percent}% ({iterator} of {total})'
        message = message.format(
            process=process,
            status=status,
            message=message,
            iterator=i,
            total=total,
            percent=percent,
            data=data,
            timestamp=timestamp,
        )

        log = json.dumps(dict(
            status=status,
            process=process,
            message=message,
            iterator=iterator,
            total=total,
            percent=percent,
            data=data,
            timestamp=timestamp,
        ))
        return log

    def log(
        self,
        process,
        message=None,
        iterator=0,
        total=None,
        data=None,
        status='pending',
    ):
        # type: (str, Optional[str], int, Optional[int], Optional[Any], str) -> str
        '''
        Create a state log dictionary.

        Args:
            process (str): Process being logged.
            message (str, optional): Stateful message. Default: None.
            iterator (int): Current iteration in loop. Default: None.
            total (int, optional): Total iterations. Default: None.
            data (object, optional): Data related to state. Default: None.
            status (str, optional): Status of process. Default: 'pending'.
        '''
        self._connection.send(
            self.get_log_dict(
                process,
                message=message,
                iterator=iterator,
                total=total,
                data=data,
                status=status,
            )
        )


class DatabaseConnection:
    __instance = None

    @staticmethod
    def _request(database, command, args, kwargs):
        try:
            result = getattr(database, command)(*args, **kwargs)
            database.log(command, status='completed')
        except Exception as e:
            database.log(command, status='failed', data=svt.error_to_dict(e))
        return result

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(DatabaseConnection)
        return cls.__instance

    def __init__(self, database, *args, **kwargs):
        class DatabaseManager(BaseManager):
            pass

        attrs = list(filter(lambda x: not x.startswith('_'), dir(database)))
        DatabaseManager.register('Database', callable=database, exposed=attrs)
        self._manager = DatabaseManager()
        self._manager.start()

        self._pool = None
        self._response = None
        self._parent, self._child = Pipe(duplex=False)
        self._database = self._manager.Database(*args, **kwargs)
        self._database.set_logger(ConnectionLogger(self._child))
        self._database.log('initialize', status='completed')

    def request(self, command, *args, **kwargs):
        self._pool = Pool(1)
        self._response = self._pool.apply_async(
            func=DatabaseConnection._request,
            args=(self._database, command, args, kwargs),
        )

    def shutdown(self):
        self._parent.close()
        self._child.close()
        self._manager.shutdown()

    def refresh(self):
        self._state = json.loads(self._parent.recv())

    @property
    def response(self):
        # if self.pending:
        #     return None
        if self._pool is not None:
            self._pool.close()
            self._pool.join()
            self._pool.terminate()
            self._pool = None
        return self._response.get()

    @property
    def state(self):
        return self._state

    @property
    def pending(self):
        return self.state['status'] == 'pending'
