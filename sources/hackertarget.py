from .base import Source


class HackerTarget(Source):
    name = "hackertarget"

    async def fetch(self) -> set[str]:
        url = f"https://api.hackertarget.com/hostsearch/?q={self.domain}"
        text = await self._get(url)
        if not text or "error" in text.lower():
            return set()

        found = set()
        for line in text.strip().split("\n"):
            host = line.split(",")[0].strip().lower()
            if host:
                found.add(host)
        return found
