from typing import Any, Callable

from collections import deque
from copy import deepcopy
from lunchbox.enforce import Enforce
import dash
# ------------------------------------------------------------------------------


class EventListener:
    '''
    Listens for Dash app events and calls registered callbacks.
    '''
    def __init__(self, app, store, memory=10):
        # type: (dash.Dash, dict, int) -> None
        '''
        Constructs EventListener.

        Args:
            app (dash.Dash): Dash application instance.
            store (dict): Dash store.
            memory (int, optional): Number of state changes to remember.
                Default: 10.

        Raises:
            EnforceError: If app is not an instance of dash.Dash.
            EnforceError: If app is not an instance of dict.
            EnforceError: If memory is less than 1.
        '''
        Enforce(app, 'instance of', dash.Dash)
        Enforce(store, 'instance of', dict)
        msg = 'Memory must be greater or equal to {b}. {a} < {b}.'
        Enforce(memory, '>=', 1, message=msg)
        # ----------------------------------------------------------------------

        self._app = app  # type: dash.Dash
        self.events = {}  # type: dict
        self.state = deque([deepcopy(store)], memory)  # type: deque

    def listen(self, event, callback):
        # type: (str, Callable[[Any, dict, dash.Dash], dict]) -> EventListener
        '''
        Listen for given event and call given callback.

        Args:
            event (str): Event name.
            callback (function): Function of form (value, store, app) -> store.

        Raises:
            EnforceError: If event is not a string.

        Returns:
            EventListener: self.
        '''
        msg = 'Event name must be a string. {a} is not a string.'
        Enforce(event, 'instance of', str, message=msg)
        self.events[event] = callback
        return self

    def emit(self, event, value):
        # type: (str, object) -> EventListener
        '''
        Call a registered callback guven an event and value.

        Args:
            event (str): Event name.
            value (object): Value to be given to callback.

        Raises:
            EnforceError: If event is not a string.

        Returns:
            EventListener: self.
        '''
        msg = 'Event name must be a string. {a} is not a string.'
        Enforce(event, 'instance of', str, message=msg)
        if event in self.events:
            store = self.events[event](value, self.store, self._app)
            self.state.append(deepcopy(store))
        return self

    @property
    def store(self):
        # type () -> dict
        '''
        dict: Copy of last item in state.
        '''
        return deepcopy(self.state[-1])
