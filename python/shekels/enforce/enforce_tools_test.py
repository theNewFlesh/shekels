import unittest

from lunchbox.enforce import EnforceError
from pandas import DataFrame

import shekels.enforce.enforce_tools as eft
# ------------------------------------------------------------------------------


class EnforceDataFrameTests(unittest.TestCase):
    def get_data(self):
        data = DataFrame()
        data['foo'] = [1, 2, 3]
        data['bar'] = [4, 5, 6]
        data['baz'] = [7, 8, 9]
        return data

    def test_enforce_dataframes_are_equal(self):
        a = self.get_data()
        eft.enforce_dataframes_are_equal(a, a)

        a['foo'] = None
        eft.enforce_dataframes_are_equal(a, a)

    def test_enforce_dataframes_are_equal_columns(self):
        a = self.get_data()
        a['pizza'] = [1, 1, 1]
        b = self.get_data()
        b['taco'] = [0, 0, 0]
        expected = r"A and b have different columns: \['pizza', 'taco'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            eft.enforce_dataframes_are_equal(a, b)

    def test_enforce_dataframes_are_equal_shape(self):
        a = self.get_data()
        a.loc[3] = [0, 0, 0]
        b = self.get_data()
        expected = r'A and b have different shapes. \(4, 3\) != \(3, 3\).'
        with self.assertRaisesRegexp(EnforceError, expected):
            eft.enforce_dataframes_are_equal(a, b)

    def test_enforce_dataframes_are_equal_values(self):
        a = self.get_data()
        b = self.get_data()
        b['foo'] = [3, 3, 3]
        b['baz'] = [9, 9, 9]

        msg = [
            ['foo', 1, 3],
            ['foo', 2, 3],
            ['baz', 7, 9],
            ['baz', 8, 9],
        ]
        msg = DataFrame(msg, columns=['column', 'a', 'b']).to_string()
        expected = f'DatFrames have different values:\n{msg}'
        with self.assertRaisesRegexp(EnforceError, expected):
            eft.enforce_dataframes_are_equal(a, b)

    def test_enforce_columns_in_dataframe(self):
        cols = ['foo', 'bar', 'baz']
        data = DataFrame(columns=cols)
        eft.enforce_columns_in_dataframe(cols, data)

        cols = ['foo', 'bar', 'taco']
        expected = 'Given columns not found in data. '
        expected += r"\['taco'\] not in \['foo', 'bar', 'baz'\]\."
        with self.assertRaisesRegexp(EnforceError, expected):
            eft.enforce_columns_in_dataframe(cols, data)
