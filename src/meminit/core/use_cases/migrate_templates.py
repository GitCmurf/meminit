from __future__ import annotations

import datetime
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.repo_config import (
    DEFAULT_DOCS_ROOT,
    DocumentTypeConfig,
    RepoConfig,
    load_repo_layout,
)
from meminit.core.services.template_resolver import _CONVENTION_DIR

LEGACY_PLACEHOLDER_MAPPINGS = {
    "{title}": "{{title}}",
    "{type}": "{{type}}",
    "{status}": "{{status}}",
    "{owner}": "{{owner}}",
    "{area}": "{{area}}",
    "{description}": "{{description}}",
    "{keywords}": "{{keywords}}",
    "{related_ids}": "{{related_ids}}",
    "<REPO>": "{{repo_prefix}}",
    "<PROJECT>": "{{repo_prefix}}",
    "<SEQ>": "{{seq}}",
    "<YYYY-MM-DD>": "{{date}}",
    "<AREA>": "{{area}}",
    "<Decision Title>": "{{title}}",
    "<Feature Title>": "{{title}}",
    "<Team or Person>": "{{owner}}",
}

# Reuse CODE_FENCE_PATTERN from section_parser for consistency
CODE_FENCE_PATTERN = re.compile(r"^\s*([`~]{3,})", re.MULTILINE)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)

# Pattern to detect remaining legacy placeholders after migration
# Matches { not preceded by { and not followed by {, OR < not preceded by < and not followed by <
# This correctly identifies {title} but not {{title}}
LEGACY_PLACEHOLDER_PATTERN = re.compile(
    r"(?<![{])\{[a-zA-Z_][a-zA-Z0-9_]*\}(?![}])|(?<![<])<[A-Z][^>]*>(?![>])"
)


@dataclass(frozen=True)
class TemplateMigrationAction:
    action_type: str
    file: Optional[str] = None
    from_path: Optional[str] = None
    to_path: Optional[str] = None
    path: Optional[str] = None
    value: Optional[str] = None
    placeholder_from: Optional[str] = None
    placeholder_to: Optional[str] = None
    count: int = 0

    def as_dict(self) -> dict:
        result: Dict[str, Any] = {"type": self.action_type}
        if self.file:
            result["file"] = self.file
        if self.from_path:
            result["from"] = self.from_path
        if self.to_path:
            result["to"] = self.to_path
        if self.path:
            result["path"] = self.path
        if self.value is not None:
            result["value"] = self.value
        if self.placeholder_from:
            result["from"] = self.placeholder_from
            result["to"] = self.placeholder_to
        if self.count:
            result["count"] = self.count
        if self.action_type == "config":
            result["action"] = "add" if self.value is not None else "remove"
        elif self.action_type == "file":
            result["action"] = "rename"
        elif self.action_type == "replace":
            result["type"] = "file"
            result["action"] = "replace"
        return result


@dataclass(frozen=True)
class TemplateMigrationReport:
    dry_run: bool
    config_file: str
    templates_dir: str
    backup_path: Optional[str]
    success: bool = True
    config_entries_found: int = 0
    config_entries_migrated: int = 0
    template_files_found: int = 0
    template_files_renamed: int = 0
    placeholder_replacements: int = 0
    actions: List[TemplateMigrationAction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "config_file": self.config_file,
            "templates_dir": self.templates_dir,
            "dry_run": self.dry_run,
            "backup_path": self.backup_path,
            "success": self.success,
            "summary": {
                "config_entries_found": self.config_entries_found,
                "config_entries_migrated": self.config_entries_migrated,
                "template_files_found": self.template_files_found,
                "template_files_renamed": self.template_files_renamed,
                "placeholder_replacements": self.placeholder_replacements,
            },
            "changes": [a.as_dict() for a in self.actions],
            "warnings": self.warnings,
            "skipped_files": self.skipped_files,
        }


class MigrateTemplatesUseCase:
    """
    Migrate legacy template configurations and placeholder syntax to Templates v2 format.

    Safety:
    - dry-run by default (caller decides whether to write)
    - creates backup before modifying files
    - only migrates governed templates under configured templates directory
    - preserves existing document_types configuration
    """

    def __init__(self, root_dir: str):
        self._root_dir = Path(root_dir).resolve()
        self._layout = load_repo_layout(str(self._root_dir))
        self._config_file = self._root_dir / "docops.config.yaml"
        # Cache default_ns for efficiency - avoid repeated calls in hot paths
        self._default_ns = self._layout.default_namespace()
        # Pre-compute normalized templates prefix for efficiency
        if self._default_ns:
            docs_root = self._default_ns.docs_root.strip("/")
            if docs_root:
                self._templates_prefix = f"{docs_root}/{_CONVENTION_DIR}"
                self._docs_root = docs_root
                self._docs_root_prefix = f"{docs_root}/"
            else:
                self._templates_prefix = _CONVENTION_DIR
                self._docs_root = ""
                self._docs_root_prefix = ""
        else:
            self._templates_prefix = f"{DEFAULT_DOCS_ROOT}/{_CONVENTION_DIR}"
            self._docs_root = DEFAULT_DOCS_ROOT
            self._docs_root_prefix = f"{DEFAULT_DOCS_ROOT}/"

    def execute(
        self,
        dry_run: bool = True,
        backup: bool = True,
        migrate_type_directories: bool = True,
        migrate_templates: bool = True,
        migrate_placeholders: bool = True,
        rename_files: bool = True,
    ) -> TemplateMigrationReport:
        actions: List[TemplateMigrationAction] = []
        warnings: List[str] = []
        skipped: List[str] = []

        backup_path: Optional[str] = None
        if backup and not dry_run:
            backup_path = self._create_backup()

        config_data: Dict[str, Any] = {}
        if migrate_type_directories or migrate_templates:
            if self._config_file.exists():
                try:
                    config_data = (
                        yaml.safe_load(self._config_file.read_text(encoding="utf-8"))
                        or {}
                    )
                except Exception as e:
                    warnings.append(f"Failed to parse config: {e}")
                    return TemplateMigrationReport(
                        dry_run=dry_run,
                        config_file=relative_path_string(self._config_file, self._root_dir),
                        templates_dir=relative_path_string(self._get_templates_dir(), self._root_dir),
                        backup_path=backup_path,
                        success=False,
                        warnings=warnings,
                    )

        templates_dir = self._get_templates_dir()

        # Phase 1: Determine file renames and resolve collisions.
        path_mapping: Dict[str, str] = {}  # rel_old_path -> rel_new_path
        if templates_dir.exists() and templates_dir.is_dir() and rename_files:
            # Sort for deterministic collision resolution.
            for template_file in sorted(templates_dir.glob("*.md")):
                new_name = self._get_new_template_name(template_file.name)
                if new_name and new_name != template_file.name:
                    target_path = templates_dir / new_name
                    rel_target = target_path.relative_to(self._root_dir).as_posix()

                    # Handle name collision (disk existence OR already planned in this run)
                    if target_path.exists() or rel_target in path_mapping.values():
                        base = new_name.replace(".template.md", "")
                        found_target = False
                        for i in range(1, 100):
                            new_target = templates_dir / f"{base}.template.{i}.md"
                            rel_new_target = new_target.relative_to(self._root_dir).as_posix()
                            if not new_target.exists() and rel_new_target not in path_mapping.values():
                                target_path = new_target
                                found_target = True
                                break
                        
                        if not found_target:
                            warnings.append(
                                f"Skipping rename of {template_file.name}: all numbered variants (1-99) exist or are reserved"
                            )
                            continue

                    old_rel = template_file.relative_to(self._root_dir).as_posix()
                    new_rel = target_path.relative_to(self._root_dir).as_posix()
                    path_mapping[old_rel] = new_rel

        config_entries_found = 0
        config_entries_migrated = 0

        if migrate_type_directories and "type_directories" in config_data:
            type_dirs = config_data.get("type_directories", {})
            if isinstance(type_dirs, dict):
                config_entries_found += len(type_dirs)

                if "document_types" not in config_data:
                    config_data["document_types"] = {}

                migrated_keys = []
                for doc_type, directory in type_dirs.items():
                    doc_type_key = doc_type.upper()
                    existing = config_data["document_types"].get(doc_type_key)
                    if existing is not None:
                        if isinstance(existing, dict):
                            if existing.get("directory"):
                                warnings.append(
                                    f"Skipping type_directories.{doc_type}: directory already exists in document_types.{doc_type_key}"
                                )
                                continue
                            existing["directory"] = directory
                        else:
                            # existing is a string (legacy template path)
                            config_data["document_types"][doc_type_key] = {
                                "directory": directory,
                                "template": existing,
                            }
                    else:
                        config_data["document_types"][doc_type_key] = {
                            "directory": directory
                        }
                    
                    config_entries_migrated += 1
                    migrated_keys.append(doc_type)
                    actions.append(
                        TemplateMigrationAction(
                            action_type="config",
                            path=f"document_types.{doc_type_key}.directory",
                            value=directory,
                        )
                    )
                    actions.append(
                        TemplateMigrationAction(
                            action_type="config",
                            path=f"type_directories.{doc_type}",
                        )
                    )

                self._remove_migrated_keys(config_data, "type_directories", migrated_keys)

        if migrate_templates and "templates" in config_data:
            templates_config = config_data.get("templates", {})
            if isinstance(templates_config, dict):
                config_entries_found += len(templates_config)

                if "document_types" not in config_data:
                    config_data["document_types"] = {}

                migrated_keys = []
                for doc_type, template_path in templates_config.items():
                    doc_type_key = doc_type.upper()
                    normalized_path = self._normalize_template_path(template_path)

                    if rename_files:
                        if normalized_path in path_mapping:
                            normalized_path = path_mapping[normalized_path]
                        else:
                            new_name = self._get_new_template_name(
                                Path(normalized_path).name
                            )
                            if new_name:
                                normalized_path = (
                                    Path(normalized_path).parent / new_name
                                ).as_posix()

                    if doc_type_key in config_data["document_types"]:
                        existing = config_data["document_types"][doc_type_key]
                        if isinstance(existing, dict) and existing.get("template"):
                            warnings.append(
                                f"Skipping templates.{doc_type}: already has template in document_types"
                            )
                            continue
                        if isinstance(existing, dict):
                            existing["template"] = normalized_path
                        else:
                            config_data["document_types"][doc_type_key] = {
                                "directory": existing
                                if isinstance(existing, str)
                                else "",
                                "template": normalized_path,
                            }
                    else:
                        # Use cached default_ns for efficiency
                        default_directory = (
                            self._default_ns.expected_subdir_for_type(doc_type_key)
                            if self._default_ns
                            else ""
                        )
                        config_data["document_types"][doc_type_key] = {
                            "directory": default_directory,
                            "template": normalized_path,
                        }

                    config_entries_migrated += 1
                    migrated_keys.append(doc_type)
                    actions.append(
                        TemplateMigrationAction(
                            action_type="config",
                            path=f"document_types.{doc_type_key}.template",
                            value=normalized_path,
                        )
                    )

                self._remove_migrated_keys(config_data, "templates", migrated_keys)

        template_files_found = 0
        template_files_renamed = 0
        placeholder_replacements = 0

        if templates_dir.exists() and templates_dir.is_dir():
            for template_file in templates_dir.glob("*.md"):
                template_files_found += 1

                actually_renamed = False
                target_path = template_file
                old_rel = template_file.relative_to(self._root_dir).as_posix()

                if old_rel in path_mapping:
                    target_path = self._root_dir / path_mapping[old_rel]

                    if rename_files:
                        actions.append(
                            TemplateMigrationAction(
                                action_type="file",
                                from_path=old_rel,
                                to_path=path_mapping[old_rel],
                            )
                        )
                        template_files_renamed += 1

                        if not dry_run:
                            template_file.rename(target_path)
                            actually_renamed = True

                if migrate_placeholders:
                    file_to_work_on = target_path if actually_renamed else template_file

                    try:
                        content = file_to_work_on.read_text(encoding="utf-8")
                    except Exception as e:
                        warnings.append(f"Failed to read {file_to_work_on.name}: {e}")
                        continue

                    original_content = content

                    content, placeholder_replacements = (
                        self._replace_placeholders_aware(
                            content,
                            LEGACY_PLACEHOLDER_MAPPINGS,
                            placeholder_replacements,
                            actions,
                            file_to_work_on,
                        )
                    )

                    # Re-check for remaining legacy placeholders.
                    protected_ranges_check = self._get_protected_ranges(content)
                    remaining_legacy = []
                    for match in LEGACY_PLACEHOLDER_PATTERN.finditer(content):
                        in_protected = any(
                            start <= match.start() < end
                            for start, end in protected_ranges_check
                        )
                        if not in_protected:
                            remaining_legacy.append(match.group(0))

                    if remaining_legacy:
                        unique_remaining = set(remaining_legacy)
                        warnings.append(
                            f"Unsupported legacy placeholders in {file_to_work_on.name}: "
                            f"{', '.join(sorted(unique_remaining))}"
                        )

                    if content != original_content and not dry_run:
                        file_to_work_on.write_text(content, encoding="utf-8")

        if not dry_run and config_data:
            self._config_file.write_text(
                yaml.dump(config_data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )

        return TemplateMigrationReport(
            dry_run=dry_run,
            config_file=relative_path_string(self._config_file, self._root_dir),
            templates_dir=relative_path_string(templates_dir, self._root_dir),
            backup_path=backup_path,
            config_entries_found=config_entries_found,
            config_entries_migrated=config_entries_migrated,
            template_files_found=template_files_found,
            template_files_renamed=template_files_renamed,
            placeholder_replacements=placeholder_replacements,
            actions=actions,
            warnings=warnings,
            skipped_files=skipped,
        )

    def _get_templates_dir(self) -> Path:
        """Get the templates directory for the current namespace."""
        if self._default_ns:
            return self._default_ns.docs_dir / _CONVENTION_DIR
        return self._root_dir / DEFAULT_DOCS_ROOT / _CONVENTION_DIR

    def _remove_migrated_keys(
        self, config_data: Dict[str, Any], section: str, migrated_keys: List[str]
    ) -> None:
        """Remove migrated keys from config section and delete section if empty."""
        for key in migrated_keys:
            config_data[section].pop(key, None)

        if not config_data.get(section):
            config_data.pop(section, None)

    def _normalize_template_path(self, raw_path: str) -> str:
        path = raw_path.strip()
        if path.startswith("./"):
            path = path[2:]

        # Use cached prefix for efficiency
        if path == self._templates_prefix or path.startswith(f"{self._templates_prefix}/"):
            return path
        if self._docs_root_prefix and path.startswith(self._docs_root_prefix):
            path = path[len(self._docs_root_prefix):]
        return f"{self._templates_prefix}/{path}"

    def _get_new_template_name(self, old_name: str) -> Optional[str]:
        match = re.match(r"template-\d{3}-(.+)\.md$", old_name)
        if match:
            doc_type = match.group(1).lower()
            return f"{doc_type}.template.md"
        return None

    def _get_protected_ranges(self, content: str) -> List[Tuple[int, int]]:
        """Get character ranges that should not be modified during placeholder replacement.

        Includes HTML comments and code fence blocks (stateful tracking to handle
        nested or edge cases with fence char/length matching).
        """
        protected = []

        # HTML comments are protected
        for match in HTML_COMMENT_PATTERN.finditer(content):
            protected.append((match.start(), match.end()))

        # Code fences - use stateful tracking like SectionParser does
        in_code_fence = False
        current_fence_char = ""
        current_fence_len = 0
        fence_start = 0

        for match in CODE_FENCE_PATTERN.finditer(content):
            fence_str = match.group(1)
            fence_char = fence_str[0]
            fence_len = len(fence_str)

            if in_code_fence:
                if fence_char == current_fence_char and fence_len >= current_fence_len:
                    # Closing fence - end protected range at match.end()
                    protected.append((fence_start, match.end()))
                    in_code_fence = False
                    current_fence_char = ""
                    current_fence_len = 0
            else:
                # Opening fence - start protected range
                in_code_fence = True
                current_fence_char = fence_char
                current_fence_len = fence_len
                fence_start = match.start()

        # If still in code fence at end, protect to end of content
        if in_code_fence:
            protected.append((fence_start, len(content)))

        return protected

    def _replace_placeholders_aware(
        self,
        content: str,
        mappings: Dict[str, str],
        placeholder_replacements: int,
        actions: List[TemplateMigrationAction],
        template_file: Path,
    ) -> Tuple[str, int]:
        result = content
        for legacy, new in mappings.items():
            idx = 0
            while True:
                idx = result.find(legacy, idx)
                if idx == -1:
                    break
                
                # Recompute protected ranges for each check to handle shifts
                protected_ranges = self._get_protected_ranges(result)
                in_protected = any(
                    start <= idx < end for start, end in protected_ranges
                )
                if not in_protected:
                    result = result[:idx] + new + result[idx + len(legacy) :]
                    placeholder_replacements += 1
                    actions.append(
                        TemplateMigrationAction(
                            action_type="replace",
                            file=str(template_file.relative_to(self._root_dir)),
                            placeholder_from=legacy,
                            placeholder_to=new,
                            count=1,
                        )
                    )
                    idx += len(new)
                else:
                    idx += len(legacy)
        return result, placeholder_replacements

    def _create_backup(self) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = self._root_dir / ".meminit" / "migrations" / f"backup-{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        if self._config_file.exists():
            shutil.copy2(self._config_file, backup_dir / "docops.config.yaml")

        templates_dir = self._get_templates_dir()

        if templates_dir.exists() and templates_dir.is_dir():
            backup_templates = backup_dir / "templates"
            backup_templates.mkdir(exist_ok=True)
            for template_file in templates_dir.glob("*.md"):
                shutil.copy2(template_file, backup_templates / template_file.name)

        return str(backup_dir.relative_to(self._root_dir))
