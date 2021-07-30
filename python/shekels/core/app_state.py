from typing import Any, Dict, Optional

import datetime
import json
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

    Attributes:
        log_path (str): Path to log file.
        step (str): Current step of process.
        message (str): State message.
        iterator (int): Current iteration in loop.
        total (int): Total iterations.
        percent (float): Percent complete.
        data (object): Data related to state.
        timestamp (str): Time of construction.
    '''
    log_path = '/tmp/app_state.json'

    def __init__(
        self, step, message=None, iterator=0, total=None, data=None
    ):
        # type: (str, Optional[str], int, Optional[int], Optional[Any]) -> None
        '''
        Constructs an AppState instance.

        Args:
            step (str): Current step of process.
            message (str, optional): State message. Default: None.
            iterator (int): Current iteration in loop. Default: 0.
            total (int, optional): Total iterations. Default: None.
            data (object, optional): Data related to state. Default: None.
        '''
        iterator += 1

        self.step = step
        self.iterator = iterator
        self.total = total
        self.data = data
        self.timestamp = datetime.datetime.now().isoformat()

        # create message
        if message is None:
            message = '{step}'
            if iterator is not None and total is not None:
                message = '{step} - {iterator} of {total}'
        message = str(message).format(
            step=step,
            message=message,
            iterator=iterator,
            total=total,
            percent=self.percent,
            data=data,
            timestamp=self.timestamp,
        )
        self.message = message

    @property
    def percent(self):
        # type: () -> Optional[float]
        '''
        float: Iteration / total.
        '''
        if self.iterator is not None and self.total is not None:
            return round((self.iterator / float(self.total)) * 100, 2)
        return None

    def __repr__(self):
        # type: () -> str
        '''
        str: String representation of AppState.
        '''
        return f'''AppState
    step: {self.step}
    message: {self.message}
    iterator: {self.iterator}
    total: {self.total}
    percent: {self.percent}
    data: {self.data}
    timestamp: {self.timestamp}
'''[:-1]

    def to_dict(self):
        # type: () -> Dict[str, Any]
        '''
        Converts instance to dictionary.

        Returns:
            dict: App state dictionary.
        '''
        return dict(
            step=self.step,
            message=self.message,
            iterator=self.iterator,
            total=self.total,
            percent=self.percent,
            data=self.data,
            timestamp=self.timestamp,
        )

    @staticmethod
    def log(step, message=None, iterator=0, total=None, data=None):
        # type: (str, Optional[str], int, Optional[int], Optional[Any]) -> None
        '''
        Logs state to file.

        Args:
            step (str): Current step of process.
            message (str, optional): State message. Default: None.
            iterator (int): Current iteration in loop. Default: None.
            total (int, optional): Total iterations. Default: None.
            data (object, optional): Data related to state. Default: None.
        '''
        state = AppState(
            step,
            iterator=iterator,
            total=total,
            message=message,
            data=data,
        ).to_dict()
        with open(AppState.log_path, 'w') as f:
            json.dump(state, f, indent=4)
