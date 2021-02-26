from copy import deepcopy
from datetime import datetime
import re
import unittest

from lunchbox.enforce import EnforceError
from pandas import DataFrame, Series
from schematics.exceptions import DataError

import shekels.core.data_tools as sdt
import shekels.enforce.enforce_tools as eft
# ------------------------------------------------------------------------------


class DataToolsTests(unittest.TestCase):
    # CONFORM-------------------------------------------------------------------
    def get_conform_actions(self):
        overwrite = {
            'action': 'overwrite',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'kiwi': 123,
            }
        }
        substitute = {
            'action': 'substitute',
            'source_column': 'description',
            'target_column': 'description',
            'mapping': {
                'foo': 'taco',
            }
        }
        ow = deepcopy(overwrite)
        ow['target_column'] = 'amount'
        ow['mapping'] = {
            'taco': 0.0,
            'pizza': 11.11,
        }
        return [overwrite, substitute, ow]

    def get_partial_config(self):
        ow1, sub, ow2 = self.get_conform_actions()
        return dict(conform=[ow1, sub, ow2])

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

    def test_conform_columns(self):
        data = self.get_data()
        result = sdt.conform(data).columns.tolist()
        expected = [
            'date',
            'description',
            'original_description',
            'amount',
            'type',
            'category',
            'account',
            'labels',
            'notes',
        ]
        self.assertEqual(result, expected)

        expected = expected[:-2]
        result = sdt.conform(data, columns=expected).columns.tolist()
        self.assertEqual(result, expected)

    def test_conform_category(self):
        data = self.get_data()
        result = sdt.conform(data).category
        self.assertEqual(result[0], 'food_and_drug')
        self.assertEqual(result[1], 'fancy_banking')

    def test_conform_account(self):
        data = self.get_data()
        result = sdt.conform(data).account
        self.assertEqual(result[0], 'visa_credit_card')
        self.assertEqual(result[1], 'amex')

    def test_conform_actions(self):
        data = self.get_data()
        actions = self.get_conform_actions()
        result = sdt.conform(data, actions=actions)
        self.assertEqual(result.loc[0, 'description'], '123')
        self.assertEqual(result.loc[1, 'description'], 'tacoBar')
        self.assertEqual(result.loc[1, 'amount'], 0.0)
        self.assertEqual(result.loc[2, 'amount'], 11.11)

    def test_conform_actions_target(self):
        data = self.get_data()
        actions = [{
            'action': 'overwrite',
            'source_column': 'description',
            'target_column': 'new_col',
            'mapping': {
                'kiwi': 123,
            }
        }]
        result = sdt.conform(data, actions=actions)
        self.assertEqual(result.loc[0, 'description'], 'Kiwi')
        self.assertEqual(result.loc[0, 'new_col'], 123)

    def test_conform_actions_errors(self):
        data = self.get_data()
        ow, sub, _ = self.get_conform_actions()
        bad = deepcopy(sub)
        bad['mapping'] = {'a': ['b']}
        with self.assertRaises(DataError):
            sdt.conform(data, actions=[ow, sub, bad])

        # bad source column
        cols = [
            'date', 'description', 'original_description', 'amount', 'type',
            'category', 'account', 'labels', 'notes'
        ]
        cols = "'" + "', '".join(cols) + "'"
        cols = cols.lower()
        expected = 'Source column bagel not found in columns. '
        expected += f"Legal columns include: \\[{cols}\\]\\."
        bad = deepcopy(sub)
        bad['source_column'] = 'bagel'
        with self.assertRaisesRegexp(ValueError, expected):
            sdt.conform(data, actions=[ow, sub, bad])

    # FILTER-DATA---------------------------------------------------------------
    def get_data_2(self):
        data = DataFrame()
        data['id'] = [1, 2, 3, 4, 5]
        data['age'] = [21, 22, 23, 27, 30]
        data['name'] = ['tom', 'dick', 'jane', 'harry', 'bill']
        data['group'] = [0, 0, 1, 1, 1]
        data['date'] = [
            datetime(2021, 1, 1, 1, 1, 1, 1),
            datetime(2021, 4, 1, 1, 1, 1, 1),      # 1/4y
            datetime(2021, 5, 30, 1, 1, 1, 1),     # 1/4y
            datetime(2021, 5, 30, 23, 1, 1, 1),    # 1/4y, 1/2m, 1/2h, 1/4h
            datetime(2021, 5, 13, 23, 59, 1, 1),   # 1/4y, 1/2m, 1/2h, 1/4h
        ]
        return data

    def test_filter_data_errors(self):
        data = self.get_data_2()

        # data
        with self.assertRaises(EnforceError):
            sdt.filter_data('id', 'age', '==', 24)

        # column
        expected = 'Column must be a str. 123 is not str.'
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.filter_data(data, 123, '==', 24)

        expected = 'Given columns not found in data. '
        expected += r"\['pizza'\] not in "
        expected += r"\['id', 'age', 'name', 'group', 'date'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.filter_data(data, 'pizza', '==', 24)

        # comparator
        expected = 'Illegal comparator. '
        expected += r"= not in \[==, !=, >, >=, <, <=, ~, !~\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.filter_data(data, 'age', '=', 24)

        # regex comparator
        expected = 'Value must be string if comparator is ~ or !~. 24 is not str.'
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.filter_data(data, 'age', '~', 24)

        expected = 'Value must be string if comparator is ~ or !~. 24 is not str.'
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.filter_data(data, 'age', '!~', 24)

    def test_filter_data_eq(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '==', 23).index.tolist()
        mask = data['age'].apply(lambda x: x == 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_neq(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '!=', 23).index.tolist()
        mask = data['age'].apply(lambda x: x != 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_gt(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '>', 23).index.tolist()
        mask = data['age'].apply(lambda x: x > 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_gte(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '>=', 23).index.tolist()
        mask = data['age'].apply(lambda x: x >= 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_lt(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '<', 23).index.tolist()
        mask = data['age'].apply(lambda x: x < 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_lte(self):
        data = self.get_data_2()
        result = sdt.filter_data(data, 'age', '<=', 23).index.tolist()
        mask = data['age'].apply(lambda x: x <= 23)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    def test_filter_data_re(self):
        data = self.get_data_2()

        # ~
        result = sdt.filter_data(data, 'name', '~', 'tom|dick').index.tolist()
        mask = data['name'] \
            .apply(lambda x: re.search('tom|dick', x, flags=re.I)).astype(bool)
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

        # !~
        result = sdt.filter_data(data, 'name', '!~', 'tom|dick').index.tolist()
        mask = data['name'] \
            .apply(lambda x: not bool(re.search('tom|dick', x, flags=re.I)))
        expected = data[mask].index.tolist()
        self.assertEqual(result, expected)

    # GROUP-DATA----------------------------------------------------------------
    def test_group_data_errors(self):
        data = self.get_data_2()

        # data
        with self.assertRaises(EnforceError):
            sdt.group_data('id', 'age', 'mean')

        # columns
        expected = 'Given columns not found in data. '
        expected += r"\['pizza'\] not in "
        expected += r"\['id', 'age', 'name', 'group', 'date'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.group_data(data, 'pizza', 'mean')

        # metric
        expected = 'foo is not a legal metric. Legal metrics: '
        expected += r"\['count', 'max', 'mean', 'min', 'std', 'sum', 'var'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.group_data(data, ['age'], 'foo')

        # datetime_column
        keys = [
            'year', 'quarter', 'month', 'two_week', 'week', 'day', 'hour',
            'half_hour', 'quarter_hour', 'minute', 'second', 'microsecond',
        ]

        data['date'] = data.date.apply(str)
        expected = 'Datetime column of type .*, it must be of type .*datetime64'
        for key in keys:
            with self.assertRaisesRegexp(EnforceError, expected):
                sdt.group_data(data, 'month', 'mean', datetime_column='date')

    def test_group_data(self):
        data = self.get_data_2()
        result = sdt.group_data(data, 'group', 'mean')
        grp = data.groupby('group', as_index=False)
        expected = grp.mean()
        expected['name'] = grp.first()['name']
        expected['date'] = grp.first()['date']
        eft.enforce_dataframes_are_equal(result, expected)

    def test_group_data_quarter(self):
        data = DataFrame()
        data['date'] = [
            datetime(2021, 1, 1, 1, 1, 1, 1),
            datetime(2021, 2, 1, 1, 1, 1, 1),
            datetime(2021, 10, 1, 1, 1, 1, 1),
            datetime(2021, 11, 1, 1, 1, 1, 1),
            datetime(2021, 12, 1, 1, 1, 1, 1),
        ]

        result = sdt.group_data(data, 'quarter', 'count', datetime_column='date')
        result = result.quarter.astype(str).tolist()
        expected = ['2021-01-01', '2021-10-01']
        self.assertEqual(result, expected)

    def test_group_data_non_metric_columns(self):
        data = DataFrame()
        data['date'] = [
            datetime(2021, 1, 1, 1, 1, 1, 1),
            datetime(2021, 2, 1, 1, 1, 1, 1),
            datetime(2021, 10, 1, 1, 1, 1, 1),
            datetime(2021, 11, 1, 1, 1, 1, 1),
            datetime(2021, 12, 1, 1, 1, 1, 1),
        ]
        data['name'] = ['a', 'a', 'a', 'b', 'b']

        results = sdt.group_data(
            data, ['quarter', 'name'], 'count', datetime_column='date'
        )
        result = results.quarter.astype(str).tolist()
        expected = ['2021-01-01', '2021-10-01', '2021-10-01']
        self.assertEqual(result, expected)

        result = results.name.tolist()
        expected = ['a', 'a', 'b']
        self.assertEqual(result, expected)

    def test_group_data_two_week(self):
        data = DataFrame()
        data['date'] = [
            datetime(2021, 1, 1, 1, 1, 1, 1),
            datetime(2021, 1, 13, 1, 1, 1, 1),
            datetime(2021, 1, 22, 1, 1, 1, 1),
            datetime(2021, 1, 29, 1, 1, 1, 1),
            datetime(2021, 1, 30, 1, 1, 1, 1),
        ]

        result = sdt.group_data(data, 'two_week', 'count', datetime_column='date')
        result = result.two_week.astype(str).tolist()
        expected = ['2021-01-01', '2021-01-15', '2021-01-28']
        self.assertEqual(result, expected)

    def test_group_data_half_hour(self):
        data = DataFrame()
        data['date'] = [
            datetime(2021, 1, 1, 1, 0, 1, 1),
            datetime(2021, 1, 1, 1, 29, 1, 1),
            datetime(2021, 1, 1, 1, 31, 1, 1),
            datetime(2021, 1, 1, 1, 45, 1, 1),
            datetime(2021, 1, 1, 1, 59, 1, 1),
        ]

        result = sdt.group_data(data, 'half_hour', 'count', datetime_column='date')
        result = result.half_hour.astype(str).tolist()
        expected = ['2021-01-01 01:00:00', '2021-01-01 01:30:00']
        self.assertEqual(result, expected)

    def test_group_data_quarter_hour(self):
        data = DataFrame()
        data['date'] = [
            datetime(2021, 1, 1, 1, 0, 1, 1),
            datetime(2021, 1, 1, 1, 14, 1, 1),
            datetime(2021, 1, 1, 1, 46, 1, 1),
            datetime(2021, 1, 1, 1, 50, 1, 1),
            datetime(2021, 1, 1, 1, 59, 1, 1),
        ]

        result = sdt.group_data(data, 'quarter_hour', 'count', datetime_column='date')
        result = result.quarter_hour.astype(str).tolist()
        expected = ['2021-01-01 01:00:00', '2021-01-01 01:45:00']
        self.assertEqual(result, expected)

    # PIVOT-DATA----------------------------------------------------------------
    def test_pivot_data_errors(self):
        data = self.get_data_2()

        # data
        with self.assertRaises(EnforceError):
            sdt.pivot_data('id', 'age', 'mean')

        expected = 'DataFrame must be at least 1 in length. Given length: 0.'
        with self.assertRaisesRegexp(EnforceError, expected):
            d = DataFrame(columns=data.columns)
            sdt.pivot_data(d, 'age', 'mean')

        # columns
        expected = 'Given columns not found in data. '
        expected += r"\['pizza', 'taco'\] not in "
        expected += r"\['id', 'age', 'name', 'group', 'date'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.pivot_data(data, ['pizza', 'taco'])

        # values
        expected = 'Given columns not found in data. '
        expected += r"\['pizza'\] not in "
        expected += r"\['id', 'age', 'name', 'group', 'date'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.pivot_data(data, ['age'], values=['name', 'pizza'])
        sdt.pivot_data(data, ['age'], values=[])

        # index
        expected = r"pizza is not in legal column names: "
        expected += r"\['id.*year.*day.*\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.pivot_data(data, ['age'], values=['name'], index='pizza')
        sdt.pivot_data(data, ['age'], values=['name'], index=None)

    def test_pivot_data_time_columns(self):
        time_cols = [
            'date', 'year', 'quarter', 'month', 'two_week', 'week', 'day',
            'hour', 'half_hour', 'quarter_hour', 'minute', 'second',
            'microsecond'
        ]
        for col in time_cols:
            data = self.get_data_2()
            data[col] = data.date

            result = sdt.pivot_data(data.copy(), ['name'], values=['id'], index=col)
            expected = data.copy() \
                .pivot(columns=['name'], values=['id'], index=col)
            expected = expected['id']

            eft.enforce_columns_in_dataframe(expected.columns, result)

            result.index = Series(result.index.tolist()) \
                .apply(lambda x: datetime(
                    x.year, x.month, x.day, x.hour, x.minute, x.second,
                    microsecond=1
                ))
            eft.enforce_dataframes_are_equal(result, expected)

    def test_pivot_data(self):
        data = self.get_data_2()
        result = sdt.pivot_data(data, ['name'], values=['id'], index='id')
        expected = ['bill', 'dick', 'harry', 'jane', 'tom']
        self.assertEqual(result.columns.tolist(), expected)

        result = sdt.pivot_data(data, ['name'], values=['id', 'age'])
        expected += ['bill', 'dick', 'harry', 'jane', 'tom']
        self.assertEqual(result.columns.tolist(), expected)

        result = sdt.pivot_data(data, ['name'], values=['id', 'age'], index='id')
        self.assertEqual(result.columns.tolist(), expected)
        self.assertEqual(result.index.tolist(), [1, 2, 3, 4, 5])

    # GET-FIGURE----------------------------------------------------------------
    def test_get_figure_filter_error(self):
        data = self.get_data()
        good = dict(
            column='Description',
            comparator='~',
            value='amex|visa'
        )
        sdt.get_figure(data, filters=[good, good])

        bad = dict(
            comparator='~',
            value='amex|visa'
        )
        expected = 'Invalid filter.*column.*This field is required'
        with self.assertRaisesRegexp(DataError, expected):
            sdt.get_figure(data, filters=[good, bad])

    def test_get_figure_filter_zero_length(self):
        data = self.get_data()
        filt = dict(
            column='Amount',
            comparator='==',
            value='donotmatch',
        )
        sdt.get_figure(data, filters=[filt, filt, filt])

    def test_get_figure_filter_group(self):
        data = self.get_data()
        filt = dict(
            column='Amount',
            comparator='==',
            value='donotmatch',
        )
        grp = dict(
            columns=['Description', 'Amount'],
            metric='count',
            datetime_column='date',
        )
        sdt.get_figure(data, filters=[filt], group=grp)

    def test_get_figure_group_pivot(self):
        data = self.get_data()
        data['Description'] = None
        grp = dict(
            columns=['Description'],
            metric='count',
            datetime_column='date',
        )
        pvt = dict(
            columns=['Description', 'Category'],
            values=['Amount'],
            index='Date',
        )
        expected = 'DataFrame must be at least 1 in length. Given length: 0.'
        with self.assertRaisesRegexp(EnforceError, expected):
            sdt.get_figure(data, group=grp, pivot=pvt)

    def test_get_figure_group_error(self):
        data = self.get_data()
        good = dict(
            columns=['Description', 'Amount'],
            metric='count',
            datetime_column='date',
        )
        sdt.get_figure(data, group=good)

        bad = dict(
            metric='mean',
            datetime_column='date',
        )
        expected = 'Invalid group.*columns.*This field is required'
        with self.assertRaisesRegexp(DataError, expected):
            sdt.get_figure(data, group=bad)

    def test_get_figure_pivot_error(self):
        data = self.get_data()
        good = dict(
            columns=['Description', 'Category'],
            values=['Amount'],
            index='Date',
        )
        sdt.get_figure(data, pivot=good)

        bad = dict(
            values=['Amount'],
            index='Date',
        )
        expected = 'Invalid pivot.*columns.*This field is required'
        with self.assertRaisesRegexp(DataError, expected):
            sdt.get_figure(data, pivot=bad)

    def test_get_figure_params(self):
        data = self.get_data()
        pivot = dict(
            columns=['Description'],
            values=['Amount'],
            index='Date',
        )
        fig = sdt.get_figure(
            data,
            pivot=pivot,
            color_scheme={
                'grey1': '#0000FF',
                'cyan2': '#FF0000',
            },
            kind='hist',
            title='Foobar',
            x_title='foos',
            y_title='bars',
            bins=100
        )

        # color scheme
        result = fig['layout']['legend']['bgcolor']
        self.assertEqual(result, '#0000FF')

        result = fig['data'][0]['marker']['color']
        self.assertEqual(result, '#FF0000')

        # kind
        result = fig['data'][0]['type']
        self.assertEqual(result, 'histogram')

        # bins
        result = fig['data'][0]['nbinsx']
        self.assertEqual(result, 100)

        # title
        result = fig['layout']['title']['text']
        self.assertEqual(result, 'Foobar')

        # x_title
        result = fig['layout']['xaxis']['title']['text']
        self.assertEqual(result, 'foos')

        # y_title
        result = fig['layout']['yaxis']['title']['text']
        self.assertEqual(result, 'bars')
    # --------------------------------------------------------------------------

    def test_parse_rgba(self):
        result = sdt.parse_rgba('rgb(0, 0, 0)')
        self.assertEqual(result, (0, 0, 0))

        result = sdt.parse_rgba('rgb(255, 0, 0)')
        self.assertEqual(result, (255, 0, 0))

        result = sdt.parse_rgba('rgba(0, 0, 0, 0.5)')
        self.assertEqual(result, (0, 0, 0, 0.5))

        result = sdt.parse_rgba('rgba(255, 0, 0, 0.5)')
        self.assertEqual(result, (255, 0, 0, 0.5))

        result = sdt.parse_rgba('foo')
        self.assertIsNone(result)

    def test_conform_figure(self):
        data = self.get_data_2()
        fig = data.iplot(
            asFigure=True, theme='henanigans', colorscale='henanigans'
        ).to_dict()
        expected1 = '#0000FF'
        expected2 = '#FF0000'
        color_scheme = {
            'grey1': expected1,
            'cyan2': expected2
        }
        temp = sdt.conform_figure(fig, color_scheme)

        result = temp['layout']['legend']['bgcolor']
        self.assertEqual(result, expected1)

        result = temp['data'][0]['line']['color']
        self.assertEqual(result, expected2)
