from filelock import FileLock

from selenium.webdriver.chrome.options import Options
import lunchbox.tools as lbt
import pytest

import shekels.server.app as app
# ------------------------------------------------------------------------------


def pytest_setup_options():
    '''
    Configures Chrome webdriver.
    '''
    options = Options()
    options.add_argument('--no-sandbox')
    # options.add_argument('--disable-gpu')
    # options.binary_location = "/usr/bin/chromium-browser"
    return options


@pytest.fixture
def run_app():
    '''
    Pytest fixture used to run shekels Dash app.
    Sets config_path to resources/test_config.json.
    '''
    config_path = lbt \
        .relative_path(__file__, '../resources/test_config.json') \
        .as_posix()
    app.run(app.APP, config_path, debug=True, test=True)
    return app.APP, app.APP.client


@pytest.fixture(autouse=True)
def serial(request):
    '''
    Pytest fixture that forces decorated tests to run in parallel.

    Code copied from:
    https://github.com/pytest-dev/pytest-xdist/issues/385
    '''
    if request.node.get_closest_marker("sequential"):
        with FileLock("semaphore.lock"):
            yield
    else:
        yield
