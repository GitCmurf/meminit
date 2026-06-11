"""Python-frontmatter adapter implementing FrontmatterPort."""
import frontmatter

from meminit.core.ports.frontmatter_port import FrontmatterPort


class PythonFrontmatterAdapter:
    """Concrete frontmatter adapter wrapping python-frontmatter."""

    def load(self, path: str):
        post = frontmatter.load(path)
        return dict(post.metadata), post.content

    def loads(self, text: str):
        post = frontmatter.loads(text)
        return dict(post.metadata), post.content
