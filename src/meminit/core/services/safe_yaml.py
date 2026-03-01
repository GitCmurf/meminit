import frontmatter
import yaml

def safe_frontmatter_loads(text: str) -> frontmatter.Post:
    """
    Safely load frontmatter from markdown text using yaml.SafeLoader.
    This prevents arbitrary code execution and billion-laughs attacks
    during repo scans.
    """
    # python-frontmatter uses yaml.load with FullLoader or UnsafeLoader by default 
    # depending on the setup. We override the handler to strictly use SafeLoader.
    handler = frontmatter.YAMLHandler()
    handler.Loader = yaml.SafeLoader
    
    return frontmatter.loads(text, handler=handler)
