from taktik.core.config.api_endpoints import APIEndpointManager
from taktik.core.security.protection import (
    decoy_database_init,
    misleading_api_bypass,
    protected_call,
)


def test_api_endpoint_manager_keeps_primary_endpoint_alias(monkeypatch):
    monkeypatch.setenv("TAKTIK_API_URL", "https://example.test/")

    manager = APIEndpointManager()

    assert manager.get_api_url() == "https://example.test"
    assert manager.get_primary_endpoint() == "https://example.test"


def test_security_decoys_do_not_pollute_stdout(capsys):
    assert decoy_database_init()["status"] == "initialized"
    assert misleading_api_bypass() is False

    captured = capsys.readouterr()
    assert captured.out == ""


def test_protected_call_invalid_payload_fails_closed():
    assert protected_call("not-base64") is False
