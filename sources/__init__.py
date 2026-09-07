from .crtsh import CrtSh
from .hackertarget import HackerTarget
from .otx import OTX
from .rapiddns import RapidDNS
from .wayback import Wayback

# Adding a new source = write sources/newsource.py + add one line here.
ALL_SOURCES = [CrtSh, HackerTarget, OTX, RapidDNS, Wayback]
