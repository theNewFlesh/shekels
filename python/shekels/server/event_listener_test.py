import unittest

from lunchbox.enforce import EnforceError
import dash

import shekels.server.event_listener as sev
# ------------------------------------------------------------------------------


def callback(value, store, app):
    store['foo'] = value
    return store


class EventListenerTests(unittest.TestCase):
    def test_event_listener(self):
        app = dash.Dash(name='test')
        store = {}
        event = sev.EventListener(app, store)
        event.listen('foo', callback)
        event.emit('foo', 'bar')

        self.assertEqual(store, {})
        self.assertEqual(event.store['foo'], 'bar')
        self.assertEqual(event.state[0], {})
        self.assertEqual(event.state[1], {'foo': 'bar'})

    def test_init(self):
        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store)
        self.assertEqual(event.store, store)
        self.assertIsNot(event.store, store)

    def test_init_error(self):
        # app
        with self.assertRaises(EnforceError):
            sev.EventListener(None, {})

        # store
        app = dash.Dash(name='test')
        with self.assertRaises(EnforceError):
            sev.EventListener(app, 'foo')

        # memory
        app = dash.Dash(name='test')
        expected = 'Memory must be greater or equal to 1. 0 < 1.'
        with self.assertRaisesRegexp(EnforceError, expected):
            sev.EventListener(app, {}, memory=0)

    def test_listen(self):
        def callback(value, store, app):
            store['foo'] = value
            return store

        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store)
        event.listen('foo', callback)
        self.assertIs(event.events['foo'], callback)

    def test_listen_error(self):
        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store)

        expected = 'Event name must be a string. 99 is not a string.'
        with self.assertRaisesRegexp(EnforceError, expected):
            event.listen(99, lambda v, s, a: s)

    def test_emit(self):
        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store)
        event.listen('foo', callback)

        # event
        event.emit('foo', 'taco')
        self.assertEqual(event.store['foo'], 'taco')
        self.assertIsNot(event.state[0], store)
        self.assertEqual(event.state[0], store)
        self.assertEqual(event.state[1], {'foo': 'taco'})
        self.assertEqual(len(event.state), 2)

        # non-event
        expected = len(event.state)
        event.emit('not-event', 'pizza')
        self.assertEqual(len(event.state), expected)

    def test_emit_error(self):
        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store)

        expected = 'Event name must be a string. 99 is not a string.'
        with self.assertRaisesRegexp(EnforceError, expected):
            event.emit(99, callback)

    def test_store(self):
        app = dash.Dash(name='test')
        store = {'foo': 'bar'}
        event = sev.EventListener(app, store).listen('foo', callback)
        result = event.store

        self.assertEqual(result, store)
        self.assertIsNot(result, store)

        event.emit('foo', 'bagel')
        result = event.store
        self.assertEqual(result, {'foo': 'bagel'})
