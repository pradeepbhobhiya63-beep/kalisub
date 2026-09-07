import json
from .base import Source


class OTX(Source):
    name = "otx"

    async def fetch(self) -> set[str]:
        url = f"https://otx.alienvault.com/api/v1/indicators/domain/{self.domain}/passive_dns"
        text = await self._get(url)
        if not text:
            return set()

        found = set()
        try:
            data = json.loads(text)
            for record in data.get("passive_dns", []):
                hostname = record.get("hostname", "").strip().lower()
                if hostname and hostname.endswith(self.domain):
                    found.add(hostname)
        except json.JSONDecodeError:
            pass
        return found
