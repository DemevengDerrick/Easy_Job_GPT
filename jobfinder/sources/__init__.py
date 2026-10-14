from pathlib import Path

import yaml

from .ats import Cornerstone, OracleRecruiting, PageUp, SuccessFactorsRSS, Taleo, Workday
from .base import Source, SourceError
from .boards import Adzuna, Arbeitnow, Greenhouse, Jooble, Lever, RemoteOK, Remotive, WeWorkRemotely
from .reliefweb import ReliefWeb
from .un_careers import UNCareers

CONFIG = Path(__file__).resolve().parent.parent / "sources.yaml"

# yaml key -> adapter. Lists configure one source per organisation.
SINGLE = {
    "un_careers": UNCareers,
    "reliefweb": ReliefWeb,
    "adzuna": Adzuna,
    "jooble": Jooble,
    "remotive": Remotive,
    "arbeitnow": Arbeitnow,
    "remoteok": RemoteOK,
    "weworkremotely": WeWorkRemotely,
    "greenhouse": Greenhouse,
    "lever": Lever,
}
PER_ORG = {
    "oracle_recruiting": OracleRecruiting,
    "taleo": Taleo,
    "workday": Workday,
    "cornerstone": Cornerstone,
    "successfactors_rss": SuccessFactorsRSS,
    "pageup": PageUp,
}


def load_sources(path=CONFIG):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    sources = []
    for key, value in cfg.items():
        if key in SINGLE and (value or {}).get("enabled", True):
            sources.append(SINGLE[key](value))
        elif key in PER_ORG:
            sources += [PER_ORG[key](org) for org in value or [] if org.get("enabled", True)]
    return sources


__all__ = ["Source", "SourceError", "load_sources"]
