from selenium.webdriver.chrome.options import Options
import lunchbox.tools as lbt
import pytest

import shekels.server.app as app
# ------------------------------------------------------------------------------


def pytest_setup_options():
    options = Options()
    options.add_argument('--no-sandbox')
    # options.add_argument('--disable-gpu')
    # options.binary_location = "/usr/bin/chromium-browser"
    return options


@pytest.fixture
def run_app():
    config_path = lbt \
        .relative_path(__file__, '../resources/test_config.json') \
        .as_posix()
    app.run(app.APP, config_path, debug=True, test=True)
    return app.APP, app.APP.client
