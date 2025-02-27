from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import time

from flask_healthz import HealthError
import dash
import flask
import flask_caching
import jsoncomment as jsonc
import lunchbox.tools as lbt
import pytest
import selenium.webdriver.common.action_chains as sac
import selenium.webdriver.common.keys as sek

import shekels.server.api as api
import shekels.server.app as app
import shekels.server.event_listener as sev
# ------------------------------------------------------------------------------


RESOURCES_DIR = lbt.relative_path(__file__, '../../../resources').as_posix()


def test_liveness():
    app.liveness()


def test_readiness():
    app.readiness()

    api = app.APP.api
    del app.APP.api
    try:
        app.readiness()
    except HealthError as result:
        assert result.args[0] == 'App is missing API.'
    app.APP.api = api


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_get_app(dash_duo):
    result = app.get_app()
    dash_duo.start_server(result)
    assert isinstance(result, dash.Dash)
    assert result.api is api.API
    assert isinstance(result.client, flask.testing.FlaskClient)
    assert isinstance(result.cache, flask_caching.Cache)
    assert isinstance(result.event_listener, sev.EventListener)


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_healthz(dash_duo, run_app):
    test_app, client = run_app
    dash_duo.start_server(test_app)

    # live
    result = client.get('/healthz/live')
    assert result.status_code == 200

    # ready
    result = client.get('/healthz/ready')
    assert result.status_code == 200

    api = test_app.api
    del test_app.api
    result = client.get('/healthz/ready')
    assert result.json == dict(status=503, title='App is missing API.')
    test_app.api = api


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_run():
    result = app.APP
    config_path = Path(RESOURCES_DIR, 'test_config.json').as_posix()
    app.run(result, config_path, debug=True, test=True)
    assert result.api.config_path == config_path
    assert isinstance(result.api.config, dict)


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_stylesheet(dash_duo, run_app):
    test_app, client = run_app
    dash_duo.start_server(test_app)
    result = client.get('/stylesheet/style.css').data.decode('utf-8')
    assert 'static/style.css' in result


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_update_button(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click init button
    dash_duo.wait_for_element('#lower-content div')
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#status-table td:last-child > div')

    # click update button
    dash_duo.find_elements('#update-button')[-1].click()
    dash_duo.wait_for_element('.js-plotly-plot')
    time.sleep(0.03)
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_update_button_no_init(dash_duo, run_app):
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
def test_on_event_update_button_no_init_error(dash_duo, run_app):
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
def test_on_event_search_button(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # default tab
    dash_duo.wait_for_element('#lower-content div')
    dash_duo.find_elements('#search-button')[-1].click()
    time.sleep(0.03)

    # init message
    dash_duo.wait_for_text_to_equal(
        '#status-table td:last-child > div',
        'Please call init or update.',
    )

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.1)
    dash_duo.find_elements('#search-button')[-1].click()
    dash_duo.wait_for_text_to_equal(
        '#status-table td:last-child > div',
        'Please call update.'
    )

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


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_save_button(dash_duo):
    with TemporaryDirectory() as root:
        test_config_path = Path(RESOURCES_DIR, 'test_config.json')
        with open(test_config_path) as f:
            config = jsonc.JsonComment().load(f)

        config['columns'] = ['date']

        config_path = Path(root, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f)

        app.run(app.APP, config_path, debug=True, test=True)
        test_app = app.APP
        dash_duo.start_server(test_app)

        config = test_app.api.config

        # click on config tab
        dash_duo.find_elements('#tabs .tab')[2].click()
        time.sleep(0.1)

        # click init
        dash_duo.find_elements('#init-button')[-1].click()
        time.sleep(0.1)

        # delete config
        os.remove(config_path)

        # save bad config
        dash_duo.find_elements('#save-button')[-1].click()
        time.sleep(0.1)

        assert config_path.is_file()
        with open(config_path) as f:
            result = json.load(f)['columns']
        assert result == ['date']


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_event_save_button_error(dash_duo):
    with TemporaryDirectory() as root:
        test_config_path = Path(RESOURCES_DIR, 'test_config.json')
        with open(test_config_path) as f:
            config = jsonc.JsonComment().load(f)

        config['foo'] = 'bar'

        config_path = Path(root, 'config.json')
        with open(config_path, 'w') as f:
            json.dump(config, f)

        app.run(app.APP, config_path, debug=True, test=True)
        test_app = app.APP
        dash_duo.start_server(test_app)

        config = test_app.api.config

        # click on config tab
        dash_duo.find_elements('#tabs .tab')[2].click()
        time.sleep(0.1)

        # click init
        dash_duo.find_elements('#init-button')[-1].click()
        time.sleep(0.12)

        # delete config
        os.remove(config_path)

        # save bad config
        dash_duo.find_elements('#save-button')[-1].click()
        time.sleep(0.1)

        dash_duo.wait_for_element('#error')
        assert not config_path.is_file()
        result = dash_duo.wait_for_element('#error tr td:last-child > div').text
        assert result == 'DataError'


# TABS--------------------------------------------------------------------------
@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_plots_update(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # default tab
    result = dash_duo.wait_for_element('#lower-content div')
    assert result.get_property('id') == 'plots-content'

    # init message
    dash_duo.wait_for_text_to_equal(
        '#status-table td:last-child > div',
        'Please call init or update.',
    )

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.06)
    dash_duo.wait_for_text_to_equal(
        '#status-table td:last-child > div',
        'Please call update.',
    )

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = len(dash_duo.find_elements('.dash-graph.plot'))
    assert result == 6


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_plots_update_error(dash_duo, run_app):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    dash_duo.wait_for_element('#status-table td:last-child > div')
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_datatable_update(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on data tab
    dash_duo.find_elements('#tabs .tab')[1].click()
    time.sleep(0.1)
    dash_duo.wait_for_element('#status-table')
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'data-content'

    # init message
    result = dash_duo.find_element('#status-table td:last-child > div').text
    assert result == 'Please call init or update.'

    # update message
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.1)
    dash_duo.wait_for_text_to_equal(
        '#status-table td:last-child > div',
        'Please call update.',
    )

    # content
    dash_duo.find_elements('#update-button')[-1].click()
    result = dash_duo.find_elements('#datatable td')
    assert len(result) == 680


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_plots_datatable_error(dash_duo, run_app):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    # click on data tab
    dash_duo.find_elements('#tabs .tab')[1].click()
    time.sleep(1)
    dash_duo.wait_for_element('#status-table td:last-child > div')
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(1)
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_update(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on config tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    time.sleep(0.12)
    dash_duo.wait_for_element('#config-content')
    result = dash_duo.find_element('#lower-content div')
    assert result.get_property('id') == 'config-content'

    # content
    dash_duo.find_elements('#init-button')[-1].click()
    time.sleep(0.1)
    result = dash_duo.find_elements('#config-table tr')
    assert len(result) == 117


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_search(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on config tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    time.sleep(0.1)
    dash_duo.wait_for_element('#config-content', timeout=4)

    # init
    dash_duo.find_elements('#init-button')[-1].click()

    # search
    query = dash_duo.find_elements('#config-query')[-1]
    query.send_keys(sek.Keys.CONTROL + 'a')
    query.send_keys(sek.Keys.BACK_SPACE)
    query.send_keys('select * from config where key ~ color')
    dash_duo.find_elements('#config-search-button')[-1].click()
    time.sleep(0.1)
    result = dash_duo.find_elements('#config-table tr')
    assert len(result) == 38

    # search error
    query = dash_duo.find_elements('#config-query')[-1]
    query.send_keys(sek.Keys.CONTROL + 'a')
    query.send_keys(sek.Keys.BACK_SPACE)
    query.send_keys('select * from config where foo ~ bar')
    dash_duo.find_elements('#config-search-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'KeyError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_update_error(dash_duo, run_app):
    test_app, _ = run_app
    test_app.api.config['columns'] = 99
    dash_duo.start_server(test_app)

    # click on config tab and init button
    dash_duo.find_elements('#tabs .tab')[2].click()
    time.sleep(0.1)
    dash_duo.find_elements('#init-button')[-1].click()
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'


@pytest.mark.skipif('SKIP_SLOW_TESTS' in os.environ, reason='slow test')
def test_on_config_edit(dash_duo, run_app):
    test_app, _ = run_app
    dash_duo.start_server(test_app)

    # click on config tab
    dash_duo.find_elements('#tabs .tab')[2].click()
    time.sleep(0.2)
    dash_duo.wait_for_element('#config-content')

    # init
    dash_duo.find_elements('#init-button')[-1].click()

    # search
    query = dash_duo.find_elements('#config-query')[-1]
    query.send_keys(sek.Keys.CONTROL + 'a')
    query.send_keys(sek.Keys.BACK_SPACE)
    time.sleep(0.1)
    query.send_keys('select * from config where key ~ data_path')
    dash_duo.find_elements('#config-search-button')[-1].click()
    time.sleep(0.1)

    # click cell
    cell = dash_duo.find_element('#config-table tr td.dash-cell.column-1 > div')
    cell.click()

    # enter bad data_path
    sac.ActionChains(dash_duo.driver).send_keys('/a/bad/path' + sek.Keys.ENTER).perform()

    # save
    dash_duo.find_elements('#save-button')[-1].click()
    time.sleep(0.1)

    # data_path error
    dash_duo.wait_for_element('#error')
    result = dash_duo.wait_for_element('#error tr td:last-child > div').text
    assert result == 'DataError'
