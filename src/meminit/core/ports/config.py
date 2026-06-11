"""Config port for repository configuration loading."""
from typing import Protocol

from meminit.core.services.repo_config import RepoConfig, RepoLayout


class ConfigPort(Protocol):
    """Protocol for loading repository configuration."""

    def load_repo_layout(self, root_dir: str) -> RepoLayout:
        """Load the repository layout configuration."""
        ...

    def load_repo_config(self, root_dir: str) -> RepoConfig:
        """Load the repository configuration for the default namespace."""
        ...
