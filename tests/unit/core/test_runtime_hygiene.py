from taktik.core.app.config import APIEndpointManager
from taktik.core.app.config.runtime.api_endpoints import APIEndpointManager as ScopedAPIEndpointManager


def test_app_config_exports_point_to_scoped_owners():
    assert APIEndpointManager is ScopedAPIEndpointManager


def test_api_endpoint_manager_keeps_primary_endpoint_alias(monkeypatch):
    monkeypatch.setenv("TAKTIK_API_URL", "https://example.test/")

    manager = APIEndpointManager()

    assert manager.get_api_url() == "https://example.test"
    assert manager.get_primary_endpoint() == "https://example.test"
