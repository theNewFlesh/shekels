from pathlib import Path
import json
import time

import dash
import flask
import flask_caching
import lunchbox.tools as lbt

import shekels.server.api as api
import shekels.server.app as app
# ------------------------------------------------------------------------------


def write_config(root):
    config = dict(
        data_path='/foo/bar.baz',
        columns=['foo', 'bar'],
    )
    config_path = Path(root, 'config.json').as_posix()
    with open(config_path, 'w') as f:
        json.dump(config, f)
    return config_path


def test_get_app(dash_duo):
    result = app.get_app()
    dash_duo.start_server(result)
    assert isinstance(result, dash.Dash)
    assert result.api is api.API
    assert isinstance(result.client, flask.testing.FlaskClient)
    assert isinstance(result.cache, flask_caching.Cache)


def test_solve_component_state():
    # correct
    store = {'/api/initialize': {}, '/api/update': {}, '/api/search': {}}
    result = app.solve_component_state(store)
    assert result is None

    states = {
        '/api/initialize': 'Please call init or update.',
        '/api/update': 'Please call update.',
        '/api/search': None,
    }
    keys = states.keys()
    for key, expected in states.items():
        # missing
        store = dict(zip(keys, [{}] * len(keys)))
        del store[key]
        result = None
        if expected is not None:
            result = app.solve_component_state(store) \
                .children[-1].children[-1].children[0]
        assert result == expected

        # error
        store[key] = {'error': 'foobar'}
        result = app.solve_component_state(store) \
            .children[-1].children[-1].children[0]
        assert result == 'foobar'


def test_run():
    result = app.APP
    config_path = lbt.relative_path(
        __file__, '../../../resources/test_config.json'
    ).as_posix()
    app.run(result, config_path, debug=True, test=True)
    assert result.api.config_path == config_path
    assert isinstance(result.api.config, dict)


def test_stylesheet(dash_duo, run_app):
    test_app, client = run_app
    dash_duo.start_server(test_app)
    result = client.get('/stylesheet/style.css').data.decode('utf-8')
    assert 'static/style.css' in result


# TABS--------------------------------------------------------------------------
def test_plots_update(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # default tab
    result = dash_duo.wait_for_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    # init message
    result = dash_duo.wait_for_element('#action-value').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.04)
    result = dash_duo.wait_for_element('#action-value').text
    assert result == 'Please call update.'

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


def test_datatable_update(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on data tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    dash_duo.wait_for_element('#action-value')
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'table-content'

    # init message
    result = dash_duo.find_element('#action-value').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.04)
    result = dash_duo.wait_for_element('#action-value').text
    assert result == 'Please call update.'

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = dash_duo.find_elements('#datatable td')
    assert len(result) == 680


def test_on_get_tab_config_no_init(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    dash_duo.find_elements('#tabs .tab')[3].click()
    dash_duo.wait_for_element('#config-content > div')
    # dash_duo.take_snapshot('test_on_get_tab_config_no_init-before')
    result = dash_duo.find_element('#config-content > div')
    assert result.get_property('id') == 'key-value-table-container'
