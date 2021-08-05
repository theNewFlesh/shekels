import time
import logging

from shekels.server.connection import DatabaseConnection
# ------------------------------------------------------------------------------


class Database:
    def __init__(self, *args, **kwargs):
        self._data = []
        self._logger = logging.getLogger(__name__)

    def set_logger(self, logger):
        self._logger = logger

    def log(self, *args, **kwargs):
        self._logger.log(*args, **kwargs)

    def update(self, fail=False):
        data = []
        total = 10
        for i in range(total):
            time.sleep(0.01)
            data.append(i)
            self._logger.log('update', iterator=i, total=total)
            if fail and i == 5:
                raise ValueError('Deliberate failure')
        self._data = data
        return self


DBC = DatabaseConnection(Database, fail=True)


def endpoint(event='interval'):
    if event == 'click':
        DBC.request('update')

    DBC.refresh()
    if DBC.pending:
        return DBC.state

    return DBC.response._data


endpoint('click')
print(DBC.state)
while True:
    x = endpoint()
    print(x)
    if type(x) is not dict:
        break
DBC.shutdown()
