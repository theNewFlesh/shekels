from typing import Any, Dict, List, Tuple, Union

from copy import copy
from pathlib import Path
import json
import os

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash
import dash_core_components as dcc
import dash_table
import flasgger as swg
import flask
import jsoncomment as jsonc

import shekels.core.config as cfg
import shekels.server.api as api
import shekels.server.components as comp
import shekels.server.server_tools as svt
# ------------------------------------------------------------------------------


'''
Shekels app used for displaying and interacting with database.
'''


APP = flask.Flask('$hekels')  # type: Union[flask.Flask, dash.Dash]
swg.Swagger(APP)
APP.register_blueprint(api.API)
APP = comp.get_dash_app(APP)
CONFIG_PATH = None  # type: Union[str, Path, None]


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
    temp = api.CONFIG or {}
    color_scheme = copy(cfg.COLOR_SCHEME)
    cs = temp.get('color_scheme', {})
    color_scheme.update(cs)

    params = dict(
        COLOR_SCHEME=color_scheme,
        FONT_FAMILY=temp.get('font_family', cfg.Config.font_family.default),
    )
    content = svt.render_template('style.css.j2', params)
    return flask.Response(content, mimetype='text/css')


# TOOLS-------------------------------------------------------------------------
def update_store(store, endpoint, data=None):
    client = APP.server.test_client()
    response = None
    try:
        if data is not None:
            response = client.post(endpoint, json=json.dumps(data)).json
        else:
            response = client.post(endpoint).json
    except Exception as error:
        response = svt.error_to_response(error)
    store[endpoint] = response


def store_key_is_valid(store, key):
    if key not in store:
        raise PreventUpdate
    if 'error' in store[key]:
        return False
    return True


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
    store = inputs[-1] or {}  # type: Any
    config = store.get('config', api.CONFIG)  # type: Dict

    input_ = dash.callback_context.triggered[0]
    element = input_['prop_id'].split('.')[0]
    value = input_['value']

    if element == 'query':
        # needed to block input which is called twice on page load
        key = '/api/search/query/count'
        count = store.get(key, 0)
        if count < 2:
            count += 1
            store[key] = count
        else:
            update_store(store, '/api/search', data={'query': value})
            store['/api/search/query'] = value

    elif element == 'init-button':
        update_store(store, '/api/initialize', data=config)

    elif element == 'update-button':
        if api.DATABASE is None:
            update_store(store, '/api/initialize', data=config)
        update_store(store, '/api/update')
        update_store(
            store, '/api/search', data={'query': config['default_query']}
        )

    elif element == 'search-button':
        update_store(store, '/api/search', data={'query': value})
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
            with open(CONFIG_PATH, 'w') as f:  # type: ignore
                json.dump(config.to_primitive(), f, indent=4, sort_keys=True)
        except Exception as error:
            store['/config'] = svt.error_to_response(error).json

    return store


@APP.callback(
    Output('table-content', 'children'),
    [Input('store', 'data')]
)
def on_datatable_update(store):
    # type: (Dict) -> dash_table.DataTable
    '''
    Updates datatable with read information from store.

    Args:
        store (dict): Store data.

    Returns:
        DataTable: Dash DataTable.
    '''
    if not store_key_is_valid(store, '/api/search'):
        return comp.get_key_value_card(
            store['/api/search'], header='error', id_='error'
        )
    return comp.get_datatable(store['/api/search']['response'])


@APP.callback(
    Output('plots-content', 'children'),
    [Input('store', 'data')]
)
def on_plots_update(store):
    # type: (Dict) -> dash_table.DataTable
    '''
    Updates plots with read information from store.

    Args:
        store (dict): Store data.

    Returns:
        list[dcc.Graph]: Plots.
    '''
    if not store_key_is_valid(store, '/api/search'):
        return comp.get_key_value_card(
            store['/api/search'], header='error', id_='error'
        )
    plots = store.get('config', api.CONFIG).get('plots', [])
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
        query = store.get('query', api.CONFIG['default_query'])  # type: ignore
        return comp.get_plots_tab(query)

    elif tab == 'data':
        query = store.get('query', api.CONFIG['default_query'])  # type: ignore
        return comp.get_data_tab(query)

    elif tab == 'config':
        config = store.get('config', api.CONFIG)
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
    if not store_key_is_valid(store, '/config'):
        return comp.get_key_value_card(store['/config'], 'error', 'error')
    return comp.get_key_value_card(store['/config'], 'config', 'config-card')
# ------------------------------------------------------------------------------


if __name__ == '__main__':
    debug = 'DEBUG_MODE' in os.environ.keys()
    temp = None
    if debug:
        CONFIG_PATH = '/root/shekels/resources/config.json'
        with open(CONFIG_PATH) as f:
            temp = jsonc.JsonComment().load(f)
    else:
        CONFIG_PATH = '/mnt/storage/config.json'
        with open(CONFIG_PATH) as f:
            temp = jsonc.JsonComment().load(f)

    temp = cfg.Config(temp)
    temp.validate()
    api.CONFIG = temp.to_primitive()
    APP.run_server(debug=debug, host='0.0.0.0', port=5014)
