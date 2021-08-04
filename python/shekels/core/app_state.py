from typing import Any, Optional

from collections import deque
import datetime

from lunchbox.enforce import Enforce
# ------------------------------------------------------------------------------


class AppState:
    '''
    Class used for logging application state to disk.
    Message is formatted with the following instance variables:

        * step
        * message
        * iterator
        * total
        * percent
        * data
        * timestamp
    '''
    __instance = None

    def __init__(self, memory=100):
        # type: (int) -> None
        '''
        Constructs an AppState instance.

        Args:
            memory (int, optional): Maximum number of states to hold in queue.
                Default: 100.

        Raises:
            RuntimeError: If attempt to construct duplicate instance. 
            EnforceError: If memory is less than 1.
        '''
        if AppState.__instance is not None:
            msg = 'AppState is a singleton, and so cannot be constructed more '
            msg += 'than once.'
            raise RuntimeError(msg)
        else:
            AppState.__instance = self

        msg = 'Memory must be greater or equal to {b}. {a} < {b}.'
        Enforce(memory, '>=', 1, message=msg)
        # ----------------------------------------------------------------------

        state = dict(
            step='initial state',
            message=None,
            iterator=0,
            total=None,
            data=None,
        )
        self._queue = deque([state], memory)  # type: deque

    @property
    def state(self):
        # type: () -> dict
        '''
        dict: Newest item in queue.
        '''
        return self._queue[-1]

    def __repr__(self):
        # type: () -> str
        '''
        str: String representation of AppState.
        '''
        state = self.state
        return f'''AppState
    step: {state['step']}
    message: {state['message']}
    iterator: {state['iterator']}
    total: {state['total']}
    percent: {state['percent']}
    data: {state['data']}
    timestamp: {state['timestamp']}
'''[:-1]

    def log(self, step, message=None, iterator=0, total=None, data=None):
        # type: (str, Optional[str], int, Optional[int], Optional[Any]) -> None
        '''
        Logs state to queue.

        Args:
            step (str): Current step of process.
            message (str, optional): State message. Default: None.
            iterator (int): Current iteration in loop. Default: None.
            total (int, optional): Total iterations. Default: None.
            data (object, optional): Data related to state. Default: None.
        '''
        iterator += 1

        percent = None
        if total is not None:
            percent = round((iterator / float(total)) * 100, 2)

        timestamp = datetime.datetime.now().isoformat()

        # create message
        if message is None:
            message = '{step}'
            if total is not None:
                message = '{step} - {iterator} of {total}'
        message = message.format(
            step=step,
            message=message,
            iterator=iterator,
            total=total,
            percent=percent,
            data=data,
            timestamp=timestamp,
        )

        state = dict(
            step=step,
            message=message,
            iterator=iterator,
            total=total,
            percent=percent,
            data=data,
            timestamp=timestamp,
        )
        self._queue.append(state)


APP_STATE = AppState(memory=100)
