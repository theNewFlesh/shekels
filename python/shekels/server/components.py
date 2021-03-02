from typing import Any, Dict, List, Optional

from copy import copy
import re

from lunchbox.enforce import Enforce
from pandas import DataFrame, DatetimeIndex
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import flask
import rolling_pin.blob_etl as rpb

import shekels.core.config as cfg
import shekels.core.data_tools as sdt


# TODO: add JSON editor component for config
# APP---------------------------------------------------------------------------
def get_dash_app(server, storage_type='memory'):
    # type: (flask.Flask, str) -> dash.Dash
    '''
    Generate Dash Flask app instance.

    Args:
        server (Flask): Flask instance.
        storage_type (str): Storage type (used for testing). Default: memory.

    Returns:
        Dash: Dash app instance.
    '''

    store = dcc.Store(id='store', storage_type=storage_type)

    tabs = dcc.Tabs(
        id='tabs',
        className='tabs',
        value='plots',
        children=[
            dcc.Tab(
                id='logo',
                className='tab',
                label='$HEKELS',
                value='',
                disabled=True
            ),
            dcc.Tab(className='tab', label='plots', value='plots'),
            dcc.Tab(className='tab', label='data', value='data'),
            dcc.Tab(className='tab', label='config', value='config'),
            dcc.Tab(className='tab', label='api', value='api'),
            dcc.Tab(className='tab', label='docs', value='docs')
        ],
    )
    content = dcc.Loading(
        id="content",
        className='content',
        type="dot",
        fullscreen=True,
    )

    app = dash.Dash(
        __name__,
        server=server,
        external_stylesheets=['http://0.0.0.0:5014/static/style.css'],
    )
    app.layout = html.Div(id='layout', children=[store, tabs, content])
    app.config['suppress_callback_exceptions'] = True

    return app


# TABS--------------------------------------------------------------------------
def get_data_tab(query=None):
    # type: (Optional[str]) -> List
    '''
    Get tab element for Shekels data.

    Args:
        query (str, optional): Query string. Default: None.

    Return:
        list: List of elements for data tab.
    '''
    # dummies must go first for element props behavior to work
    content = html.Div(id='lower-content', children=[
        html.Div(id='table-content', className='col', children=[])
    ])
    return [*get_dummy_elements(), get_searchbar(query), content]


def get_plots_tab(query=None):
    # type: (Optional[str]) -> List
    '''
    Get tab element for Shekels plots.

    Args:
        query (str, optional): Query string. Default: None.

    Return:
        list: List of elements for plots tab.
    '''
    # dummies must go first for element props behavior to work
    content = html.Div(id='lower-content', children=[
        html.Div(id='plots-content', className='col', children=[
            dcc.Loading(id="progress-bar", type="circle")
        ])
    ])
    return [*get_dummy_elements(), get_searchbar(query), content]


def get_config_tab(config):
    # type: (Dict) -> List
    '''
    Get tab element for Shekels config.

    Args:
        config (dict): Configuration to be displayed.

    Return:
        list: List of elements for config tab.
    '''
    # dummies must go first for element props behavior to work
    return [*get_dummy_elements(), get_configbar(config)]


# MENUBARS----------------------------------------------------------------------
def get_searchbar(query=None):
    # type: (Optional[str]) -> html.Div
    '''
    Get a row of elements used for querying Shekels data.

    Args:
        query (str, optional): Query string. Default: None.

    Returns:
        Div: Div with query field and buttons.
    '''
    if query is None:
        query = 'select * from data'

    spacer = html.Div(className='col spacer')
    query = dcc.Input(
        id='query',
        className='col query',
        value=query,
        placeholder='SQL query that uses "FROM data"',
        type='text',
        autoFocus=True,
        debounce=True
    )

    search = get_button('search')
    init = get_button('init')
    update = get_button('update')

    row = html.Div(
        className='row',
        children=[query, spacer, search, spacer, init, spacer, update],
    )
    searchbar = html.Div(
        id='searchbar', className='menubar', children=[row]
    )
    return searchbar


def get_dummy_elements():
    # type: () -> List
    '''
    Returns a list of all elements with callbacks so that the client will not
    throw errors in each tab.

    Returns:
        list: List of html elements.
    '''
    return [
        dcc.Input(className='dummy', id='query', value=None),
        html.Div(className='dummy', id='search-button', n_clicks=None),
        html.Div(className='dummy', id='init-button', n_clicks=None),
        html.Div(className='dummy', id='update-button', n_clicks=None),
        dcc.Upload(className='dummy', id='upload', contents=None),
        html.Div(className='dummy', id='write-button', n_clicks=None),
    ]


def get_configbar(config):
    # type: (Dict) -> html.Div
    '''
    Get a row of elements used for configuring Shekels.

    Args:
        config (dict): Configuration to be displayed.

    Returns:
        Div: Div with buttons and JSON editor.
    '''
    expander = html.Div(className='col expander')
    spacer = html.Div(className='col spacer')

    upload = dcc.Upload(
        id='upload',
        children=[get_button('upload')]
    )
    write = get_button('write')

    rows = [
        html.Div(
            className='row',
            children=[expander, spacer, upload, spacer, write],
        ),
        html.Div(className='row-spacer'),
        html.Div(id='config-content', children=[get_key_value_table(config)])
    ]
    configbar = html.Div(id='configbar', className='menubar', children=rows)
    return configbar


# ELEMENTS----------------------------------------------------------------------
def get_button(title):
    # type: (str) -> html.Button
    '''
    Get a html button with a given title.

    Args:
        title (str): Title of button.

    Raises:
        TypeError: If title is not a string.

    Returns:
        Button: Button element.
    '''
    if not isinstance(title, str):
        msg = f'{title} is not a string.'
        raise TypeError(msg)
    return html.Button(id=f'{title}-button', children=[title], n_clicks=0)


def get_key_value_card(data, header=None, id_='key-value-card'):
    # type: (Dict, Optional[str], str) -> html.Div
    '''
    Creates a key-value card using the keys and values from the given data.
    One key-value pair per row.

    Args:
        data (dict): Dictionary to be represented.
        header (str, optional): Name of header. Default: None.
        id_ (str): Name of id property. Default: "key-value-card".

    Returns:
        Div: Card with key-value child elements.
    '''
    data = rpb.BlobETL(data)\
        .set(
            predicate=lambda k, v: re.search(r'<list_\d', k),
            key_setter=lambda k, v: re.sub('<list_|>', '', k))\
        .to_flat_dict()

    children = []  # type: List[Any]
    if header is not None:
        header = html.Div(
            id=f'{id_}-header',
            className='key-value-card-header',
            children=[str(header)]
        )
        children.append(header)

    for i, (k, v) in enumerate(sorted(data.items())):
        even = i % 2 == 0
        klass = 'odd'
        if even:
            klass = 'even'

        key = html.Div(
            id=f'{k}-key', className='key-value-card-key', children=[str(k)]
        )
        sep = html.Div(className='key-value-card-separator')
        val = html.Div(
            id=f'{k}-value', className='key-value-card-value', children=[str(v)]
        )

        row = html.Div(
            id=f'{id_}-row',
            className=f'key-value-card-row {klass}',
            children=[key, sep, val]
        )
        children.append(row)
    children[-1].className += ' last'

    card = html.Div(
        id=f'{id_}',
        className='key-value-card',
        children=children
    )
    return card


def get_key_value_table(data, color_scheme=cfg.COLOR_SCHEME, editable=True):
    '''
    Gets a Dash DataTable element representing given dictionary.

    Args:
        data (dict): Dictionary.
        color_scheme (dict, optional): Color scheme dictionary.
            Default: COLOR_SCHEME.
        editable (bool, optional): Whether table is editable. Default: False.

    Returns:
        DataTable: Table of data.w
    '''
    cs = copy(cfg.COLOR_SCHEME)
    cs.update(color_scheme)

    data = rpb.BlobETL(data).to_flat_dict()
    data = [dict(key=k, value=v) for k, v in sorted(data.items())]

    cols = []  # type: Any
    if len(data) > 0:
        cols = data[0].keys()
    cols = [{'name': x, 'id': x} for x in cols]

    table = dash_table.DataTable(
        data=data,
        columns=cols,
        id='key-value-table',
        sort_action='native',
        sort_mode='multi',
        cell_selectable=editable,
        editable=editable,
    )
    header = html.Div(id='key-value-table-header', children='config')
    return html.Div(id='key-value-table-container', children=[header, table])


def get_datatable(data, color_scheme=cfg.COLOR_SCHEME, editable=False):
    # type: (List[Dict], Dict[str, str], bool) -> dash_table.DataTable
    '''
    Gets a Dash DataTable element using given data.
    Assumes dict element has all columns of table as keys.

    Args:
        data (list[dict]): List of dicts.
        color_scheme (dict, optional): Color scheme dictionary.
            Default: COLOR_SCHEME.
        editable (bool, optional): Whether table is editable. Default: False.

    Returns:
        DataTable: Table of data.
    '''
    cs = copy(cfg.COLOR_SCHEME)
    cs.update(color_scheme)

    cols = []  # type: Any
    if len(data) > 0:
        cols = data[0].keys()
    cols = [{'name': x, 'id': x} for x in cols]

    return dash_table.DataTable(
        data=data,
        columns=cols,
        id='datatable',
        fixed_rows=dict(headers=True),
        sort_action='native',
        sort_mode='multi',
        cell_selectable=editable,
        editable=editable,
    )


def get_plots(data, plots):
    # type: (List[dict], List[dict]) -> List[dcc.Graph]
    '''
    Gets a Dash plots using given dicts.
    Assumes dict element has all columns of table as keys.

    Args:
        data (list[dict]): List of dicts defining data.
        plots (list[dict]): List of dicts defining plots.

    Raises:
        EnforceError: If data is not a list of dicts.
        EnforceError: If plots is not a list of dicts.
        DataError: If invalid plot found in plots.

    Returns:
        list[dcc.Graph]: Plots.
    '''
    # TODO: add support for plot errors
    msg = 'Data must be a list of dictionaries. Given value: {a}.'
    Enforce(data, 'instance of', list, message=msg)
    for item in data:
        Enforce(item, 'instance of', dict, message=msg)

    msg = 'Plots must be a list of dictionaries. Given value: {a}.'
    Enforce(plots, 'instance of', list, message=msg)
    for item in plots:
        Enforce(item, 'instance of', dict, message=msg)
    # --------------------------------------------------------------------------

    data_ = DataFrame(data)
    if 'date' in data_.columns:
        data_.date = DatetimeIndex(data_.date)

    elems = []
    for i, x in enumerate(plots):
        plot = cfg.PlotItem(x)
        plot.validate()
        plot = plot.to_primitive()
        min_width = str(plot['min_width']) + '%'

        fig = sdt.get_figure(
            data_,
            filters=plot['filters'],
            group=plot['group'],
            pivot=plot['pivot'],
            **plot['figure'],
        )
        fig = dcc.Graph(
            id=f'plot-{i:02d}',
            className='plot',
            figure=fig,
            style={'min-width': min_width},
        )
        elems.append(fig)
    return elems
