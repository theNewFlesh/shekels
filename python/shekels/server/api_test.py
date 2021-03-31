from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from pandas import DataFrame
import flasgger as swg
import flask

from shekels.core.database import Database
import shekels.server.api as api
# ------------------------------------------------------------------------------


class ApiTests(unittest.TestCase):
    def get_data(self):
        data = [
            [
                '10/27/2020', 'Kiwi', 'UNITED FRUIT COMPANY', '99.99', 'debit',
                'Food & Drug', 'VisaCreditCard'
            ],
            [
                '10/28/2020', 'FooBar', 'BANK OF FOOBAR', '88.88', 'debit',
                'FancyBanking', 'AMEX'
            ],
            [
                '10/29/2020', 'BBsPizza', 'BOPPITY-BOOPEES PIZZA', '33.33',
                'debit', 'Food', 'AMEX'
            ],
            [
                '10/29/2020', 'Ignore', 'IGNORE', '77.77', 'debit',
                'IgnoreMe', 'Discover'
            ],
        ]
        data = DataFrame(data)
        data.columns = [
            'Date',
            'Description',
            'Original Description',
            'Amount',
            'Transaction Type',
            'Category',
            'Account Name',
        ]
        data['Labels'] = ''
        data['Notes'] = ''
        return data

    def get_partial_config(self):
        ow1 = {
            'action': 'overwrite',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'kiwi': 123,
            }
        }
        sub = {
            'action': 'substitute',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'foo': 'taco',
            }
        }
        ow2 = deepcopy(ow1)
        ow2['target_column'] = 'amount'
        ow2['mapping'] = {
            'taco': 0.0,
            'pizza': 11.11,
        }
        config = dict(
            conform=[ow1, sub, ow2]
        )
        return config

    def setUp(self):
        # create temp dir and write config to it
        self.config = self.get_partial_config()
        self.tempdir = TemporaryDirectory()
        self.root = self.tempdir.name

        self.data_path = Path(self.root, 'transactions.csv').as_posix()
        self.data = self.get_data()
        self.data.to_csv(self.data_path, index=False)
        self.config['data_path'] = self.data_path

        self.config_path = Path(self.root, 'config.json').as_posix()
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)

        # setup app
        app = flask.Flask(__name__)
        swg.Swagger(app)
        app.register_blueprint(api.API)
        app.api = api.API
        self.context = app.app_context()
        self.context.push()

        self.app = self.context.app
        self.app.api.database = None
        api.config = None

        self.client = self.app.test_client()
        self.app.config['TESTING'] = True

    def tearDown(self):
        self.context.pop()
        self.tempdir.cleanup()

    # DOCS----------------------------------------------------------------------
    def test_apidocs(self):
        result = self.client.get('/api').data.decode('utf-8')
        self.assertIn('/apidocs/', result)

        result = self.client.get('/apidocs/').data.decode('utf-8')
        self.assertIn('flasgger', result)

    # INITIALIZE----------------------------------------------------------------
    def test_get_api(self):
        result = api.get_api()
        self.assertIsInstance(result, flask.Blueprint)
        self.assertIsNone(result.database)
        self.assertIsNone(result.config)

    def test_initialize(self):
        config = json.dumps(self.config)
        result = self.client.post('/api/initialize', json=config)
        result = result.json['message']
        expected = 'Database initialized.'
        self.assertEqual(result, expected)
        self.assertIsInstance(self.app.api.database, Database)

    def test_initialize_no_config(self):
        result = self.client.post('/api/initialize').json['message']
        expected = 'Please supply a config dictionary.'
        self.assertRegex(result, expected)

    def test_initialize_bad_config_type(self):
        bad_config = '["a", "b"]'
        result = self.client.post('/api/initialize', json=bad_config)
        result = result.json['message']
        expected = 'Please supply a config dictionary.'
        self.assertRegex(result, expected)

    def test_initialize_bad_config(self):
        config = self.config
        config['data_path'] = '/foo/bar.csv'
        config = json.dumps(config)
        result = self.client.post('/api/initialize', json=config)
        result = result.json['message']
        expected = '/foo/bar.csv is not a valid CSV(.|\n)*file.'
        self.assertRegex(result, expected)

    # READ----------------------------------------------------------------------
    def test_read(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)

        # update
        self.client.post('/api/update')

        # call read
        result = self.client.post('/api/read').json['response']
        expected = self.app.api.database.read()
        self.assertEqual(result, expected)

    def test_read_no_init(self):
        result = self.client.post('/api/read').json['message']
        expected = 'Database not initialized. Please call initialize.'
        self.assertRegex(result, expected)

    def test_read_no_update(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)

        # call read
        result = self.client.post('/api/read').json['message']
        expected = 'Database not updated. Please call update.'
        self.assertRegex(result, expected)

    # UPDATE--------------------------------------------------------------------
    def test_update(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)

        # call update
        result = self.client.post('/api/update').json['message']
        expected = 'Database updated.'
        self.assertEqual(result, expected)

    def test_update_no_init(self):
        result = self.client.post('/api/update').json['message']
        expected = 'Database not initialized. Please call initialize.'
        self.assertRegex(result, expected)

    # SEARCH--------------------------------------------------------------------
    def test_search(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)
        self.client.post('/api/update')

        # call search
        query = 'SELECT * FROM data WHERE amount == 88.88'
        temp = {'query': query}
        temp = json.dumps(temp)
        result = self.client.post('/api/search', json=temp).json['response']
        expected = self.app.api.database.search(query)
        self.assertEqual(result, expected)

    def test_search_no_query(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)
        self.client.post('/api/update')

        # call search
        temp = json.dumps({'foo': 'bar'})
        result = self.client.post('/api/search', json=temp).json['message']
        expected = 'Please supply valid search params in the form '
        expected += r'\{"query": SQL query\}\.'
        self.assertRegex(result, expected)

    def test_search_bad_json(self):
        query = 'some bad json'
        result = self.client.post('/api/search', json=query).json['error']
        expected = 'JSONDecodeError'
        self.assertRegex(result, expected)

    def test_search_bad_query_params(self):
        query = {'foo': 'bar'}
        query = json.dumps(query)
        result = self.client.post('/api/search', json=query).json['message']
        expected = 'Please supply valid search params in the form '
        expected += r'\{"query": SQL query\}\.'
        self.assertRegex(result, expected)

    def test_search_bad_query_sql(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)
        self.client.post('/api/update')

        # call search
        query = {'query': 'SELECT * FROM data WHERE foobar == foo'}
        query = json.dumps(query)
        result = self.client.post('/api/search', json=query)
        result = result.json['error']
        expected = 'PandaSQLException'
        self.assertEqual(result, expected)

    def test_search_no_init(self):
        query = {'query': 'SELECT * FROM data WHERE amount == 88.88'}
        query = json.dumps(query)
        result = self.client.post('/api/search', json=query).json['message']
        expected = 'Database not initialized. Please call initialize.'
        self.assertRegex(result, expected)

    def test_search_no_update(self):
        # init database
        config = json.dumps(self.config)
        self.client.post('/api/initialize', json=config)

        # call search
        query = {'query': 'SELECT * FROM data WHERE amount == 88.88'}
        query = json.dumps(query)
        result = self.client.post('/api/search', json=query).json['message']
        expected = 'Database not updated. Please call update.'
        self.assertRegex(result, expected)
