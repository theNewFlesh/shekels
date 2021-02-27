from typing import Any, Dict, Union

import os
from pathlib import Path

import schematics.types as sty
from schematics.models import Model
from schematics.exceptions import CompoundError, DataError, ValidationError


# VALIDATORS--------------------------------------------------------------------
COLOR_SCHEME = dict(
    dark1='#040404',
    dark2='#141414',
    bg='#181818',
    grey1='#242424',
    grey2='#444444',
    light1='#A4A4A4',
    light2='#F4F4F4',
    dialog1='#444459',
    dialog2='#5D5D7A',
    red1='#F77E70',
    red2='#DE958E',
    orange1='#EB9E58',
    orange2='#EBB483',
    yellow1='#E8EA7E',
    yellow2='#E9EABE',
    green1='#8BD155',
    green2='#A0D17B',
    cyan1='#7EC4CF',
    cyan2='#B6ECF3',
    blue1='#5F95DE',
    blue2='#93B6E6',
    purple1='#C98FDE',
    purple2='#AC92DE',
)  # type: Dict[str, str]


def is_color_scheme(item):
    # type: (dict) -> None
    '''
    Determines if given dict is a valid color scheme.

    Args:
        item (dict): Color scheme dictionary.

    Raises:
        ValidationError: If item contains invalid keys.
    '''
    keys = list(COLOR_SCHEME.keys())
    ikeys = list(item.keys())

    diff = set(ikeys).difference(keys)  # type: Any
    diff = sorted(list(diff))
    if len(diff) > 0:
        msg = f'Invalid color scheme keys: {diff}.'
        raise ValidationError(msg)


def is_csv(filepath):
    # type: (Union[str, Path]) -> None
    '''
    Determines if given filepath is a CSV.

    Args:
        filepath (str or Path): Filepath.

    Raises:
        ValidationError: If filepath is not a CSV.
    '''
    filepath = Path(filepath).as_posix()
    ext = os.path.splitext(filepath)[-1][1:].lower()
    if not os.path.isfile(filepath) or ext != 'csv':
        msg = f'{filepath} is not a valid CSV file.'
        raise ValidationError(msg)


def is_comparator(item):
    # type: (str) -> None
    '''
    Ensures that given string is a legal comparator.

    Legal comparators:

        * ==
        * !=
        * >
        * >=
        * <
        * =<
        * ~
        * !~

    Args:
        item (str): String to be tested.

    Raises:
        ValidationError: If item is not a legal comparator.
    '''
    comps = ['==', '!=', '>', '>=', '<', '=<', '~', '!~']
    if item not in comps:
        msg = f'{item} is not a legal comparator. Legal comparators: {comps}.'
        raise ValidationError(msg)


def is_metric(item):
    # type: (str) -> None
    '''
    Ensures that given string is a legal metric.

    Legal metrics:

        * max
        * mean
        * min
        * std
        * sum
        * var
        * count

    Args:
        item (str): String to be tested.

    Raises:
        ValidationError: If item is not a legal metric.
    '''
    metrics = ['max', 'mean', 'min', 'std', 'sum', 'var', 'count']
    if item not in metrics:
        msg = f'{item} is not a legal metric. Legal metrics: {metrics}.'
        raise ValidationError(msg)


def is_plot_kind(item):
    '''
    Ensures item is a kind of plotly plot.

    Args:
        item (str): Kind of plot.

    Raises:
        ValidationError: If item is a plot kind.
    '''
    kinds = [
        'area', 'bar', 'barh', 'line' 'lines', 'ratio', 'scatter', 'spread'
    ]
    if item not in kinds:
        msg = f'{item} is not a legal plot kind. Legal kinds: {kinds}.'
        raise ValidationError(msg)


def is_bar_mode(item):
    '''
    Ensures mode is a legal bar mode.

    Args:
        item (str): Mode.

    Raises:
        ValidationError: If mode is not a legal bar mode.
    '''
    modes = ['stack', 'group', 'overlay']
    if item not in modes:
        msg = f'{item} is not a legal bar mode. Legal bar modes: {modes}.'
        raise ValidationError(msg)


def is_percentage(number):
    '''
    Ensures number is between 0 and 100.

    Args:
        number (float): Number to be tested.

    Raises:
        ValidationError: If number is not between 0 and 100.
    '''
    if number < 0 or number > 100:
        msg = f'{number} is not a legal percentage. '
        msg += f'{number} is not between 0 and 100.'
        raise ValidationError(msg)


# SCHEMATICS--------------------------------------------------------------------
class FilterAction(Model):
    '''
    Schematic for filter actions.

    Attributes:
        column (str): Column name.
        comparator (str): String representation of comparator.
        value (object): Value to be compared.
    '''
    column = sty.StringType(required=True)
    comparator = sty.StringType(required=True, validators=[is_comparator])
    value = sty.BaseType(required=True)


class GroupAction(Model):
    '''
    Schematic for group actions.

    Attributes:
        columns (str or list[str]): Columns to group data by.
        metric (str): Aggregation metric.
        datetime_column (str, optinal): Datetime column for time grouping.
            Default: date.
    '''
    columns = sty.ListType(sty.StringType(), required=True)
    metric = sty.StringType(required=True, validators=[is_metric])
    datetime_column = sty.StringType(required=True, default='date')


class PivotAction(Model):
    '''
    Schematic for group actions.

    Attributes:
        columns (list[str]): Columns whose unique values become separate traces
            within a plot.
        values (list[str], optional): Columns whose values become the values
            within each trace of a plot. Default: [].
        index (str, optional): Column whose values become the y axis values of a
            plot. Default: None.
    '''
    columns = sty.ListType(sty.StringType(), required=True)
    values = sty.ListType(sty.StringType(), required=True, default=[])
    index = sty.StringType(required=True, default=None)


class ConformAction(Model):
    '''
    Schematic for conform actions.

    Attributes:
        action (str): Must be 'overwrite' or 'substitute'.
        source_column (str): Source column to be matched.
        target_column (str): Target column to be overwritten.
        mapping (dict): Mapping of matched key in source column with replacement
            value in target column.
    '''
    action = sty.StringType(required=True, choices=['overwrite', 'substitute'])
    source_column = sty.StringType(required=True)
    target_column = sty.StringType(required=True)
    mapping = sty.DictType(
        sty.UnionType(
            types=[sty.FloatType, sty.IntType, sty.BooleanType, sty.StringType]
        ),
        required=True,
    )

    def validate(self):
        '''
        Validates the state of the model. If the data is invalid, raises a
        DataError with error messages. Also, performs a stricter validation on
        mapping if action is substitute.

        Args:
            partial (bool, optional): Allow partial data to validate.
                Essentially drops the required=True settings from field
                definitions. Default: False.
            convert (bool, optional): Controls whether to perform import
                conversion before validating. Can be turned off to skip an
                unnecessary conversion step if all values are known to have the
                right datatypes (e.g., when validating immediately after the
                initial import). Default: True.

        Raises:
            DataError: If data is invalid.
        '''
        super().validate()
        if self.action == 'substitute':
            try:
                sty.DictType(sty.StringType(), required=True)\
                    .validate(self.mapping)
            except CompoundError as e:
                raise DataError(e.to_primitive())


class FigureItem(Model):
    '''
    Schematic for a plot figure.

    Attributes:
        kind (str): Type of plot. Default: bar.
        color_scheme (dict[str, str]): Color scheme for plot.
            Default: {'grey1': '#181818', 'bg': '#242424'}.
        x_axis (str): Column to use as x axis: Default: None.
        y_axis (str): Column to use as y axis: Default: None.
        title (str): Title of plot. Default: None.
        x_title (str): Title of plot x axis. Default: None.
        y_title (str): Title of plot y axis. Default: None.
        bins (int): Number of bins if histogram. Default: 50.
        bar_mode (str): How bars in bar graph are presented. Default: stack.
    '''
    kind = sty.StringType(default='bar', validators=[is_plot_kind])
    color_scheme = sty.DictType(
        sty.StringType(), default=dict(grey1='#181818', bg='#242424')
    )
    x_axis = sty.StringType(default=None)
    y_axis = sty.StringType(default=None)
    title = sty.StringType(default=None)
    x_title = sty.StringType(default=None)
    y_title = sty.StringType(default=None)
    bins = sty.IntType(default=50)
    bar_mode = sty.StringType(validators=[is_bar_mode], default='stack')


class PlotItem(Model):
    '''
    Schematic for a plot.

    Attributes:
        filters (list[dict]): How data is filtered. Default: [].
        group (dict): How data is grouped. Default: {}.
        pivot (dict): How data is pivoted. Default: {}.
        figure (dict): Plot figure details. Default: {}.
        min_width (float): Minimum width of plot. Default: 0.25.
    '''
    filters = sty.ListType(sty.ModelType(FilterAction), default=[])
    group = sty.ModelType(GroupAction)
    pivot = sty.ModelType(PivotAction)
    figure = sty.ModelType(FigureItem, default={})
    min_width = sty.FloatType(default=25, validators=[is_percentage])


class Config(Model):
    '''
    Configuration of database.

    Attributes:
        data_path (str): Path to CSV file.
        columns (list[str]): Columns to be displayed in data.
        default_query (str): Placeholder SQL query string.
        font_family (str): Font family.
        color_scheme (dict): Color scheme.
        conform (lit[dict]): List of conform actions.
        plots (list[dict]): List of plots.
    '''
    data_path = sty.StringType(required=True, validators=[is_csv])
    columns = sty.ListType(sty.StringType, default=[])
    default_query = sty.StringType(default='select * from data')
    font_family = sty.StringType(default='sans-serif, "sans serif"')
    color_scheme = sty.DictType(
        sty.StringType(), validators=[is_color_scheme], default=COLOR_SCHEME
    )
    conform = sty.ListType(sty.ModelType(ConformAction), default=[])
    plots = sty.ListType(sty.ModelType(PlotItem), default=[])
