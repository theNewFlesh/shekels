from typing import Any, Dict, List, Optional, Union

from copy import copy
from random import randint
import datetime as dt
import re

from lunchbox.enforce import Enforce
from pandas import DataFrame, DatetimeIndex
from schematics.exceptions import DataError
import cufflinks as cf  # noqa: F401
import lunchbox.tools as lbt
import numpy as np
import pandasql
import pyparsing as pp
import rolling_pin.blob_etl as rpb
import webcolors

from shekels.core.config import ConformAction
import shekels.core.config as cfg
import shekels.enforce.enforce_tools as eft
# ------------------------------------------------------------------------------


COLOR_COERCION_LUT = {
    '#00CC96': '#5F95DE',
    '#0D0887': '#444459',
    '#19D3F3': '#5F95DE',
    '#242424': '#242424',
    '#276419': '#343434',
    '#2A3F5F': '#444459',
    '#343434': '#343434',
    '#444444': '#444444',
    '#46039F': '#444459',
    '#4D9221': '#444444',
    '#636EFA': '#5F95DE',
    '#7201A8': '#5D5D7A',
    '#7FBC41': '#8BD155',
    '#8E0152': '#444459',
    '#9C179E': '#5D5D7A',
    '#A4A4A4': '#A4A4A4',
    '#AB63FA': '#AC92DE',
    '#B6E880': '#A0D17B',
    '#B6ECF3': '#B6ECF3',
    '#B8E186': '#A0D17B',
    '#BD3786': '#F77E70',
    '#C51B7D': '#F77E70',
    '#C8D4E3': '#B6ECF3',
    '#D8576B': '#F77E70',
    '#DE77AE': '#DE958E',
    '#DE958E': '#DE958E',
    '#E5ECF6': '#F4F4F4',
    '#E6F5D0': '#E9EABE',
    '#EBF0F8': '#F4F4F4',
    '#ED7953': '#F77E70',
    '#EF553B': '#F77E70',
    '#F0F921': '#E8EA7E',
    '#F1B6DA': '#C98FDE',
    '#F4F4F4': '#F4F4F4',
    '#F7F7F7': '#F4F4F4',
    '#FB9F3A': '#EB9E58',
    '#FDCA26': '#EB9E58',
    '#FDE0EF': '#F4F4F4',
    '#FECB52': '#EB9E58',
    '#FF6692': '#F77E70',
    '#FF97FF': '#C98FDE',
    '#FFA15A': '#EB9E58',
}


def conform(data, actions=[], columns=[]):
    # type: (DataFrame, List[dict], List[str]) -> DataFrame
    '''
    Conform given mint transaction data.

    Args:
        data (DataFrame): Mint transactions DataFrame.
        actions (list[dict], optional): List of conform actions. Default: [].
        columns (list[str], optional): List of columns. Default: [].

    Raises:
        DataError: If invalid conform action given.
        ValueError: If source column not found in data columns.

    Returns:
        DataFrame: Conformed DataFrame.
    '''
    for action in actions:
        ConformAction(action).validate()

    data.rename(lbt.to_snakecase, axis=1, inplace=True)
    lut = dict(
        account_name='account',
        transaction_type='type'
    )
    data.rename(lambda x: lut.get(x, x), axis=1, inplace=True)
    data.date = DatetimeIndex(data.date)
    data.amount = data.amount.astype(float)
    data.category = data.category \
        .apply(lambda x: re.sub('&', 'and', lbt.to_snakecase(x)))
    data.account = data.account.apply(lbt.to_snakecase)

    for action in actions:
        source = action['source_column']
        if source not in data.columns:
            msg = f'Source column {source} not found in columns. '
            msg += f'Legal columns include: {data.columns.tolist()}.'
            raise ValueError(msg)

        target = action['target_column']
        if target not in data.columns:
            data[target] = None

        for regex, val in action['mapping'].items():
            if action['action'] == 'overwrite':
                mask = data[source] \
                    .apply(lambda x: re.search(regex, x, flags=re.I)).astype(bool)
                data.loc[mask, target] = val
            elif action['action'] == 'substitute':
                data[target] = data[source] \
                    .apply(lambda x: re.sub(regex, val, str(x), flags=re.I))

    if columns != []:
        data = data[columns]
    return data


def filter_data(data, column, comparator, value):
    # type: (DataFrame, str, str, Any) -> DataFrame
    '''
    Filters given data via comparator(column value, value).

    Legal comparators:

        * == ``lambda a, b: a == b``
        * != ``lambda a, b: a != b``
        *  > ``lambda a, b: a > b``
        * >= ``lambda a, b: a >= b``
        *  < ``lambda a, b: a < b``
        * =< ``lambda a, b: a <= b``
        *  ~ ``lambda a, b: bool(re.search(a, b, flags=re.I))``
        * !~ ``lambda a, b: not bool(re.search(a, b, flags=re.I))``

    Args:
        data (DataFrame): DataFrame to be filtered.
        column (str): Column name.
        comparator (str): String representation of comparator.
        value (object): Value to be compared.

    Raises:
        EnforceError: If data is not a DataFrame.
        EnforceError: If column is not a string.
        EnforceError: If column not in data columns.
        EnforceError: If illegal comparator given.
        EnforceError: If comparator is ~ or !~ and value is not a string.

    Returns:
        DataFrame: Filtered data.
    '''
    Enforce(data, 'instance of', DataFrame)
    msg = 'Column must be a str. {a} is not str.'
    Enforce(column, 'instance of', str, message=msg)
    eft.enforce_columns_in_dataframe([column], data)

    lut = {
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
        '>': lambda a, b: a > b,
        '>=': lambda a, b: a >= b,
        '<': lambda a, b: a < b,
        '<=': lambda a, b: a <= b,
        '~': lambda a, b: bool(re.search(b, a, flags=re.I)),
        '!~': lambda a, b: not bool(re.search(b, a, flags=re.I)),
    }
    msg = 'Illegal comparator. {a} not in [==, !=, >, >=, <, <=, ~, !~].'
    Enforce(comparator, 'in', lut.keys(), message=msg)

    if comparator in ['~', '!~']:
        msg = 'Value must be string if comparator is ~ or !~. {a} is not str.'
        Enforce(value, 'instance of', str, message=msg)
    # --------------------------------------------------------------------------

    op = lut[comparator]
    mask = data[column].apply(lambda x: op(x, value))
    data = data[mask]
    return data


def group_data(data, columns, metric, datetime_column='date'):
    # type: (DataFrame, Union[str, List[str]], str, str) -> DataFrame
    '''
    Groups given data by given columns according to given metric.
    If a legal time interval is given in the columns, then an additional special
    column of that same name is added to the data for grouping.

    Legal metrics:

        *   max ``lambda x: x.max()``
        *  mean ``lambda x: x.mean()``
        *   min ``lambda x: x.min()``
        *   std ``lambda x: x.std()``
        *   sum ``lambda x: x.sum()``
        *   var ``lambda x: x.var()``
        * count ``lambda x: x.count()``

    Legal time intervals:

        * year
        * quarter
        * month
        * two_week
        * week
        * day
        * hour
        * half_hour
        * quarter_hour
        * minute
        * second
        * microsecond

    Args:
        data (DataFrame): DataFrame to be grouped.
        columns (str or list[str]): Columns to group data by.
        metric (str): String representation of metric.
        datetime_column (str, optinal): Datetime column for time grouping.
            Default: date.

    Raises:
        EnforceError: If data is not a DataFrame.
        EnforceError: If columns not in data columns.
        EnforceError: If illegal metric given.
        EnforceError: If time interval in columns and datetime_column not in
            columns.

    Returns:
        DataFrame: Grouped data.
    '''
    # luts
    met_lut = {
        'max': lambda x: x.max(),
        'mean': lambda x: x.mean(),
        'min': lambda x: x.min(),
        'std': lambda x: x.std(),
        'sum': lambda x: x.sum(),
        'var': lambda x: x.var(),
        'count': lambda x: x.count(),
    }

    time_lut = {
        'year': lambda x: dt.datetime(x.year, 1, 1),
        'quarter': lambda x: dt.datetime(
            x.year, int(np.ceil(x.month / 3) * 3 - 2), 1
        ),
        'month': lambda x: dt.datetime(x.year, x.month, 1),
        'two_week': lambda x: dt.datetime(
            x.year, x.month, min(int(np.ceil(x.day / 14) * 14 - 13), 28)
        ),
        'week': lambda x: dt.datetime(
            x.year, x.month, max(1, min([int(x.month / 7) * 7, 28]))
        ),
        'day': lambda x: dt.datetime(x.year, x.month, x.day),
        'hour': lambda x: dt.datetime(x.year, x.month, x.day, x.hour),
        'half_hour': lambda x: dt.datetime(
            x.year, x.month, x.day, x.hour, int(x.minute / 30) * 30
        ),
        'quarter_hour': lambda x: dt.datetime(
            x.year, x.month, x.day, x.hour, int(x.minute / 15) * 15
        ),
        'minute': lambda x: dt.datetime(
            x.year, x.month, x.day, x.hour, x.minute
        ),
        'second': lambda x: dt.datetime(
            x.year, x.month, x.day, x.hour, x.minute, x.second
        ),
        'microsecond': lambda x: dt.datetime(
            x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond
        ),
    }
    # --------------------------------------------------------------------------

    # enforcements
    Enforce(data, 'instance of', DataFrame)
    columns_ = columns  # type: Any
    if type(columns_) != list:
        columns_ = [columns_]

    cols = list(filter(lambda x: x not in time_lut.keys(), columns_))
    eft.enforce_columns_in_dataframe(cols, data)

    msg = '{a} is not a legal metric. Legal metrics: {b}.'
    Enforce(metric, 'in', sorted(list(met_lut.keys())), message=msg)

    # time column
    if len(columns_) > len(cols):
        eft.enforce_columns_in_dataframe([datetime_column], data)
        msg = 'Datetime column of type {a}, it must be of type {b}.'
        Enforce(
            data[datetime_column].dtype.type, '==', np.datetime64, message=msg
        )
    # --------------------------------------------------------------------------

    for col in columns_:
        if col in time_lut.keys():
            op = time_lut[col]
            data[col] = data[datetime_column].apply(op)
    agg = met_lut[metric]
    cols = data.columns.tolist()
    grp = data.groupby(columns_, as_index=False)
    output = agg(grp)

    # get first value for columns that cannot be computed by given metric
    diff = set(cols).difference(output.columns.tolist())
    if len(diff) > 0:
        first = grp.first()
        for col in diff:
            output[col] = first[col]
    return output


def pivot_data(data, columns, values=[], index=None):
    # type: (DataFrame, List[str], List[str], Optional[str]) -> DataFrame
    '''
    Pivots a given dataframe via a list of columns.

    Legal time columns:

        * date
        * year
        * quarter
        * month
        * two_week
        * week
        * day
        * hour
        * half_hour
        * quarter_hour
        * minute
        * second
        * microsecond

    Args:
        data (DataFrame): DataFrame to be pivoted.
        columns (list[str]): Columns whose unique values become separate traces
            within a plot.
        values (list[str], optional): Columns whose values become the values
            within each trace of a plot. Default: [].
        index (str, optional): Column whose values become the y axis values of a
            plot. Default: None.

    Raises:
        EnforceError: If data is not a DataFrame.
        EnforceError: If data is of zero length.
        EnforceError: If columns not in data columns.
        EnforceError: If values not in data columns.
        EnforceError: If index not in data columns or legal time columns.

    Returns:
        DataFrame: Pivoted data.
    '''
    time_cols = [
        'date', 'year', 'quarter', 'month', 'two_week', 'week', 'day', 'hour',
        'half_hour', 'quarter_hour', 'minute', 'second', 'microsecond',
    ]

    Enforce(data, 'instance of', DataFrame)
    msg = 'DataFrame must be at least 1 in length. Given length: {a}.'
    Enforce(len(data), '>=', 1, message=msg)
    eft.enforce_columns_in_dataframe(columns, data)
    eft.enforce_columns_in_dataframe(values, data)
    if index is not None:
        msg = '{a} is not in legal column names: {b}.'
        Enforce(index, 'in', data.columns.tolist() + time_cols, message=msg)
    # --------------------------------------------------------------------------

    vals = copy(values)
    if index is not None and index not in values:
        vals.append(index)

    if index in time_cols:
        data[index] = data[index] \
            .apply(lambda x: x + dt.timedelta(microseconds=randint(0, 999999)))

    data = data.pivot(columns=columns, values=vals, index=index)
    data = data[values]
    data.columns = data.columns.droplevel(0)
    return data


def get_figure(
    data,              # type: DataFrame
    filters=[],        # type: List[dict]
    group=None,        # type: Optional[dict]
    pivot=None,        # type: Optional[dict]
    kind='bar',        # type: str
    color_scheme={},   # type: Dict[str, str]
    x_axis=None,       # type: Optional[str]
    y_axis=None,       # type: Optional[str]
    title=None,        # type: Optional[str]
    x_title=None,      # type: Optional[str]
    y_title=None,      # type: Optional[str]
    bins=50,           # type: int
    bar_mode='stack',  # type: str
):
    '''
    Generates a plotly figure dictionary from given data and manipulations.

    Args:
        data (DataFrame): Data.
        filters (list[dict], optional): List of filters for data. Default: [].
        group (dict, optional): Grouping operation. Default: None.
        pivot (dict, optional): Pivot operation. Default: None.
        kind (str, optional): Kind of plot. Default: bar.
        color_scheme (dict[str, str], optional): Color scheme. Default: {}.
        x_axis (str): Column to use as x axis: Default: None.
        y_axis (str): Column to use as y axis: Default: None.
        title (str, optional): Title of plot. Default: None.
        x_title (str, optional): Title of x axis. Default: None.
        y_title (str, optional): Title of y axis. Default: None.
        bins (int, optional): Number of bins if histogram. Default: 50.
        bar_mode (str, optional): How bars in bar graph are presented.
            Default: stack.

    Raises:
        DataError: If any filter in filters is invalid.
        DataError: If group is invalid.
        DataError: If pivot is invalid.

    Returns:
        dict: Plotly Figure as dictionary.
    '''
    data = data.copy()

    # filter
    for f in filters:
        f = cfg.FilterAction(f)
        try:
            f.validate()
        except DataError as e:
            raise DataError({'Invalid filter': e.to_primitive()})

        f = f.to_primitive()
        if len(data) == 0:
            break
        data = filter_data(data, f['column'], f['comparator'], f['value'])

    # group
    if group is not None:
        grp = group  # type: Any
        grp = cfg.GroupAction(grp)
        try:
            grp.validate()
        except DataError as e:
            raise DataError({'Invalid group': e.to_primitive()})
        grp = grp.to_primitive()

        data = group_data(
            data,
            grp['columns'],
            grp['metric'],
            datetime_column=grp['datetime_column'],
        )

    # pivot
    if pivot is not None:
        pvt = pivot  # type: Any
        pvt = cfg.PivotAction(pvt)
        try:
            pvt.validate()
        except DataError as e:
            raise DataError({'Invalid pivot': e.to_primitive()})
        pvt = pvt.to_primitive()

        data = pivot_data(
            data, pvt['columns'], values=pvt['values'], index=pvt['index']
        )

    # create figure
    figure = data.iplot(
        kind=kind, asFigure=True, theme='henanigans', colorscale='henanigans',
        x=x_axis, y=y_axis, title=title, xTitle=x_title, yTitle=y_title,
        barmode=bar_mode, bins=bins
    ).to_dict()  # type: dict
    figure['layout']['title']['font']['color'] = '#F4F4F4'
    figure['layout']['xaxis']['title']['font']['color'] = '#F4F4F4'
    figure['layout']['yaxis']['title']['font']['color'] = '#F4F4F4'
    if color_scheme != {}:
        figure = conform_figure(figure, color_scheme)
    return figure


def parse_rgba(string):
    '''
    Parses rgb and rgba strings into tuples of numbers.

    Example:
        >>>parse_rgba('rgb(255, 0, 0)')
        (255, 0, 0)
        >>>parse_rgba('rgba(255, 0, 0, 0.5)')
        (255, 0, 0, 0.5)
        >>>parse_rgba('foo') is None
        True

    Args:
        string (str): String to be parsed.

    Returns:
        tuple: (red, green, blue) or (red, green, blue, alpha)
    '''
    result = re.search(r'rgba?\((\d+, \d+, \d+(, \d+\.?\d*)?)\)', string)
    if result is None:
        return None

    result = result.group(1)
    result = re.split(', ', result)
    if len(result) == 3:
        result = tuple(map(int, result))
        return result

    result = list(map(int, result[:-1])) + [float(result[-1])]
    result = tuple(result)
    return result


def conform_figure(figure, color_scheme):
    '''
    Conforms given figure to use given color scheme.

    Args:
        figure (dict): Plotly figure.
        color_scheme (dict): Color scheme dictionary.

    Returns:
        dict: Conformed figure.
    '''
    # create hex to hex lut
    lut = {}
    for key, val in cfg.COLOR_SCHEME.items():
        if key in color_scheme:
            lut[val] = color_scheme[key]

    # rgba? to hex --> coerce to standard colors --> coerce with color_scheme
    figure = rpb.BlobETL(figure) \
        .set(
            predicate=lambda k, v: isinstance(v, str) and 'rgb' in v,
            value_setter=lambda k, v: webcolors.rgb_to_hex(parse_rgba(v)[:3]).upper()) \
        .set(
            predicate=lambda k, v: isinstance(v, str),
            value_setter=lambda k, v: COLOR_COERCION_LUT.get(v, v)) \
        .set(
            predicate=lambda k, v: isinstance(v, str),
            value_setter=lambda k, v: lut.get(v, v)) \
        .to_dict()
    return figure


# SQL-PARSING-------------------------------------------------------------------
def get_sql_grammar():
    '''
    Creates a grammar for parsing SQL queries.

    Returns:
       MatchFirst: SQL parser.
    '''
    select = pp.Regex('select', flags=re.I) \
        .setParseAction(lambda s, l, t: 'select') \
        .setResultsName('operator')
    from_ = pp.Suppress(pp.Regex('from', flags=re.I))
    table = (from_ + pp.Regex('[a-z]+', flags=re.I)) \
        .setParseAction(lambda s, l, t: t[0]) \
        .setResultsName('table')
    regex = pp.Regex('~|regex').setParseAction(lambda s, l, t: '~')
    not_regex = pp.Regex('!~|not regex').setParseAction(lambda s, l, t: '!~')
    any_op = pp.Regex('[^ ]*')
    operator = pp.Or([not_regex, regex, any_op]).setResultsName('operator')
    quote = pp.Suppress(pp.Optional("'"))
    value = (quote + pp.Regex('[^\']+', flags=re.I) + quote) \
        .setResultsName('value') \
        .setParseAction(lambda s, l, t: t[0])
    columns = pp.delimitedList(pp.Regex('[^, ]*'), delim=pp.Regex(', *')) \
        .setResultsName('display_columns')
    column = pp.Regex('[a-z]+', flags=re.I).setResultsName('column')
    conditional = column + operator + value
    head = select + columns + table
    grammar = head | conditional
    return grammar


def query_data(data, query):
    '''
    Parses SQL + regex query and applies it to given data.

    Regex operators:

        * ~, regex - Match regular expression
        * !~, not regex - Do not match regular expression

    Args:
        data (DataFrame): DataFrame to be queried.
        query (str): SQL query that may include regex operators.

    Returns:
        DataFrame: Data filtered by query.
    '''
    # split queries by where/and/or
    queries = re.split(' where | and | or ', query, flags=re.I)

    # detect whether any sub query has a regex operator
    has_regex = False
    for q in queries:
        if re.search(' regex | ~ | !~ ', q, flags=re.I):
            has_regex = True
            break

    # if no regex operator is found just submit query to pandasql
    if not has_regex:
        data = pandasql.sqldf(query, {'data': data})

    else:
        grammar = get_sql_grammar()

        # move select statement to end
        if 'select' in queries[0]:
            q = queries.pop(0)
            queries.append(q)

        for q in queries:
            # get column, operator and value
            parse = grammar.parseString(q).asDict()
            op = parse['operator']

            # initial select statement
            if op == 'select':
                data = pandasql.sqldf(q, {'data': data})

            # regex search
            elif op == '~':
                mask = data[parse['column']] \
                    .astype(str) \
                    .apply(lambda x: re.search(parse['value'], x, flags=re.I)) \
                    .astype(bool)
                data = data[mask]

            # regex not search
            elif op == '!~':
                mask = data[parse['column']] \
                    .astype(str) \
                    .apply(lambda x: re.search(parse['value'], x, flags=re.I)) \
                    .astype(bool)
                data = data[~mask]

            # ther SQL query
            else:
                data = pandasql.sqldf('select * from data where ' + q, {'data': data})

            if len(data) == 0:
                break
    return data


def query_dict(data, query):
    # type: (dict, str) -> dict
    '''
    Query a given diction with a given SQL query.

    Args:
        data (dict): Dictionary to be queried.
        query (str): SQL query.

    Returns:
        dict: Queried dictionary.
    '''
    data_ = data  # type: Any
    data_ = rpb.BlobETL(data_) \
        .to_flat_dict() \
        .items()
    data_ = DataFrame(list(data_), columns=['key', 'value'])
    data_ = query_data(data_, query)
    data_ = dict(zip(data_.key.tolist(), data_.value.tolist()))
    data_ = rpb.BlobETL(data_).to_dict()
    return data_
