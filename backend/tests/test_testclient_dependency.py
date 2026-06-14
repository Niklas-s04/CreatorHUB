from __future__ import annotations

import starlette.testclient as testclient


def test_starlette_testclient_uses_httpx2_backend() -> None:
    assert testclient.httpx.__name__ == "httpx2"
