from typing import Any, Dict, List, Tuple, Union

from copy import copy
from copy import deepcopy
from pathlib import Path
import os

from dash.dependencies import Input, Output, State
from flask_caching import Cache
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import flasgger as swg
import flask
import flask_monitoringdashboard as fmdb
import jsoncomment as jsonc

from shekels.server.api import API
import shekels.core.config as cfg
import shekels.server.components as svc
import shekels.server.event_listener as sev
import shekels.server.server_tools as svt
# ------------------------------------------------------------------------------


'''
Shekels app used for displaying and interacting with database.
'''


def get_app():
    # type: () -> dash.Dash
    '''
    Creates a Shekels app.

    Returns:
        Dash: Dash app.
    '''
    flask_app = flask.Flask('Shekels')
    swg.Swagger(flask_app)
    flask_app.register_blueprint(API)

    # flask monitoring
    fmdb.config.link = 'monitor'
    fmdb.config.monitor_level = 3
    fmdb.config.git = 'https://thenewflesh.github.io/shekels/'
    fmdb.bind(flask_app)

    app = svc.get_dash_app(flask_app)
    app.api = API
    app.client = flask_app.test_client()
    app.cache = Cache(flask_app, config={'CACHE_TYPE': 'SimpleCache'})

    # register event listener
    app.event_listener = sev.EventListener(app, {}) \
        .listen('config-query', svt.config_query_event) \
        .listen('config-search-button', svt.config_query_event) \
        .listen('config-table', svt.config_edit_event) \
        .listen('query', svt.data_query_event) \
        .listen('search-button', svt.data_query_event) \
        .listen('init-button', svt.init_event) \
        .listen('update-button', svt.update_event) \
        .listen('upload', svt.upload_event) \
        .listen('save-button', svt.save_event)
    return app


APP = get_app()


@APP.server.route('/static/<stylesheet>')
def serve_stylesheet(stylesheet):
    # type: (str) -> flask.Response
    '''
    Serve stylesheet to app.

    Args:
        stylesheet (str): stylesheet filename.

    Returns:
        flask.Response: Response.
    '''
    temp = APP.api.config or {}
    color_scheme = copy(cfg.COLOR_SCHEME)
    cs = temp.get('color_scheme', {})
    color_scheme.update(cs)

    params = dict(
        COLOR_SCHEME=color_scheme,
        FONT_FAMILY=temp.get('font_family', cfg.Config.font_family.default),
    )
    content = svt.render_template('style.css.j2', params)
    return flask.Response(content, mimetype='text/css')


# EVENTS------------------------------------------------------------------------
@APP.callback(
    Output('store', 'data'),
    [
        Input('config-query', 'value'),
        Input('config-search-button', 'n_clicks'),
        Input('config-table', 'data'),
        Input('query', 'value'),
        Input('init-button', 'n_clicks'),
        Input('update-button', 'n_clicks'),
        Input('search-button', 'n_clicks'),
        Input('upload', 'contents'),
        Input('save-button', 'n_clicks'),
    ],
    [State('config-table', 'data_previous')]
)
def on_event(*inputs):
    # type: (Tuple[Any, ...]) -> Dict[str, Any]
    '''
    Update database instance, and updates store with input data.

    Args:
        inputs (tuple): Input elements.

    Returns:
        dict: Store data.
    '''
    event = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    value = dash.callback_context.triggered[0]['value']
    store = APP.event_listener.store

    if event == 'config-table':
        value = dict(new=value[0], old=inputs[-1][0])

    if event == 'update-button' and store.get('/api/initialize') is None:
        APP.event_listener.emit('init-button', None)
    store = APP.event_listener.emit(event, value).store
    return store


@APP.callback(
    Output('plots-content', 'children'),
    [Input('store', 'data')]
)
@APP.cache.memoize(100)
def on_plots_update(store):
    # type: (Dict) -> dash_table.DataTable
    '''
    Updates plots with read information from store.

    Args:
        store (dict): Store data.

    Returns:
        list[dcc.Graph]: Plots.
    '''
    comp = svt.solve_component_state(store)
    if comp is not None:
        return comp
    config = store.get('/config', deepcopy(APP.api.config))
    plots = config.get('plots', [])
    return svc.get_plots(store['/api/search']['response'], plots)


@APP.callback(
    Output('table-content', 'children'),
    [Input('store', 'data')]
)
@APP.cache.memoize(100)
def on_datatable_update(store):
    # type: (Dict) -> dash_table.DataTable
    '''
    Updates datatable with read information from store.

    Args:
        store (dict): Store data.

    Returns:
        DataTable: Dash DataTable.
    '''
    comp = svt.solve_component_state(store)
    if comp is not None:
        return comp
    return svc.get_datatable(store['/api/search']['response'])


@APP.callback(
    Output('config-content', 'children'),
    [Input('store', 'data')]
)
@APP.cache.memoize(100)
def on_config_update(store):
    # type: (Dict[str, Any]) -> List[flask.Response]
    '''
    Updates config table with config information from store.

    Args:
        store (dict): Store data.

    Returns:
        flask.Response: Response.
    '''
    config = store.get('/config', deepcopy(APP.api.config))
    store['/config'] = config
    store['/config/search'] = store.get('/config/search', store['/config'])
    comp = svt.solve_component_state(store, config=True)
    if comp is not None:
        return [
            comp,
            html.Div(className='dummy', children=[
                dash_table.DataTable(id='config-table')
            ])
        ]
    return svc.get_key_value_table(
        store['/config/search'],
        id_='config',
        header='config',
        editable=True,
    )


@APP.callback(
    Output('content', 'children'),
    [Input('tabs', 'value')],
    [State('store', 'data')]
)
def on_get_tab(tab, store):
    # type: (str, Dict) -> Union[flask.Response, List, None]
    '''
    Serve content for app tabs.

    Args:
        tab (str): Name of tab to render.
        store (dict): Store.

    Returns:
        flask.Response: Response.
    '''
    store = store or {}

    if tab == 'plots':
        query = store.get('/api/search/query', APP.api.config['default_query'])
        return svc.get_plots_tab(query)

    elif tab == 'data':
        query = store.get('/api/search/query', APP.api.config['default_query'])
        return svc.get_data_tab(query)

    elif tab == 'config':
        config = store.get('/config', deepcopy(APP.api.config))
        return svc.get_config_tab(config)

    elif tab == 'api':  # pragma: no cover
        return dcc.Location(id='api', pathname='/api')

    elif tab == 'docs':  # pragma: no cover
        return dcc.Location(
            id='docs',
            href='https://thenewflesh.github.io/shekels/'
        )

    elif tab == 'monitor':  # pragma: no cover
        return dcc.Location(id='monitor', pathname='/monitor')
# ------------------------------------------------------------------------------


def run(app, config_path, debug=False, test=False):
    '''
    Runs a given Shekels app.

    Args:
        Dash: Shekels app.
        config_path (str or Path): Path to configuration JSON.
        debug (bool, optional): Whether debug mode is turned on. Default: False.
        test (bool, optional): Calls app.run_server if False. Default: False.
    '''
    config_path = Path(config_path).as_posix()
    with open(config_path) as f:
        config = jsonc.JsonComment().load(f)
    app.api.config = config
    app.api.config_path = config_path
    app.event_listener.state.clear()
    app.event_listener.state.append({})
    if not test:
        app.run_server(debug=debug, host='0.0.0.0', port=5014)  # pragma: no cover


if __name__ == '__main__':  # pragma: no cover
    run(
        APP,
        '/root/shekels/resources/test_config.json',
        debug='DEBUG_MODE' in os.environ.keys()
    )
