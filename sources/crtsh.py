import json
import re
from .base import Source


class CrtSh(Source):
    name = "crtsh"
    timeout = 25  # crt.sh is notoriously slow under load

    async def fetch(self) -> set[str]:
        # %25 = URL-encoded wildcard % — this was the key fix from the original scraper
        url = f"https://crt.sh/?q=%25.{self.domain}&output=json"
        text = await self._get(url)
        if not text:
            return set()

        found = set()
        try:
            data = json.loads(text)
            for entry in data:
                name_value = entry.get("name_value", "")
                for line in name_value.split("\n"):
                    line = line.strip().lower()
                    if line and not line.startswith("*."):
                        found.add(line)
                    elif line.startswith("*."):
                        found.add(line[2:])
        except json.JSONDecodeError:
            # crt.sh sometimes returns malformed/truncated JSON under load — fall back to regex
            found.update(re.findall(rf"([a-zA-Z0-9_.-]+\.{re.escape(self.domain)})", text))

        return found
