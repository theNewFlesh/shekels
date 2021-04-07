import unittest

from lunchbox.enforce import EnforceError
import flask

import shekels.server.components as svc
# ------------------------------------------------------------------------------


class ComponentsTests(unittest.TestCase):
    def test_get_dash_app(self):
        result = svc.get_dash_app(flask.Flask('foo'))._layout
        self.assertEqual(result.children[0].id, 'store')
        self.assertEqual(result.children[1].id, 'tabs')
        self.assertEqual(result.children[2].id, 'content')

    def test_get_button(self):
        expected = '10 is not a string.'
        with self.assertRaisesRegexp(TypeError, expected):
            svc.get_button(10)

        result = svc.get_button('foo')
        self.assertEqual(result.id, 'foo-button')
        self.assertEqual(result.children[0], 'foo')

    def test_get_searchbar(self):
        searchbar = svc.get_searchbar('foo')

        query = searchbar.children[0].children[0]
        self.assertEqual(query.value, 'foo')

        searchbar = svc.get_searchbar()
        self.assertEqual(searchbar.id, 'searchbar')

        query = searchbar.children[0].children[0]
        self.assertEqual(query.id, 'query')
        self.assertEqual(query.value, 'select * from data')
        self.assertEqual(query.placeholder, 'SQL query that uses "FROM data"')

        button = searchbar.children[0].children[2]
        self.assertEqual(button.id, 'search-button')
        self.assertEqual(button.children[0], 'search')

        button = searchbar.children[0].children[4]
        self.assertEqual(button.id, 'init-button')
        self.assertEqual(button.children[0], 'init')

        button = searchbar.children[0].children[6]
        self.assertEqual(button.id, 'update-button')
        self.assertEqual(button.children[0], 'update')

    def test_get_configbar(self):
        configbar = svc.get_configbar({'foo': 'bar'})
        self.assertEqual(configbar.id, 'configbar')

        row = configbar.children[0].children

        self.assertEqual(row[0].id, 'config-query')
        self.assertEqual(row[2].id, 'config-search-button')
        self.assertEqual(row[4].id, 'init-button')
        self.assertEqual(row[6].id, 'upload')

    def test_get_plots_tab(self):
        tab = svc.get_plots_tab()
        self.assertEqual(tab[-2].id, 'searchbar')
        self.assertEqual(tab[-1].id, 'lower-content')

    def test_get_data_tab(self):
        tab = svc.get_data_tab()
        self.assertEqual(tab[-2].id, 'searchbar')
        self.assertEqual(tab[-1].id, 'lower-content')

    def test_get_config_tab(self):
        tab = svc.get_config_tab({'foo': 'bar'})
        self.assertEqual(tab[-1].id, 'lower-content')
        self.assertEqual(tab[-1].children[0].id, 'config-content')

    def test_get_datatable(self):
        data = [
            {'foo': 'pizza', 'bar': 'taco'},
            {'foo': 'kiwi', 'bar': 'potato'},
        ]
        result = svc.get_datatable(data)
        self.assertEqual(result.id, 'datatable')
        expected = [
            {'name': 'foo', 'id': 'foo'},
            {'name': 'bar', 'id': 'bar'}
        ]
        self.assertEqual(result.columns, expected)

        result = svc.get_datatable([])
        self.assertEqual(result.columns, [])

    def test_get_plots_errors(self):
        # data
        expected = 'Data must be a list of dictionaries. Given value: foo.'
        with self.assertRaisesRegexp(EnforceError, expected):
            svc.get_plots('foo', [])

        expected = 'Data must be a list of dictionaries. Given value: foo.'
        with self.assertRaisesRegexp(EnforceError, expected):
            svc.get_plots(['foo'], [])

        # plots
        expected = 'Plots must be a list of dictionaries. Given value: foo.'
        with self.assertRaisesRegexp(EnforceError, expected):
            svc.get_plots([], 'foo')

        expected = 'Plots must be a list of dictionaries. Given value: foo.'
        with self.assertRaisesRegexp(EnforceError, expected):
            svc.get_plots([], ['foo'])

    def test_get_plots(self):
        data = [
            {'date': '2020-04-05T12:00:00', 'name': 'foo', 'amount': 1},
            {'date': '2020-04-05T12:00:01', 'name': 'foo', 'amount': 2},
            {'date': '2020-04-05T12:00:02', 'name': 'bar', 'amount': 3},
        ]
        plot = {
            "pivot": {
                "columns": ["name"],
                "values": ["amount"],
                "index": "date",
            },
            "figure": {
                "kind": "bar",
                "title": "Expenditures",
                "x_title": "names",
                "y_title": "amount",
            }
        }
        result = svc.get_plots(data, [plot, plot])
        self.assertEqual(len(result), 2)

    def test_get_plots_no_data(self):
        data = [
            {'date': '2020-04-05T12:00:00', 'name': 'foo', 'amount': 1},
            {'date': '2020-04-05T12:00:01', 'name': 'foo', 'amount': 2},
            {'date': '2020-04-05T12:00:02', 'name': 'bar', 'amount': 3},
        ]
        good = {
            "pivot": {
                "columns": ["name"],
                "values": ["amount"],
                "index": "date",
            },
            "figure": {
                "kind": "bar",
                "title": "Expenditures",
                "x_title": "names",
                "y_title": "amount",
            }
        }
        bad = {
            "pivot": {
                "columns": ["not_a_column"],
                "values": ["amount"],
                "index": "date",
            },
            "figure": {"kind": "bar"}
        }
        # DataError
        result = svc.get_plots(data, [good, bad])[1].children.children
        self.assertEqual(result, 'no data found')

        # EnforceError
        result = svc.get_plots([], [good, good])[1].children.children
        self.assertEqual(result, 'no data found')

    def test_get_dummy_elements(self):
        result = svc.get_dummy_elements()
        result = set([x.id for x in result])
        expected = {
            'config-query',
            'query',
            'config-search-button',
            'search-button',
            'init-button',
            'update-button',
            'upload',
            'write-button',
        }
        self.assertEqual(result, expected)

    def test_get_key_value_table(self):
        data = {
            'foo': [{'bar': 'baz'}, {'a': 'b'}],
            'first': 'pizza',
            'second': 'taco',
        }
        order = ['first', 'second']
        result = svc.get_key_value_table(
            data, id_='id', header='header', editable=True, key_order=order
        )

        # id
        self.assertEqual(result.id, 'id')

        # header
        self.assertEqual(result.children[0].children, 'header')

        df = result.children[-1]

        # editable
        self.assertTrue(df.editable)

        # key_order
        expected = ['first', 'second', 'foo/<list_0>/bar', 'foo/<list_1>/a']
        keys = [x['key'] for x in df.data]
        self.assertEqual(keys, expected)

        # values
        vals = [x['value'] for x in df.data]
        expected = ['pizza', 'taco', 'baz', 'b']
        self.assertEqual(vals, expected)

    def test_get_key_value_table_error(self):
        data = {
            'foo': 'bar',
            'first': 'pizza',
            'second': 'taco',
        }
        order = ['first', 'second', 'not_a_key']
        expected = r"Invalid key order. Keys not found in data: \['not_a_key'\]\."
        with self.assertRaisesRegexp(KeyError, expected):
            svc.get_key_value_table(data, key_order=order)
