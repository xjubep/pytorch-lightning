import os
from time import sleep

import pytest
from tests_app import _PROJECT_ROOT

from lightning_app.testing.testing import run_app_in_cloud


@pytest.mark.cloud
def test_drive_example_cloud() -> None:
    with run_app_in_cloud(os.path.join(_PROJECT_ROOT, "examples/app_drive")) as (
        _,
        view_page,
        fetch_logs,
    ):

        has_logs = False
        while not has_logs:
            for log in fetch_logs():
                if "Application End!" in log:
                    has_logs = True
            sleep(1)
