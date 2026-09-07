import re
from urllib.parse import urlparse
from .base import Source


class Wayback(Source):
    name = "wayback"
    timeout = 30  # CDX API can be slow for domains with huge archive history

    async def fetch(self) -> set[str]:
        url = (
            f"https://web.archive.org/cdx/search/cdx"
            f"?url=*.{self.domain}/*&output=text&fl=original&collapse=urlkey"
        )
        text = await self._get(url)
        if not text:
            return set()

        found = set()
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                host = urlparse(line).netloc.lower()
                # strip port if present
                host = host.split(":")[0]
                if host and re.match(rf"^[a-zA-Z0-9_.-]+\.{re.escape(self.domain)}$", host):
                    found.add(host)
            except Exception:
                continue
        return found
