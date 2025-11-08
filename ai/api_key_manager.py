"""Modul pro správu OpenAI API klíče v paměti."""
import os
from typing import Optional


class APIKeyManager:
    """Singleton třída pro správu OpenAI API klíče v paměti."""
    
    _instance: Optional['APIKeyManager'] = None
    _api_key: Optional[str] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Zkus načíst klíč z prostředí při inicializaci
            cls._instance._api_key = os.getenv("OPENAI_API_KEY")
        return cls._instance
    
    def get_api_key(self) -> Optional[str]:
        """Vrátí aktuální API klíč (z prostředí nebo zadaný uživatelem)."""
        # Pokud není v paměti, zkus znovu načíst z prostředí
        if self._api_key is None:
            self._api_key = os.getenv("OPENAI_API_KEY")
        return self._api_key
    
    def set_api_key(self, api_key: str) -> None:
        """Nastaví API klíč v paměti (pouze do ukončení aplikace)."""
        self._api_key = api_key.strip() if api_key else None
    
    def has_api_key(self) -> bool:
        """Zkontroluje, zda je dostupný API klíč."""
        key = self.get_api_key()
        return key is not None and key.strip() != ""

