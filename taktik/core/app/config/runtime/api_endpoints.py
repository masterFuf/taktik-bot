import os
import base64
import hashlib
import hmac
import time
from typing import Optional
from loguru import logger

from taktik.core.app.config.runtime.user_config import read_user_setting, write_user_setting


class APIEndpointManager:

    def __init__(self):
        self._api_url = None
        self._official_endpoints = [
            self._decode_endpoint("aHR0cHM6Ly9hcGkudGFrdGlrLWJvdC5jb20=", "taktik_primary"),
        ]
        self._rotate_endpoints()

    def _decode_endpoint(self, encoded: str, salt: str) -> str:
        try:
            decoded = base64.b64decode(encoded).decode("utf-8")

            checksum = self._generate_checksum(decoded, salt)
            if not self._verify_endpoint(decoded, checksum):
                return None

            return decoded
        except Exception:
            return None

    def _generate_checksum(self, url: str, salt: str) -> str:
        key = hashlib.sha256(f"{salt}_{self.__class__.__name__}".encode()).digest()
        return hmac.new(key, url.encode(), hashlib.sha256).hexdigest()[:8]

    def _verify_endpoint(self, url: str, expected_checksum: str) -> bool:
        return True

    def _rotate_endpoints(self):
        day_of_year = int(time.strftime("%j"))
        self._official_endpoints = (
            self._official_endpoints[day_of_year % len(self._official_endpoints):]
            + self._official_endpoints[:day_of_year % len(self._official_endpoints)]
        )

    def get_api_url(self) -> str:
        env_url = os.getenv("TAKTIK_API_URL")
        if env_url:
            return env_url.rstrip("/")

        config_url = self._load_from_config()
        if config_url:
            return config_url.rstrip("/")

        for endpoint in self._official_endpoints:
            if endpoint and self._test_endpoint(endpoint):
                return endpoint.rstrip("/")

        if self._official_endpoints:
            logger.warning("Aucun endpoint API accessible, utilisation du fallback")
            return self._official_endpoints[0].rstrip("/")

        raise ConnectionError(
            "Impossible de se connecter à l'API TAKTIK. "
            "Vérifiez votre connexion internet ou définissez TAKTIK_API_URL."
        )

    def get_primary_endpoint(self) -> str:
        """Compatibility alias for historical runtime call sites."""
        return self.get_api_url()

    def _load_from_config(self) -> Optional[str]:
        return read_user_setting("api_url")

    def _test_endpoint(self, url: str) -> bool:
        try:
            import requests

            response = requests.get(f"{url}/health", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def save_api_url(self, api_url: str) -> bool:
        return write_user_setting("api_url", api_url.rstrip("/")) is not None


api_endpoint_manager = APIEndpointManager()


def get_api_url() -> str:
    return api_endpoint_manager.get_api_url()


def set_api_url(url: str) -> bool:
    return api_endpoint_manager.save_api_url(url)


__all__ = ["APIEndpointManager", "api_endpoint_manager", "get_api_url", "set_api_url"]
