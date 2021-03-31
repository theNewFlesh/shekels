from typing import List, Union

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import jsoncomment as jsonc
import numpy as np
import pandas as pd

from shekels.core.config import Config
import shekels.core.data_tools as sdt
# ------------------------------------------------------------------------------


class Database:
    '''
    Database is a class for wrapping a mint transaction DataFrame with a simple
    CRUD-like API. API methods include: update, read and search.
    '''
    @staticmethod
    def from_json(filepath):
        # type: (Union[str, Path]) -> Database
        '''
        Constructs a Database instance from a given JSON filepath.

        Args:
            filepath(Path or str): Path to JSON config file.

        Returns:
            Database: Database instance.
        '''
        with open(filepath) as f:
            config = jsonc.JsonComment().load(f)
        return Database(config)

    def __init__(self, config):
        # type: (dict) -> None
        '''
        Constructs a Database instance.

        Args:
            config (dict): Configuration.
        '''
        config = Config(config)
        config.validate()
        self._config = config.to_primitive()
        self._data = None  # type: Union[None, pd.DataFrame]

    @staticmethod
    def _to_records(data):
        # type: (pd.DataFrame) -> List[dict]
        '''
        Converts given DataFrame to a list of JSONifiable dicts.

        Args:
            data (DataFrame): Data.

        Returns:
            list[dict]: Records.
        '''
        data = data.copy()
        data.date = data.date.apply(lambda x: x.isoformat())
        data = data.replace({np.nan: None}).to_dict(orient='records')
        return data

    @property
    def config(self):
        # type: () -> dict
        '''
        Returns a copy of this instance's configuration.

        Returns:
            dict: Copy of config.
        '''
        return deepcopy(self._config)

    @property
    def data(self):
        # type: () -> Union[None, pd.DataFrame]
        '''
        Returns a copy of this instance's data.

        Returns:
            DataFrame: Copy of data.
        '''
        if self._data is None:
            return None
        return self._data.copy()

    def update(self):
        # type: () -> Database
        '''
        Loads CSV found in config's data_path into self._data.

        Returns:
            Database: self.
        '''
        data = pd.read_csv(self._config['data_path'], index_col=None)
        self._data = sdt.conform(
            data,
            actions=self._config['conform'],
            columns=self._config['columns'],
        )
        return self

    @lru_cache(maxsize=1)
    def read(self):
        # type: () -> List[dict]
        '''
        Returns data if update has been called.

        Raises:
            RuntimeError: If update has not first been called.

        Returns:
            list[dict]: Data as records.
        '''
        if self._data is None:
            msg = 'Database not updated. Please call update.'
            raise RuntimeError(msg)
        return self._to_records(self._data)

    @lru_cache()
    def search(self, query):
        # type: (str) -> List[dict]
        '''
        Search data according to given SQL query.

        Args:
            query (str): SQL query. Make sure to use "FROM data" in query.

        Returns:
            DataFrame: Formatted data.
        '''
        output = sdt.query_data(self._data, query)
        # pandasql coerces Timestamps to strings
        output.date = pd.DatetimeIndex(output.date)
        return self._to_records(output)
