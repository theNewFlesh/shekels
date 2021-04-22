from typing import Any, Dict, List, Optional

from copy import copy
import os

from lunchbox.enforce import Enforce, EnforceError
from pandas import DataFrame, DatetimeIndex
from schematics.exceptions import DataError
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import flask
import lunchbox.tools as lbt
import rolling_pin.blob_etl as rpb

import shekels.core.config as cfg
import shekels.core.data_tools as sdt
# ------------------------------------------------------------------------------


# TODO: refactor components tests to use selnium and be less brittle
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

    icon = html.Img(id='icon', src='/assets/icon.svg')
    tabs = dcc.Tabs(
        id='tabs',
        className='tabs',
        value='plots',
        children=[
            dcc.Tab(className='tab', label='plots', value='plots'),
            dcc.Tab(className='tab', label='data', value='data'),
            dcc.Tab(className='tab', label='config', value='config'),
            dcc.Tab(className='tab', label='api', value='api'),
            dcc.Tab(className='tab', label='docs', value='docs'),
            dcc.Tab(className='tab', label='monitor', value='monitor'),
        ],
    )
    tabs = html.Div(id='tabs-container', children=[icon, tabs])

    content = dcc.Loading(
        id="content",
        className='content',
        type="dot",
        fullscreen=True,
    )

    # path to resources inside pip package
    assets = lbt.relative_path(__file__, "../resources")

    # path to resources inside repo
    if 'REPO_ENV' in os.environ.keys():
        assets = lbt.relative_path(__file__, "../../../resources")

    app = dash.Dash(
        name='Shekels',
        title='Shekels',
        server=server,
        external_stylesheets=['/static/style.css'],
        assets_folder=assets,
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
    content = html.Div(id='lower-content', children=[
        html.Div(id='config-content', className='col', children=[
            get_key_value_table(
                config, id_='config', header='config', editable=True
            )
        ])
    ])
    return [*get_dummy_elements(), get_configbar(config), content]


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
    searchbar = html.Div(id='searchbar', className='menubar', children=[row])
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
        dcc.Input(className='dummy', id='config-query', value=None),
        html.Div(className='dummy', children=[dash_table.DataTable(id='config-table')]),
        dcc.Input(className='dummy', id='query', value=None),
        html.Div(className='dummy', id='config-search-button', n_clicks=None),
        html.Div(className='dummy', id='search-button', n_clicks=None),
        html.Div(className='dummy', id='init-button', n_clicks=None),
        html.Div(className='dummy', id='update-button', n_clicks=None),
        dcc.Upload(className='dummy', id='upload', contents=None),
        html.Div(className='dummy', id='save-button', n_clicks=None),
    ]


def get_configbar(config, query='select * from config'):
    # type: (Dict, Optional[str]) -> html.Div
    '''
    Get a row of elements used for configuring Shekels.

    Args:
        config (dict): Configuration to be displayed.
        query (str, optional): Query string. Default: None.

    Returns:
        Div: Div with buttons and JSON editor.
    '''
    spacer = html.Div(className='col spacer')
    query = dcc.Input(
        id='config-query',
        className='col query',
        value=query,
        placeholder='SQL query that uses "FROM config"',
        type='text',
        autoFocus=True,
        debounce=True
    )

    search = get_button('search')
    search.id = 'config-search-button'
    init = get_button('init')
    upload = dcc.Upload(
        id='upload',
        children=[get_button('upload')]
    )
    save = get_button('save')
    row = html.Div(
        className='row',
        children=[
            query, spacer, search, spacer, init, spacer, upload, spacer, save
        ],
    )
    configbar = html.Div(id='configbar', className='menubar', children=[row])
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


def get_key_value_table(
    data, id_='key-value', header='', editable=False, key_order=None
):
    # type (dict, Optional(str), str, bool, Optional(List[str])) -> DataTable
    '''
    Gets a Dash DataTable element representing given dictionary.

    Args:
        data (dict): Dictionary.
        id_ (str, optional): CSS id. Default: 'key-value'.
        header (str, optional): Table header title. Default: ''.
        editable (bool, optional): Whether table is editable. Default: False.
        key_order (list[str], optional): Order in which keys will be displayed.
            Default: None.

    Returns:
        DataTable: Tablular representation of given dictionary.
    '''
    data = rpb.BlobETL(data).to_flat_dict()

    # determine keys
    keys = sorted(list(data.keys()))
    if key_order is not None:
        diff = set(key_order).difference(keys)
        if len(diff) > 0:
            diff = list(sorted(diff))
            msg = f'Invalid key order. Keys not found in data: {diff}.'
            raise KeyError(msg)

        keys = set(keys).difference(key_order)
        keys = sorted(list(keys))
        keys = key_order + keys

    # transform data
    data = [dict(key=k, value=data[k]) for k in keys]

    cols = []  # type: Any
    if len(data) > 0:
        cols = data[0].keys()
    cols = [{'name': x, 'id': x} for x in cols]

    table = dash_table.DataTable(
        data=data,
        data_previous=data,
        columns=cols,
        id=f'{id_}-table',
        sort_action='native',
        sort_mode='multi',
        page_action='none',
        cell_selectable=True,
        editable=editable,
    )
    head = html.Div(className='key-value-table-header', children=header)
    return html.Div(
        id=id_, className='key-value-table-container', children=[head, table]
    )


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

    Returns:
        list[dcc.Graph]: Plots.
    '''
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

        try:
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
        except (DataError, EnforceError):
            fig = html.Div(
                id=f'plot-{i:02d}',
                className='plot plot-error',
                style={'min-width': min_width},
                children=html.Div(
                    className='plot-error-container',
                    children=html.Div(
                        className='plot-error-message',
                        children='no data found'
                    )
                )
            )
        elems.append(fig)
    return elems
