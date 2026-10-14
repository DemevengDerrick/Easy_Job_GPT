class SourceError(Exception):
    """Raised when a source answers but can't be used (blocked, missing key...)."""


class Source:
    """A job source.

    `per_keyword = False` sources return every open posting (keyword matching happens
    locally, see filters.py) and are cached between searches. `per_keyword = True`
    sources are queried once per keyword because they are too large to list in full.
    """

    name = "source"
    org_type = ""
    per_keyword = False
    cache_ttl = 3600  # seconds, for per_keyword = False sources

    def __init__(self, cfg=None):
        cfg = cfg or {}
        self.name = cfg.get("name", self.name)
        self.org_type = cfg.get("org_type", self.org_type)
        self.cfg = cfg

    def fetch(self, keyword=None):
        raise NotImplementedError

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"
