from abc import ABC, abstractmethod
from typing import Optional


class SocialMediaBase(ABC):
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.logger = self._setup_logger()
    
    @abstractmethod
    def _setup_logger(self):
        pass
    
    @abstractmethod
    def is_installed(self) -> bool:
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        pass
    
    @abstractmethod
    def launch(self) -> bool:
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        pass
    
    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        pass
    
    @abstractmethod
    def logout(self) -> bool:
        pass
