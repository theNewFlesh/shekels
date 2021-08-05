from typing import Any, Optional

from multiprocessing import Pipe, Pool
from multiprocessing.managers import BaseManager
from pprint import pformat
import datetime
import json
import time
import traceback
# ------------------------------------------------------------------------------


def error_to_dict(error):
    args = []  # type: Any
    for arg in error.args:
        if hasattr(arg, 'items'):
            for key, val in arg.items():
                args.append(pformat({key: pformat(val)}))
        else:
            args.append(str(arg))
    args = ['    ' + x for x in args]
    args = '\n'.join(args)
    klass = error.__class__.__name__
    msg = f'{klass}(\n{args}\n)'
    return dict(
        error=error.__class__.__name__,
        args=list(map(str, error.args)),
        message=msg,
        code=500,
        traceback=traceback.format_exc()
    )


class Database:
    def __init__(self, logger, *args, **kwargs):
        self._logger = logger
        self.data = []

    def update(self, fail=False):
        data = []
        total = 10
        for i in range(total):
            time.sleep(0.1)
            data.append(i)
            self._logger.log('update', iterator=i, total=total)
            if fail and i == 5:
                raise ValueError('Deliberate failure')
        self.data = data
        return self


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
    def _request(logger, database, command, args, kwargs):
        try:
            result = getattr(database, command)(*args, **kwargs)
            logger.log(command, status='completed')
        except Exception as e:
            logger.log(command, status='failed', data=error_to_dict(e))
        return result

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(DatabaseConnection)
        return cls.__instance

    def __init__(self, *args, **kwargs):
        class DatabaseManager(BaseManager):
            pass

        attrs = list(filter(lambda x: not x.startswith('_'), dir(Database)))
        DatabaseManager.register('Database', callable=Database, exposed=attrs)
        self._manager = DatabaseManager()
        self._manager.start()

        self._pool = None
        self._response = None
        self._parent, self._child = Pipe(duplex=False)
        self._logger = ConnectionLogger(self._child)
        self._database = self._manager.Database(self._logger, *args, **kwargs)
        self._logger.log('initialize', status='completed')

    def request(self, command, *args, **kwargs):
        self._pool = Pool(1)
        self._response = self._pool.apply_async(
            func=DatabaseConnection._request,
            args=(self._logger, self._database, command, args, kwargs),
        )

    def shutdown(self):
        self._parent.close()
        self._child.close()
        self._manager.shutdown()

    def refresh(self):
        self._state = json.loads(self._parent.recv())

    @property
    def response(self):
        if self.pending:
            return None
        if self._pool is not None:
            self._pool.close()
            self._pool.join()
            self._pool.terminate()
            self._pool = None
            return self._response.get()
        return None

    @property
    def state(self):
        return self._state

    @property
    def pending(self):
        return self.state['status'] == 'pending'


DBC = DatabaseConnection(Database, fail=True)


def endpoint(event='interval'):
    if event == 'click':
        DBC.request('update')

    DBC.refresh()
    if DBC.pending:
        return DBC.state

    r = DBC.response
    if r is not None:
        return r.data
    return None


print(endpoint())
endpoint('click')
for i in range(10):
    print(endpoint())
print(endpoint())

DBC.shutdown()
