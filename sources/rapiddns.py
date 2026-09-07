import re
from .base import Source


class RapidDNS(Source):
    name = "rapiddns"

    async def fetch(self) -> set[str]:
        url = f"https://rapiddns.io/subdomain/{self.domain}?full=1"
        text = await self._get(url)
        if not text:
            return set()

        # RapidDNS returns an HTML table — pull hostnames out with a scoped regex
        pattern = rf"([a-zA-Z0-9_.-]+\.{re.escape(self.domain)})"
        return set(m.lower() for m in re.findall(pattern, text))
