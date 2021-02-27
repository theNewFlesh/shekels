from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from schematics.exceptions import DataError, ValidationError
import pytest
import shekels.core.config as cfg
# ------------------------------------------------------------------------------


class ConfigValidatorTests(unittest.TestCase):
    def test_is_csv(self):
        csv_path = Path('/foo', 'bar.csv')
        expected = '/foo/bar.csv is not a valid CSV file.'
        with self.assertRaisesRegexp(ValidationError, expected):
            cfg.is_csv(csv_path)

        with TemporaryDirectory() as root:
            expected = 'bar.txt is not a valid CSV file.'
            csv_path = Path(root, 'bar.txt')
            with open(csv_path, 'w') as f:
                f.write('')
            with self.assertRaisesRegexp(ValidationError, expected):
                cfg.is_csv(csv_path)

            csv_path = Path(root, 'bar.csv')
            with open(csv_path, 'w') as f:
                f.write('')
            cfg.is_csv(csv_path)

    def test_is_color_scheme(self):
        cs = deepcopy(cfg.COLOR_SCHEME)
        cfg.is_color_scheme(cs)

        cs['foo'] = 'bar'
        expected = r"Invalid color scheme keys: \['foo'\]\."
        with self.assertRaisesRegexp(ValidationError, expected):
            cfg.is_color_scheme(cs)

    def test_is_comparator(self):
        comps = ['==', '!=', '>', '>=', '<', '=<', '~', '!~']
        for comp in comps:
            cfg.is_comparator(comp)

        expected = f'foo is not a legal comparator. Legal comparators: {comps}.'
        with pytest.raises(ValidationError) as e:
            cfg.is_comparator('foo')
        self.assertIn(expected, str(e.value))

    def test_is_metric(self):
        vals = ['max', 'mean', 'min', 'std', 'sum', 'var', 'count']
        for val in vals:
            cfg.is_metric(val)

        expected = f'foo is not a legal metric. Legal metrics: {vals}.'
        with pytest.raises(ValidationError) as e:
            cfg.is_metric('foo')
        self.assertIn(expected, str(e.value))

    def test_is_plot_kind(self):
        vals = [
            'area', 'bar', 'barh', 'line' 'lines', 'ratio', 'scatter', 'spread'
        ]
        for val in vals:
            cfg.is_plot_kind(val)

        expected = f'foo is not a legal plot kind. Legal kinds: {vals}.'
        with pytest.raises(ValidationError) as e:
            cfg.is_plot_kind('foo')
        self.assertIn(expected, str(e.value))

    def test_is_bar_mode(self):
        vals = ['stack', 'group', 'overlay']
        for val in vals:
            cfg.is_bar_mode(val)

        expected = f'foo is not a legal bar mode. Legal bar modes: {vals}.'
        with pytest.raises(ValidationError) as e:
            cfg.is_bar_mode('foo')
        self.assertIn(expected, str(e.value))

    def test_is_percentage(self):
        cfg.is_percentage(0)
        cfg.is_percentage(51.3)
        cfg.is_percentage(100)

        expected = '-4 is not a legal percentage. -4 is not between 0 and 100.'
        with self.assertRaisesRegexp(ValidationError, expected):
            cfg.is_percentage(-4)

        expected = '200 is not a legal percentage. 200 is not between 0 and 100.'
        with self.assertRaisesRegexp(ValidationError, expected):
            cfg.is_percentage(200)


class ConfigSchematicTests(unittest.TestCase):
    def get_actions(self):
        overwrite = {
            'action': 'overwrite',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'pizza': True
            }
        }
        substitute = {
            'action': 'substitute',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'pizza': 'taco'
            }
        }
        return overwrite, substitute

    def test_filter_action(self):
        data = dict(
            column='foo',
            comparator='~',
            value='bar',
        )
        cfg.FilterAction(data).validate()

        # column
        bad = deepcopy(data)
        del bad['column']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FilterAction(bad).validate()

        # comparator
        bad = deepcopy(data)
        del bad['comparator']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FilterAction(bad).validate()

        bad['comparator'] = 'foo'
        expected = 'foo is not a legal comparator.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FilterAction(bad).validate()

        # value
        bad = deepcopy(data)
        del bad['value']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FilterAction(bad).validate()

    def test_group_action(self):
        data = dict(
            columns=['foo', 'bar'],
            metric='mean',
            datetime_column='baz',
        )
        cfg.GroupAction(data).validate()

        # columns
        bad = deepcopy(data)
        del bad['columns']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.GroupAction(bad).validate()

        # metric
        bad = deepcopy(data)
        del bad['metric']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.GroupAction(bad).validate()

        bad['metric'] = 'foo'
        expected = 'foo is not a legal metric.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.GroupAction(bad).validate()

        # datetime_column
        bad = deepcopy(data)
        del bad['datetime_column']
        result = cfg.GroupAction(bad).to_primitive()
        self.assertEqual(result['datetime_column'], 'date')

    def test_pivot_action(self):
        data = dict(
            columns=['foo', 'bar'],
            values=['taco', 'pizza'],
            index='kiwi',
        )
        cfg.PivotAction(data).validate()

        # columns
        bad = deepcopy(data)
        del bad['columns']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.PivotAction(bad).validate()

        # values
        bad = deepcopy(data)
        del bad['values']
        result = cfg.PivotAction(bad).to_primitive()
        self.assertEqual(result['values'], [])

        # index
        bad = deepcopy(data)
        del bad['index']
        result = cfg.PivotAction(bad).to_primitive()
        self.assertIsNone(result['index'])

    def test_conform_action(self):
        ow, sub = self.get_actions()
        cfg.ConformAction(ow).validate()
        cfg.ConformAction(sub).validate()

        # action
        bad = deepcopy(ow)
        bad['action'] = 'foo'
        expected = 'action.*Value must be one of.*overwrite.*substitute'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.ConformAction(bad).validate()

        # source_column
        bad = deepcopy(ow)
        del bad['source_column']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.ConformAction(bad).validate()

        # target_column
        bad = deepcopy(ow)
        del bad['target_column']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.ConformAction(bad).validate()

        # mapping
        bad = deepcopy(ow)
        del bad['mapping']
        expected = 'This field is required.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.ConformAction(bad).validate()

        # mapping bad value
        bad = deepcopy(ow)
        bad['mapping'] = {'a': ['b', 'c']}
        with self.assertRaises(DataError):
            cfg.ConformAction(bad).validate()

        # mapping substitute action
        bad = deepcopy(sub)
        bad['mapping'] = {'foo': 123}
        expected = "Couldn't interpret.*123.*as string"
        with self.assertRaisesRegexp(DataError, expected):
            cfg.ConformAction(bad).validate()

    def test_figure_item(self):
        result = cfg.FigureItem({}).to_primitive()
        self.assertEqual(result['kind'], 'bar')
        self.assertEqual(
            result['color_scheme'],
            {'bg': '#242424', 'grey1': '#181818'}
        )
        self.assertIsNone(result['title'])
        self.assertIsNone(result['x_title'])
        self.assertIsNone(result['y_title'])
        self.assertEqual(result['bins'], 50)
        self.assertEqual(result['bar_mode'], 'stack')

        # kind
        bad = dict(kind='foo')
        expected = 'foo is not a legal plot kind.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FigureItem(bad).validate()

        # bar mode
        bad = dict(bar_mode='foo')
        expected = 'foo is not a legal bar mode.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.FigureItem(bad).validate()

    def test_plot_item(self):
        result = cfg.PlotItem({}).to_primitive()
        self.assertEqual(result['filters'], [])
        self.assertIsNone(result['group'])
        self.assertIsNone(result['pivot'])
        expected = cfg.FigureItem({}).to_primitive()
        self.assertEqual(result['figure'], expected)
        self.assertEqual(result['min_width'], 25)

        bad = dict(figure=dict(kind='foo'))
        expected = 'foo is not a legal plot kind.'
        with self.assertRaisesRegexp(DataError, expected):
            cfg.PlotItem(bad).validate()

    def get_config(self, root):
        data_path = Path(root, 'transactions.csv').as_posix()
        ow, sub = self.get_actions()
        config = dict(
            data_path=data_path,
            columns=['foo', 'bar'],
            conform=[ow, sub],
            font_family='Tahoma',
            plots=[
                dict(
                    filters=[
                        dict(
                            column='foo',
                            comparator='~',
                            value='bar'
                        ),
                        dict(
                            column='amount',
                            comparator='>',
                            value=9000
                        )
                    ],
                    group=dict(
                        columns=['foo', 'bar'],
                        metric='mean',
                        datetime_column='baz',
                    ),
                    pivot=dict(
                        columns=['foo', 'bar'],
                        values=['taco', 'pizza'],
                        index='kiwi',
                    ),
                    figure=dict(
                        kind='area',
                        title='FooBar',
                        x_title='foos',
                        y_title='bars',
                        color_scheme=dict(
                            red2='#FF0000'
                        )
                    ),
                    min_width=67
                )
            ]
        )
        return config

    def test_config(self):
        ow, sub = self.get_actions()
        with TemporaryDirectory() as root:
            config = self.get_config(root)
            data_path = config['data_path']
            with open(data_path, 'w') as f:
                f.write('')
            cfg.Config(config).validate()

            # default values
            result = {
                'data_path': data_path,
            }
            result = cfg.Config(result)
            self.assertEqual(result.columns, [])
            self.assertEqual(result.conform, [])
            self.assertEqual(result.default_query, 'select * from data')

            # data_path bad ext
            bad = deepcopy(config)
            bad['data_path'] = re.sub('csv', 'tsv', config['data_path'])
            expected = '.* is not a valid CSV file.'
            with self.assertRaisesRegexp(DataError, expected):
                cfg.Config(bad).validate()

            # data_path not exist
            bad['data_path'] = Path(root, 'foo.csv').as_posix()
            with self.assertRaisesRegexp(DataError, expected):
                cfg.Config(bad).validate()

            # conform
            bad = deepcopy(ow)
            bad['action'] = 'foo'
            config['conform'] = [ow, sub, bad]
            expected = 'action.*Value must be one of.*overwrite.*substitute'
            with self.assertRaisesRegexp(DataError, expected):
                cfg.Config(config).validate()

            # color scheme
            bad = deepcopy(config)
            cs = deepcopy(cfg.COLOR_SCHEME)
            cs['foo'] = 'bar'
            bad['color_scheme'] = cs
            expected = 'Invalid color scheme keys:.*foo'
            with self.assertRaisesRegexp(DataError, expected):
                cfg.Config(bad).validate()
