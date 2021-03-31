from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandas import DataFrame
import numpy as np
import pandas as pd

import shekels.core.config as cfg
import shekels.core.data_tools as sdt
import shekels.core.database as db
import shekels.enforce.enforce_tools as eft
# ------------------------------------------------------------------------------


class DatabaseTests(unittest.TestCase):
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

    def write_data(self, root):
        data_path = Path(root, 'transactions.csv').as_posix()
        self.get_data().to_csv(data_path, index=False)
        return data_path
    # --------------------------------------------------------------------------

    def test_write_data(self):
        with TemporaryDirectory() as root:
            result = self.write_data(root)
            result = pd.read_csv(result, index_col=None)
            self.assertEqual

    def get_config(self, root):
        config = self.get_partial_config()
        config['data_path'] = self.write_data(root)
        config['columns'] = []
        config = cfg.Config(config).to_primitive()

        config_path = Path(root, 'config.json').as_posix()
        with open(config_path, 'w') as f:
            json.dump(config, f)
        return config, config_path

    def test_init(self):
        with TemporaryDirectory() as root:
            config, _ = self.get_config(root)
            result = db.Database(config)
            self.assertEqual(result._config, config)
            self.assertIs(result._data, None)

    def test_from_json(self):
        with TemporaryDirectory() as root:
            config, config_path = self.get_config(root)
            result = db.Database.from_json(config_path)
            self.assertEqual(result._config, config)

    def test_config(self):
        with TemporaryDirectory() as root:
            expected, _ = self.get_config(root)
            result = db.Database(expected).config
            self.assertEqual(result, expected)

    def test_data(self):
        with TemporaryDirectory() as root:
            config, _ = self.get_config(root)
            temp = db.Database(config).update()
            result = temp.data
            result['new_col'] = None
            result = result.columns.tolist()
            expected = temp._data.columns.tolist()
            self.assertNotEqual(result, expected)

    def test_to_records(self):
        data = self.get_data()
        data = sdt.conform(data)
        result = db.Database._to_records(data)
        expected = data.copy()
        expected.date = expected.date.apply(lambda x: x.isoformat())
        expected = expected.replace({np.nan: None}).to_dict(orient='records')
        self.assertEqual(result, expected)

    def test_to_records_no_mutation(self):
        result = self.get_data()
        result = sdt.conform(result)
        expected = result.copy()
        db.Database._to_records(result)
        eft.enforce_dataframes_are_equal(result, expected)

    def test_update(self):
        with TemporaryDirectory() as root:
            config, _ = self.get_config(root)
            result = db.Database(config).update()._data

            expected = pd.read_csv(config['data_path'], index_col=None)
            expected = sdt.conform(
                expected, actions=config['conform'], columns=config['columns']
            )

            eft.enforce_dataframes_are_equal(result, expected)

    def test_read(self):
        with TemporaryDirectory() as root:
            config, _ = self.get_config(root)
            dbase = db.Database(config).update()
            result = dbase.read()

            expected = dbase.data
            expected.date = expected.date.apply(lambda x: x.isoformat())
            expected = expected.replace({np.nan: None}).to_dict(orient='records')

            self.assertEqual(result, expected)

            expected = 'Database not updated. Please call update.'
            with self.assertRaisesRegexp(RuntimeError, expected):
                db.Database(config).read()

    def test_search(self):
        with TemporaryDirectory() as root:
            config, _ = self.get_config(root)
            query = "SELECT * FROM data WHERE description LIKE 'Ignore'"
            result = db.Database(config).update().search(query)
            self.assertEqual(len(result), 1)
