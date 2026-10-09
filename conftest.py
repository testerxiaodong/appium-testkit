"""Load the project's pytest plugin for fixtures and test reporting."""

pytest_plugins = [
    "appium_testkit.pytest_plugin",
    "appium_testkit.mocking.pytest_plugin",
    "apps.kazumi.pytest_plugin",
]
