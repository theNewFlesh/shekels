import re
import unittest

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
