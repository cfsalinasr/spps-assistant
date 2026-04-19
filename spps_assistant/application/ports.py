"""Abstract port interfaces for infrastructure adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatabaseRepository(ABC):
    """Abstract interface for the SPPS residue and synthesis database."""

    @abstractmethod
    def save_residue(
        self,
        token: str,
        base_code: str,
        protection: str,
        fmoc_mw: float,
        free_mw: float,
        stock_conc: float = 0.5,
        notes: str = '',
    ) -> None:
        """Persist residue MW record."""

    @abstractmethod
    def get_residue(self, token: str):
        """Retrieve ResidueInfo by token string. Returns None if not found."""

    @abstractmethod
    def list_residues(self) -> List[Dict[str, Any]]:
        """Return all residue records as list of dicts."""

    @abstractmethod
    def save_default(self, key: str, value: str) -> None:
        """Persist a synthesis default key-value pair."""

    @abstractmethod
    def get_default(self, key: str) -> Optional[str]:
        """Retrieve synthesis default value by key."""

    @abstractmethod
    def log_synthesis(self, synthesis_name: str, metadata: Dict[str, Any]) -> None:
        """Log a synthesis run to the history."""

    @abstractmethod
    def export_csv(self, path: Path) -> None:
        """Export residue library to CSV file."""

    @abstractmethod
    def import_csv(self, path: Path) -> int:
        """Import residue library from CSV file. Returns number of rows imported."""

    @abstractmethod
    def reset(self) -> None:
        """Drop and recreate all tables (dangerous — for dev/reset only)."""


class ConfigRepository(ABC):
    """Abstract interface for the SPPS configuration store."""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load and return the full config as a dict."""

    @abstractmethod
    def save(self, config_dict: Dict[str, Any]) -> None:
        """Persist the full config dict."""

    @abstractmethod
    def get_field(self, field: str) -> Any:
        """Get a single config field value by name."""

    @abstractmethod
    def set_field(self, field: str, value: Any) -> None:
        """Set a single config field and persist."""
