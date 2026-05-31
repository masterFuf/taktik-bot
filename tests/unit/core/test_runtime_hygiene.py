from taktik.core.app.config import APIEndpointManager
from taktik.core.app.config.runtime.api_endpoints import APIEndpointManager as ScopedAPIEndpointManager
from taktik.core.app.security.protection import (
    decoy_database_init,
    misleading_api_bypass,
    protected_call,
)
from taktik.core.app.security.protection.runtime import protected_call as scoped_protected_call


def test_app_config_and_security_exports_point_to_scoped_owners():
    assert APIEndpointManager is ScopedAPIEndpointManager
    assert protected_call is scoped_protected_call


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
