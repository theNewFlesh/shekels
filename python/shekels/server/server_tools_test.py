from pathlib import Path
from tempfile import TemporaryDirectory
import json
import re
import unittest

from dash.exceptions import PreventUpdate
import flask

import shekels.server.server_tools as svt
# ------------------------------------------------------------------------------


class ServerToolsTests(unittest.TestCase):
    def test_error_to_response(self):
        error = TypeError('foo')
        result = svt.error_to_response(error)
        self.assertEqual(result.mimetype, 'application/json')
        self.assertEqual(result.json['error'], 'TypeError')
        self.assertEqual(result.json['args'], ['foo'])
        self.assertEqual(result.json['message'], 'TypeError(\n    foo\n)')
        self.assertEqual(result.json['code'], 500)

    def test_error_to_response_dict(self):
        arg = {
            'bars': {
                f'bar-{i:02d}': {
                    f'bar-{i:02d}': 'banana'
                } for i in range(3)
            },
            'foos': [['pizza'] * 3] * 3,
        }
        error = TypeError(arg, arg, 'arg2')
        result = svt.error_to_response(error)

        expected = r'''
TypeError(
    {'bars': "{'bar-00': {'bar-00': 'banana'},\n"
         " 'bar-01': {'bar-01': 'banana'},\n"
         " 'bar-02': {'bar-02': 'banana'}}"}
    {'foos': "[['pizza', 'pizza', 'pizza'],\n"
         " ['pizza', 'pizza', 'pizza'],\n"
         " ['pizza', 'pizza', 'pizza']]"}
    {'bars': "{'bar-00': {'bar-00': 'banana'},\n"
         " 'bar-01': {'bar-01': 'banana'},\n"
         " 'bar-02': {'bar-02': 'banana'}}"}
    {'foos': "[['pizza', 'pizza', 'pizza'],\n"
         " ['pizza', 'pizza', 'pizza'],\n"
         " ['pizza', 'pizza', 'pizza']]"}
    arg2
)'''[1:]

        self.assertEqual(result.mimetype, 'application/json')
        self.assertEqual(result.json['error'], 'TypeError')
        self.assertEqual(result.json['args'][0], str(arg))
        self.assertEqual(result.json['args'][1], str(arg))
        self.assertEqual(result.json['args'][2], 'arg2')
        self.assertEqual(result.json['message'], expected)
        self.assertEqual(result.json['code'], 500)

    def test_render_template(self):
        with TemporaryDirectory() as root:
            template = Path(root, 'foo.j2').as_posix()
            lines = '''
                foo: {{ foo }}
                bar: {{ bar }}
            '''
            with open(template, 'w') as f:
                f.write(lines)
            params = dict(foo='taco', bar='pizza')
            result = svt.render_template('foo.j2', params, directory=root)
            expected = b'''
                foo: taco
                bar: pizza
            '''
            self.assertEqual(result, expected)

    def test_parse_json_file_content(self):
        content = '''data:application/json;base64,\
ewogICAgInJvb3RfZGlyZWN0b3J5IjogIi90bXAvYmFnZWxoYXQiLAogICAgImhpZGVib3VuZF9kaXJ\
lY3RvcnkiOiAiL3RtcC9zaWxseWNhdHMvaGlkZWJvdW5kIiwKICAgICJzcGVjaWZpY2F0aW9uX2ZpbG\
VzIjogWwogICAgICAgICIvcm9vdC9oaWRlYm91bmQvcHl0aG9uL2hpZGVib3VuZC9hd2Vzb21lX3NwZ\
WNpZmljYXRpb25zLnB5IgogICAgXSwKICAgICJpbmNsdWRlX3JlZ2V4IjogIiIsCiAgICAiZXhjbHVk\
ZV9yZWdleCI6ICJcXC5EU19TdG9yZXx5b3VyLW1vbSIsCiAgICAid3JpdGVfbW9kZSI6ICJjb3B5Igp\
9Cg=='''
        svt.parse_json_file_content(content)

        content_with_comment = '''data:application/json;base64,\
ewogICAgImZvbyI6ICJiYXIiCiAgICAvLyAicGl6emEiOiAidGFjbyIKfQo = '''
        svt.parse_json_file_content(content_with_comment)

        expected = 'File header is not JSON. Header: '
        expected += 'data:application/text;base64.'
        content = re.sub('json', 'text', content)
        with self.assertRaisesRegexp(ValueError, expected):
            svt.parse_json_file_content(content)

    def get_client(self):
        app = flask.Flask('test')

        @app.route('/api/foo', methods=['POST'])
        def foo():
            return flask.Response(
                response=json.dumps({'value': 'foo'}),
                mimetype='application/json'
            )

        @app.route('/api/bar', methods=['POST'])
        def bar():
            data = flask.request.get_json()
            data = json.loads(data)
            return flask.Response(
                response=json.dumps({'value': data}),
                mimetype='application/json'
            )

        @app.route('/api/error', methods=['POST'])
        def error():
            raise RuntimeError('some error')

        @app.errorhandler(RuntimeError)
        def handler(error):
            return svt.error_to_response(error)

        app.register_error_handler(500, handler)
        return app.test_client()

    def test_update_store(self):
        client = self.get_client()
        store = {}

        svt.update_store(client, store, '/api/foo')
        expected = {'/api/foo': {'value': 'foo'}}
        self.assertEqual(store, expected)

        svt.update_store(client, store, '/api/bar', data=['data'])
        expected.update({'/api/bar': {'value': ['data']}})
        self.assertEqual(store, expected)

        svt.update_store(client, store, '/api/error')
        expected = svt.error_to_response(RuntimeError('some error')).json
        result = store['/api/error']
        self.assertEqual(result['args'], expected['args'])
        self.assertEqual(result['error'], expected['error'])

    def test_store_key_is_valid(self):
        store = {}
        with self.assertRaises(PreventUpdate):
            svt.store_key_is_valid(store, 'foo')

        store['foo'] = {'error': ''}
        result = svt.store_key_is_valid(store, 'foo')
        self.assertFalse(result)

        store['bar'] = {'taco': ''}
        result = svt.store_key_is_valid(store, 'bar')
        self.assertTrue(result)

        store['pizza'] = 'error'
        result = svt.store_key_is_valid(store, 'pizza')
        self.assertTrue(result)

    def test_solve_component_state(self):
        # correct
        store = {'/api/initialize': {}, '/api/update': {}, '/api/search': {}}
        result = svt.solve_component_state(store)
        self.assertIsNone(result)

        states = {
            '/api/initialize': 'Please call init or update.',
            '/api/update': 'Please call update.',
            '/api/search': None,
        }
        keys = states.keys()
        for key, expected in states.items():
            # missing
            store = dict(zip(keys, [{}] * len(keys)))
            del store[key]
            result = None
            if expected is not None:
                result = svt \
                    .solve_component_state(store).children[-1].data[0]['value']
            self.assertEqual(result, expected)

            # error
            store[key] = {
                'error': 'FooBarError',
                'message': 'Not all foos are bars.',
                'code': '500',
                'traceback': 'foobar',
                'args': ['foo', 'bar'],
            }
            result = svt \
                .solve_component_state(store).children[-1].data[0]['value']
            self.assertEqual(result, 'FooBarError')
