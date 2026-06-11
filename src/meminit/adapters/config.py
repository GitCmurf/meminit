"""YAML config adapter implementing ConfigPort."""
from meminit.core.ports.config import ConfigPort
from meminit.core.services.repo_config import load_repo_config, load_repo_layout


class YamlConfigAdapter:
    """Concrete config adapter wrapping YAML-based repo config."""

    def load_repo_layout(self, root_dir: str):
        return load_repo_layout(root_dir)

    def load_repo_config(self, root_dir: str):
        return load_repo_config(root_dir)
