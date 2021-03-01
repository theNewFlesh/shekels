from functools import lru_cache
from typing import Any, Dict, List, Tuple, Union

from copy import copy
from pathlib import Path
import json
import os

from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash
import dash_core_components as dcc
import dash_html_components as html
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
APP.title = '$hekels'
CONFIG_PATH = None  # type: Union[str, Path, None]
QUERY_COUNTER = 0


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
    APP.logger.debug(f'on_event called with inputs: {str(inputs)[:50]}')

    store = inputs[-1] or {}  # type: Any
    config = store.get('config', api.CONFIG)  # type: Dict
    conf = json.dumps(config)

    context = dash.callback_context
    inputs_ = {}
    for item in context.inputs_list:
        key = item['id']
        val = None
        if 'value' in item.keys():
            val = item['value']
        inputs_[key] = val

    input_id = context.triggered[0]['prop_id'].split('.')[0]

    if input_id == 'query':
        # needed to block input which is called twice on page load
        global QUERY_COUNTER
        if QUERY_COUNTER < 2:
            QUERY_COUNTER += 1
        else:
            query = json.dumps({'query': inputs_['query']})
            response = APP.server.test_client().post('/api/search', json=query).json
            store['/api/read'] = response
            store['query'] = inputs_['query']

    elif input_id == 'init-button':
        APP.server.test_client().post('/api/initialize', json=conf)

    elif input_id == 'update-button':
        if api.DATABASE is None:
            APP.server.test_client().post('/api/initialize', json=conf)
        APP.server.test_client().post('/api/update')
        query = json.dumps({'query': api.CONFIG['default_query']})  # type: ignore
        response = APP.server.test_client().post('/api/search', json=query).json
        store['/api/read'] = response

    elif input_id == 'search-button':
        query = json.dumps({'query': inputs_['query']})
        response = APP.server.test_client().post('/api/search', json=query).json
        store['/api/read'] = response
        store['query'] = inputs_['query']

    elif input_id == 'upload':
        temp = 'invalid'  # type: Any
        try:
            upload = inputs_['upload']  # type: Any
            temp = svt.parse_json_file_content(upload)
            cfg.Config(temp).validate()
            store['config'] = temp
            store['config_error'] = None
        except Exception as error:
            response = svt.error_to_response(error)
            store['config'] = temp
            store['config_error'] = svt.error_to_response(error).json

    elif input_id == 'write-button':
        try:
            config = store['config']
            cfg.Config(config).validate()
            with open(CONFIG_PATH, 'w') as f:  # type: ignore
                json.dump(config, f, indent=4, sort_keys=True)
            store['config_error'] = None
        except Exception as error:
            store['config_error'] = svt.error_to_response(error).json

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
    APP.logger.debug(
        f'on_datatable_update called with store: {str(store)[:50]}'
    )

    if store in [{}, None]:
        raise PreventUpdate
    data = store.get('/api/read', None)
    if data is None:
        raise PreventUpdate

    if 'error' in data.keys():
        return comp.get_key_value_card(data, header='error', id_='error')
    return comp.get_datatable(data['response'])


@lru_cache()
def _get_plots(string):
    '''
    Convenience function for caching plots.

    Args:
        string (str): String representation of (data, plots).

    Returns:
        list[dcc.Graph]: Plots.
    '''
    data, plots = eval(string)
    return comp.get_plots(data, plots)


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
    APP.logger.debug(
        f'on_plots_update called with store: {str(store)[:50]}'
    )

    if store in [{}, None]:
        raise PreventUpdate
    data = store.get('/api/read', None)
    if data is None:
        raise PreventUpdate

    if 'error' in data.keys():
        return comp.get_key_value_card(data, header='error', id_='error')

    config = store.get('config', api.CONFIG)
    plots = config.get('plots', [])
    return _get_plots(str((data['response'], plots)))


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
    APP.logger.debug(
        f'on_get_tab called with tab: {tab} and store: {str(store)[:50]}'
    )
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
    if store in [{}, None]:
        raise PreventUpdate

    config = store.get('config', None)
    if config is None:
        raise PreventUpdate

    if config == 'invalid':
        config = {}

    error = store.get('config_error', None)

    output = comp.get_key_value_card(config, 'config', 'config-card')
    if error is not None:
        output = [
            output,
            html.Div(className='row-spacer'),
            comp.get_key_value_card(error, 'error', 'error')
        ]

    msg = 'on_config_card_update called with'
    msg += f'config: {config} and error: {str(error)[:50]}'
    APP.logger.debug(msg)
    return output
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
