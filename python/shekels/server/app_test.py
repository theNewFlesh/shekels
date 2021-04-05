from pathlib import Path
import json
import os
import time

import dash
import flask
import flask_caching
import lunchbox.tools as lbt
import pytest
import selenium.webdriver.common.keys as sek

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


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_get_app(dash_duo, serial):
    result = app.get_app()
    dash_duo.start_server(result)
    assert isinstance(result, dash.Dash)
    assert result.api is api.API
    assert isinstance(result.client, flask.testing.FlaskClient)
    assert isinstance(result.cache, flask_caching.Cache)


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
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
            result = app \
                .solve_component_state(store).children[-1].data[0]['value']
        assert result == expected

        # error
        store[key] = {
            'error': 'FooBarError',
            'message': 'Not all foos are bars.',
            'code': '500',
            'traceback': 'foobar',
            'args': ['foo', 'bar'],
        }
        result = app \
            .solve_component_state(store).children[-1].data[0]['value']
        assert result == 'FooBarError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_run():
    result = app.APP
    config_path = lbt.relative_path(
        __file__, '../../../resources/test_config.json'
    ).as_posix()
    app.run(result, config_path, debug=True, test=True)
    assert result.api.config_path == config_path
    assert isinstance(result.api.config, dict)


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_stylesheet(dash_duo, run_app, serial):
    test_app, client = run_app
    dash_duo.start_server(test_app)
    result = client.get('/stylesheet/style.css').data.decode('utf-8')
    assert 'static/style.css' in result


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_update_button(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click init button
    dash_duo.wait_for_element('#lower-content div')
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#key-value-table td:last-child > div').text

    # click update button
    dash_duo.find_elements('#update-button')[-1].click()
    dash_duo.wait_for_element('.js-plotly-plot')
    time.sleep(0.01)
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_update_button_no_init(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click update button
    dash_duo.wait_for_element('#lower-content div')
    # dash_duo.take_snapshot('test_on_event_update_button_no_init-0')
    dash_duo.find_elements('#update-button')[-1].click()
    # dash_duo.take_snapshot('test_on_event_update_button_no_init-1')
    dash_duo.wait_for_element('.js-plotly-plot')
    result = dash_duo.find_elements('.dash-graph.plot')
    assert len(result) == 6


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_update_button_no_init_error(dash_duo, run_app, serial):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    # click update button
    dash_duo.wait_for_element('#lower-content div')
    dash_duo.find_elements('#update-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_search_button(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # default tab
    dash_duo.wait_for_element('#lower-content div')
    dash_duo.find_elements('#search-button')[-1].click()
    time.sleep(0.01)

    # init message
    result = dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.04)
    dash_duo.find_elements('#search-button')[-1].click()
    result = dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    assert result == 'Please call update.'

    # click update button
    dash_duo.find_elements('#update-button')[-1].click()
    dash_duo.wait_for_element('.js-plotly-plot')
    # dash_duo.take_snapshot('on_event_search-0')

    # enter new query
    query = dash_duo.find_elements('#query')[-1]
    query.send_keys(sek.Keys.CONTROL + 'a')
    query.send_keys(sek.Keys.BACK_SPACE)
    query.send_keys('select * from data')
    # dash_duo.take_snapshot('on_event_search-1')

    # click search button
    dash_duo.find_elements('#search-button')[-1].click()
    dash_duo.wait_for_element('.js-plotly-plot')
    # dash_duo.take_snapshot('on_event_search-2')
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


# TABS--------------------------------------------------------------------------
@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_plots_update(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # default tab
    result = dash_duo.wait_for_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    # init message
    result = dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.04)
    result = dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    assert result == 'Please call update.'

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_plots_update_error(dash_duo, run_app, serial):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_datatable_update(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on data tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    dash_duo.wait_for_element('#key-value-table')
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'table-content'

    # init message
    result = dash_duo.find_element('#key-value-table td:last-child > div').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.04)
    result = dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    assert result == 'Please call update.'

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = dash_duo.find_elements('#datatable td')
    assert len(result) == 680


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_plots_datatable_error(dash_duo, run_app, serial):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    # click on data tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    dash_duo.wait_for_element('#key-value-table td:last-child > div').text
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_update(dash_duo, run_app, serial):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on config tab
    dash_duo.find_elements('#tabs .tab')[3].click()
    time.sleep(0.1)
    dash_duo.wait_for_element('#config-content')
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'config-content'

    # content
    dash_duo.find_elements('#init-button')[-1].click()
    result = dash_duo.find_elements('#key-value-table tr')
    assert len(result) == 117


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_update_error(dash_duo, run_app, serial):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    # click on config tab and init button
    dash_duo.find_elements('#tabs .tab')[3].click()
    time.sleep(0.1)
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'
