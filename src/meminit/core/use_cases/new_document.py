import re
from datetime import date
from pathlib import Path
from typing import Dict, Optional

import frontmatter
import yaml

from meminit.core.services.repo_config import RepoConfig, load_repo_layout


class NewDocumentUseCase:
    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self.root_dir = self._layout.root_dir

    def execute(self, doc_type: str, title: str, namespace: Optional[str] = None) -> Path:
        ns = (
            self._layout.get_namespace(namespace) if namespace else self._layout.default_namespace()
        )
        if ns is None:
            valid = [n.namespace for n in self._layout.namespaces]
            raise ValueError(f"Unknown namespace: {namespace}. Valid namespaces: {valid}")

        normalized_type = self._normalize_type(doc_type)
        expected_subdir = ns.expected_subdir_for_type(normalized_type)
        if not expected_subdir:
            valid = sorted(ns.type_directories.keys())
            raise ValueError(f"Unknown document type: {doc_type}. Valid types: {valid}")

        target_dir = ns.docs_dir / expected_subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        # ID Generation
        doc_id = self._generate_id(normalized_type, target_dir, ns)

        # Filename Generation
        filename = self._generate_filename(doc_id, title)
        target_path = target_dir / filename

        # Template Loading
        content = self._load_template(normalized_type, title, doc_id, ns)

        if target_path.exists():
            raise FileExistsError(f"Document already exists: {target_path}")

        target_path.write_text(content, encoding="utf-8")
        return target_path

    def _normalize_type(self, doc_type: str) -> str:
        t = str(doc_type).strip().upper()
        if t == "GOVERNANCE":
            return "GOV"
        return t

    def _generate_id(self, doc_type: str, target_dir: Path, ns: RepoConfig) -> str:
        repo_prefix = ns.repo_prefix
        id_type = self._id_type_segment(doc_type)

        max_id = 0
        # Our generated filenames start with `<type>-<NNN>-...` (e.g., `adr-001-title.md`).
        regex = re.compile(rf"^{re.escape(id_type.lower())}-(\d{{3}})-", re.IGNORECASE)
        frontmatter_regex = re.compile(
            rf"^[A-Z]{{3,10}}-{re.escape(id_type)}-(\d{{3}})$", re.IGNORECASE
        )

        for p in target_dir.glob("*.md"):
            # Try to find ID in frontmatter or filename
            # Filename typical: prefix-001-title.md
            match = regex.match(p.name)
            if match:
                num = int(match.group(1))
                if num > max_id:
                    max_id = num
            else:
                # Fall back to frontmatter if filename does not include a parseable ID.
                try:
                    post = frontmatter.load(p)
                except (OSError, UnicodeDecodeError, yaml.YAMLError):
                    continue

                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str):
                    continue

                doc_id = doc_id.strip()
                match = frontmatter_regex.match(doc_id)
                if match:
                    num = int(match.group(1))
                    if num > max_id:
                        max_id = num

        next_id = max_id + 1
        return f"{repo_prefix}-{id_type}-{next_id:03d}"

    def _generate_filename(self, doc_id: str, title: str) -> str:
        safe_title = title.lower().replace(" ", "-")
        # Remove special chars
        safe_title = re.sub(r"[^a-z0-9-]", "", safe_title)
        safe_title = re.sub(r"-{2,}", "-", safe_title).strip("-")
        if not safe_title:
            safe_title = "untitled"
        parts = doc_id.split("-")
        short_id = doc_id.lower()
        if len(parts) >= 3:
            short_id = f"{parts[-2].lower()}-{parts[-1].lower()}"
        return f"{short_id}-{safe_title}.md"

    def _load_template(self, doc_type: str, title: str, doc_id: str, ns: RepoConfig) -> str:
        template_path_str = ns.templates.get(doc_type.lower())
        template_content = ""

        if template_path_str:
            template_path = self.root_dir / template_path_str
            if template_path.exists():
                template_content = template_path.read_text(encoding="utf-8")

        body = template_content
        if body.strip().startswith("---"):
            # Template may contain placeholder frontmatter; we always generate canonical frontmatter.
            try:
                post = frontmatter.loads(body)
            except (yaml.YAMLError, ValueError):
                pass
            else:
                body = post.content

        if not body.strip():
            body = f"# {doc_type}: {title}\n\n## Context\n\n## Content\n"

        body = self._apply_common_template_substitutions(
            body, doc_type=doc_type, title=title, doc_id=doc_id, status="Draft"
        )

        docops_version = str(ns.docops_version or "2.0")

        metadata = {
            "document_id": doc_id,
            "type": doc_type,
            "title": title,
            "status": "Draft",
            "version": "0.1",
            "last_updated": date.today().isoformat(),
            "owner": "__TBD__",
            "docops_version": docops_version,
        }

        fm_yaml = yaml.safe_dump(metadata, sort_keys=False, default_flow_style=False).strip()
        return f"---\n{fm_yaml}\n---\n\n{body.lstrip()}"

    def _id_type_segment(self, doc_type: str) -> str:
        doc_type_upper = doc_type.upper()
        if doc_type_upper == "GOVERNANCE":
            return "GOV"
        if 3 <= len(doc_type_upper) <= 10 and doc_type_upper.isalpha():
            return doc_type_upper
        segment = re.sub(r"[^A-Z]", "", doc_type_upper)[:10]
        return segment if len(segment) >= 3 else "DOC"

    def _apply_common_template_substitutions(
        self, body: str, doc_type: str, title: str, doc_id: str, status: str
    ) -> str:
        """
        Apply substitutions for templates that use human-friendly placeholder tokens.

        We support both:
        - `{title}`, `{status}` (simple MVP placeholders)
        - `<REPO>`, `<PROJECT>`, `<SEQ>`, `<YYYY-MM-DD>`, `<Decision Title>`, `<Team or Person>`

        This keeps legacy templates usable without requiring a full templating engine.
        """
        parts = doc_id.split("-")
        repo_prefix = parts[0] if len(parts) >= 1 else self._layout.default_namespace().repo_prefix
        seq = parts[-1] if len(parts) >= 3 else "001"

        today = date.today().isoformat()

        substitutions = {
            "{title}": title,
            "{status}": status,
            "<REPO>": repo_prefix,
            "<PROJECT>": repo_prefix,
            "<SEQ>": seq,
            "<YYYY-MM-DD>": today,
            "<Decision Title>": title,
            "<Feature Title>": title,
            "<Team or Person>": "__TBD__",
        }

        for k, v in substitutions.items():
            body = body.replace(k, v)

        return body
