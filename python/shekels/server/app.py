from typing import Any, Dict, List, Tuple, Union

from copy import copy
import json
import os

from dash.dependencies import Input, Output, State
from flask_caching import Cache
import dash
import dash_core_components as dcc
import dash_table
import flasgger as swg
import flask
import jsoncomment as jsonc

import shekels.core.config as cfg
from shekels.server.api import API
import shekels.server.components as comp
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
    flask_app = flask.Flask('$hekels')  # type: Union[flask.Flask, dash.Dash]
    swg.Swagger(flask_app)
    flask_app.register_blueprint(API)
    app = comp.get_dash_app(flask_app)
    app.api = API
    app.client = flask_app.test_client()
    app.cache = Cache(flask_app, config={'CACHE_TYPE': 'SimpleCache'})
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
# TODO: Find a way to test events.
@APP.callback(
    Output('store', 'data'),
    [
        Input('query', 'value'),
        Input('init-button', 'n_clicks'),
        Input('update-button', 'n_clicks'),
        Input('search-button', 'n_clicks'),
        Input('query', 'value'),
        Input('upload', 'contents'),
        Input('write-button', 'n_clicks'),
    ],
    [State('store', 'data')]
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
    store = inputs[-1] or {'/api/search/query/count': 0}  # type: Any
    config = store.get('config', APP.api.config)  # type: Dict

    input_ = dash.callback_context.triggered[0]
    element = input_['prop_id'].split('.')[0]
    value = input_['value']

    if element == 'query':
        # needed to block input which is called twice on page load
        key = '/api/search/query/count'
        if store[key] < 1:
            store[key] += 1
        else:
            svt.update_store(
                APP.client, store, '/api/search', data={'query': value}
            )
            store['/api/search/query'] = value

    elif element == 'init-button':
        svt.update_store(APP.client, store, '/api/initialize', data=config)

    elif element == 'update-button':
        if APP.api.database is None:
            svt.update_store(APP.client, store, '/api/initialize', data=config)
        svt.update_store(APP.client, store, '/api/update')
        svt.update_store(
            APP.client,
            store,
            '/api/search',
            data={'query': config['default_query']}
        )

    elif element == 'search-button':
        svt.update_store(APP.client, store, '/api/search', data={'query': value})
        store['/api/search/query'] = value

    elif element == 'upload':
        try:
            config = svt.parse_json_file_content(value)
            config = cfg.Config(config)
            config.validate()
            store['/config'] = config.to_primitive()
        except Exception as error:
            store['/config'] = svt.error_to_response(error).json

    elif element == 'write-button':
        try:
            config = store['/config']
            config = cfg.Config(config)
            config.validate()
            with open(APP.api.config_path, 'w') as f:  # type: ignore
                json.dump(config.to_primitive(), f, indent=4, sort_keys=True)
        except Exception as error:
            store['/config'] = svt.error_to_response(error).json

    return store


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
    if not svt.store_key_is_valid(store, '/api/search'):
        return comp.get_key_value_card(
            store['/api/search'], header='error', id_='error'
        )
    return comp.get_datatable(store['/api/search']['response'])


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
    if not svt.store_key_is_valid(store, '/api/search'):
        return comp.get_key_value_card(
            store['/api/search'], header='error', id_='error'
        )
    plots = store.get('config', APP.api.config).get('plots', [])
    return comp.get_plots(store['/api/search']['response'], plots)


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
        query = store.get('query', APP.api.config['default_query'])  # type: ignore
        return comp.get_plots_tab(query)

    elif tab == 'data':
        query = store.get('query', APP.api.config['default_query'])  # type: ignore
        return comp.get_data_tab(query)

    elif tab == 'config':
        config = store.get('config', APP.api.config)
        return comp.get_config_tab(config)

    elif tab == 'api':
        return dcc.Location(id='api', pathname='/api')

    elif tab == 'docs':
        return dcc.Location(
            id='docs',
            href='https://thenewflesh.github.io/shekels/'
        )


@APP.callback(
    Output('config-content', 'children'),
    [Input('store', 'modified_timestamp')],
    [State('store', 'data')]
)
@APP.cache.memoize(100)
def on_config_card_update(timestamp, store):
    # type: (int, Dict[str, Any]) -> flask.Response
    '''
    Updates config card with config information from store.

    Args:
        timestamp (int): Store modification timestamp.
        store (dict): Store data.

    Returns:
        flask.Response: Response.
    '''
    if not svt.store_key_is_valid(store, '/config'):
        return comp.get_key_value_card(store['/config'], 'error', 'error')
    return comp.get_key_value_card(store['/config'], 'config', 'config-card')
# ------------------------------------------------------------------------------


def run(app, config_path, debug=False):
    '''
    Runs a given Shekels app.

    Args:
        Dash: Shekels app.
        config_path (str): Path to configuration JSON.
        debug (bool, optional): Whether debug mode is turned on. Default: False.
    '''
    with open(config_path) as f:
        config = jsonc.JsonComment().load(f)
    app.api.config = config
    app.api.config_path = config_path
    app.run_server(debug=debug, host='0.0.0.0', port=5014)


if __name__ == '__main__':
    run(
        APP,
        '/root/shekels/resources/test_config.json',
        debug='DEBUG_MODE' in os.environ.keys()
    )
