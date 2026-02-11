from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class XdgPaths:
    config_home: Path
    data_home: Path

    @property
    def meminit_config_dir(self) -> Path:
        return self.config_home / "meminit"

    @property
    def meminit_data_dir(self) -> Path:
        return self.data_home / "meminit"


def get_xdg_paths(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> XdgPaths:
    """
    Resolve XDG base directories.

    Defaults:
    - XDG_CONFIG_HOME: ~/.config
    - XDG_DATA_HOME: ~/.local/share
    """

    env = env or os.environ
    home = home or Path.home()

    config_home = Path(env.get("XDG_CONFIG_HOME") or (home / ".config")).expanduser()
    data_home = Path(env.get("XDG_DATA_HOME") or (home / ".local" / "share")).expanduser()
    return XdgPaths(config_home=config_home, data_home=data_home)

