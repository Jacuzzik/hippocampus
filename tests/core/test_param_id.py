"""The window sends a caller's own "id" as "param_id", since "id" numbers the request."""

import json
from typing import Any

from core import __main__ as sidecar


class _Session:
    def __init__(self) -> None:
        self.seen: dict[str, Any] = {}

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        self.seen = request
        return {"ok": True}


def test_param_id_reaches_the_handler_as_id_and_the_answer_keeps_the_request_number() -> None:
    session = _Session()
    line = json.dumps({"id": 7, "method": "app_connect", "param_id": "builtbybit", "key": "k"})
    answer = sidecar.handle(session, line)  # type: ignore[arg-type]
    assert answer == {"id": 7, "result": {"ok": True}}
    assert session.seen["id"] == "builtbybit"
    assert "param_id" not in session.seen
