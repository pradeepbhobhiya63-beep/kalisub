"""
Base class for every subdomain source plugin.
Each source only needs to implement `fetch()` and return a set of hostnames.
This is what makes adding a new source as easy as dropping a new file in sources/.
"""

from abc import ABC, abstractmethod
import aiohttp


class Source(ABC):
    name: str = "base"
    # Per-source timeout so one slow API never stalls the whole run
    timeout: int = 15

    def __init__(self, domain: str, session: aiohttp.ClientSession, config: dict):
        self.domain = domain
        self.session = session
        self.config = config  # holds API keys etc, loaded from ~/.config/kalisub/config.yaml

    @abstractmethod
    async def fetch(self) -> set[str]:
        """Return a set of raw subdomain strings. Must not raise — catch and return set() on failure."""
        ...

    async def _get(self, url: str, **kwargs):
        """Shared GET helper with timeout + safe failure."""
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=self.timeout), **kwargs
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.text()
        except Exception:
            return None
