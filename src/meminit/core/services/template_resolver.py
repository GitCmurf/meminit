"""Template resolution service for Meminit Templates v2.

This module provides the TemplateResolver class which implements the
deterministic precedence chain for template resolution:

    config → convention → builtin → skeleton

See PRD-006 for detailed specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Final, Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.repo_config import RepoConfig

# Constants for template sources
SOURCE_CONFIG: Final = "config"
SOURCE_CONVENTION: Final = "convention"
SOURCE_BUILTIN: Final = "builtin"
SOURCE_NONE: Final = "none"

# Template file size limit (256 KiB)
_MAX_TEMPLATE_SIZE: Final = 256 * 1024

# Template file extension
_TEMPLATE_EXTENSION: Final = ".md"

# Convention directory path
_CONVENTION_DIR: Final = "00-governance/templates"


@dataclass(frozen=True)
class TemplateResolution:
    """Result of template resolution.

    Attributes:
        source: Where the template was resolved from - one of:
            "config" - Explicitly configured in document_types
            "convention" - Found via convention (<type>.template.md)
            "builtin" - Package built-in template
            "none" - No template found (will use skeleton)
        path: The filesystem path to the template, or None for builtin/skeleton.
        content: The template content as a string, or None if not found.
    """
    source: str
    path: Optional[Path]
    content: Optional[str]


class TemplateResolver:
    """Resolves template content using the precedence chain.

    The resolver follows this deterministic order:
    1. Config - Explicit template path in document_types.<type>.template
    2. Convention - docs/00-governance/templates/<type>.template.md
    3. Built-in - Package asset templates
    4. None - Returns None for skeleton generation

    All templates are validated for security (FR-10):
    - Must be a regular .md file
    - Must be UTF-8 encoded
    - Must not exceed 256 KiB size
    - Config paths must resolve under repo root
    - Convention paths must resolve under docs/00-governance/templates/
    """

    def __init__(self, repo_config: RepoConfig) -> None:
        """Initialize the resolver with repository configuration.

        Args:
            repo_config: The repository configuration for template resolution.
        """
        self.config = repo_config
        self._repo_root = repo_config.root_dir

    def resolve(self, doc_type: str) -> TemplateResolution:
        """Resolve template for a document type.

        Follows the precedence chain: config → convention → builtin → skeleton.

        Args:
            doc_type: The document type to resolve (case-insensitive).

        Returns:
            A TemplateResolution object containing the source, path, and content.
        """
        # 1. Config (explicit template in document_types)
        config_template = self._resolve_from_config(doc_type)
        if config_template:
            return config_template

        # 2. Convention (<type>.template.md in templates directory)
        convention_template = self._resolve_from_convention(doc_type)
        if convention_template:
            return convention_template

        # 3. Built-in (package assets)
        builtin_template = self._resolve_from_builtin(doc_type)
        if builtin_template:
            return builtin_template

        # 4. None (will use skeleton)
        return TemplateResolution(source=SOURCE_NONE, path=None, content=None)

    def _resolve_from_config(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check config for explicit template path.

        Returns the template if configured and the file exists.
        """
        template_path = self.config.get_template_for_type(doc_type)
        if template_path:
            full_path = self._repo_root / template_path

            # Verify path containment (must be under repo root)
            try:
                resolved_full = full_path.resolve()
                repo_root_resolved = self._repo_root.resolve()
                resolved_full.relative_to(repo_root_resolved)
            except (ValueError, OSError):
                # Path escapes repo root
                return None

            if full_path.exists():
                self._validate_template_file(full_path, allow_root=True)
                # Read content after validation to avoid duplicate reads
                content = full_path.read_text(encoding="utf-8")
                return TemplateResolution(
                    source=SOURCE_CONFIG,
                    path=full_path,
                    content=content
                )
        return None

    def _resolve_from_convention(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check convention paths for templates.

        Looks for <type>.template.md in docs/00-governance/templates/.
        Type lookup is case-insensitive.
        """
        type_key = doc_type.lower()
        new_path = self.config.docs_dir / _CONVENTION_DIR / f"{type_key}.template.md"
        if new_path.exists():
            self._validate_template_file(new_path, allow_root=False)
            # Read content after validation to avoid duplicate reads
            content = new_path.read_text(encoding="utf-8")
            return TemplateResolution(
                source=SOURCE_CONVENTION,
                path=new_path,
                content=content
            )
        return None

    def _resolve_from_builtin(self, doc_type: str) -> Optional[TemplateResolution]:
        """Check built-in package templates.

        Loads templates from the package assets. Returns None if not found.
        """
        type_key = doc_type.lower()
        try:
            template_content = files("meminit.core.assets.org_profiles.default.templates").joinpath(
                f"{type_key}.template.md"
            ).read_text(encoding="utf-8")
            return TemplateResolution(
                source=SOURCE_BUILTIN,
                path=None,  # Built-in has no filesystem path
                content=template_content
            )
        except (FileNotFoundError, AttributeError):
            # AttributeError for cases where files() doesn't support joinpath
            return None

    def _validate_template_file(
        self,
        path: Path,
        *,
        allow_root: bool = False
    ) -> None:
        """Validate template file characteristics (FR-10, FR-17).

        Security checks:
        - Must be a regular file (not a directory, symlink, device, etc.)
        - Must have .md extension
        - Must not exceed 256 KiB size
        - Must be valid UTF-8
        - If allow_root=False, must be under docs/00-governance/templates/

        Args:
            path: The template file path to validate.
            allow_root: If True, allow templates anywhere under repo root.
                If False, only allow under docs/00-governance/templates/.

        Raises:
            MeminitError: With INVALID_TEMPLATE_FILE if validation fails.
        """
        # Check it's a regular file (no symlinks, devices, etc.)
        if path.is_symlink():
            raise MeminitError(
                code=ErrorCode.INVALID_TEMPLATE_FILE,
                message=f"Template is a symbolic link (not allowed): {path.relative_to(self._repo_root)}",
                details={"file_type": "symlink", "path": str(path)}
            )
        if not path.is_file():
            raise MeminitError(
                code=ErrorCode.INVALID_TEMPLATE_FILE,
                message=f"Template path is not a regular file: {path.relative_to(self._repo_root)}",
                details={"file_type": "non_regular", "path": str(path)}
            )

        # Check extension
        if path.suffix != _TEMPLATE_EXTENSION:
            raise MeminitError(
                code=ErrorCode.INVALID_TEMPLATE_FILE,
                message=f"Template must be a .md file: {path.relative_to(self._repo_root)}",
                details={"actual_extension": path.suffix, "path": str(path)}
            )

        # Check size (256 KiB cap)
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise MeminitError(
                code=ErrorCode.INVALID_TEMPLATE_FILE,
                message=f"Template file is inaccessible: {path.relative_to(self._repo_root)}",
                details={"error": str(exc), "path": str(path)}
            )

        if size > _MAX_TEMPLATE_SIZE:
            raise MeminitError(
                code=ErrorCode.INVALID_TEMPLATE_FILE,
                message=f"Template exceeds size limit ({_MAX_TEMPLATE_SIZE / 1024} KiB): {path.relative_to(self._repo_root)}",
                details={"actual_size": size, "max_size": _MAX_TEMPLATE_SIZE, "path": str(path)}
            )

        # For convention-discovered templates, ensure they're under the templates directory
        if not allow_root:
            try:
                rel_to_docs = path.relative_to(self.config.docs_dir)
                parts = rel_to_docs.parts
                # Must be under docs/00-governance/templates/
                if len(parts) < 3 or parts[0] != _CONVENTION_DIR.split('/')[0] or parts[1] != _CONVENTION_DIR.split('/')[1]:
                    raise MeminitError(
                        code=ErrorCode.INVALID_TEMPLATE_FILE,
                        message=f"Convention templates must be under docs/{_CONVENTION_DIR}/: {path.relative_to(self._repo_root)}",
                        details={"path": str(path)}
                    )
            except ValueError:
                # path.relative_to failed - outside docs_dir
                raise MeminitError(
                    code=ErrorCode.INVALID_TEMPLATE_FILE,
                    message=f"Convention template outside docs directory: {path.relative_to(self._repo_root)}",
                    details={"path": str(path)}
                )
