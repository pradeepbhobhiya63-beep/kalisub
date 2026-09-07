import asyncio
import aiohttp

from sources import ALL_SOURCES
from utils import print_status, print_error


async def run_source(source_cls, domain, session, config, use_color, silent):
    source = source_cls(domain, session, config)
    try:
        results = await source.fetch()
        if not silent:
            print_status(f"{source.name}: {len(results)} found", use_color)
        return results
    except Exception as e:
        if not silent:
            print_error(f"{source.name} failed: {e}", use_color)
        return set()


async def enumerate_subdomains(domain: str, config: dict, use_color: bool = True, silent: bool = False) -> dict[str, set[str]]:
    """
    Fan out to every source concurrently.
    Returns {hostname: {source_names_that_found_it}} — this per-host source
    count is what confidence scoring is built on.
    """
    async with aiohttp.ClientSession(
        headers={"User-Agent": "kalisub/0.1"}
    ) as session:
        tasks = [
            run_source(src, domain, session, config, use_color, silent)
            for src in ALL_SOURCES
        ]
        results = await asyncio.gather(*tasks)

    host_to_sources: dict[str, set[str]] = {}
    for src_cls, hosts in zip(ALL_SOURCES, results):
        for h in hosts:
            host_to_sources.setdefault(h, set()).add(src_cls.name)

    # Domain itself should always be considered in scope, treat as max confidence
    host_to_sources.setdefault(domain, set()).add("root")
    return host_to_sources


def confidence_score(num_sources: int, total_sources: int = len(ALL_SOURCES)) -> float:
    """0.0-1.0 — fraction of sources that independently confirmed a subdomain."""
    return round(min(num_sources / total_sources, 1.0), 2)


async def _resolve_one(host: str, sem: asyncio.Semaphore) -> tuple[str, bool]:
    loop = asyncio.get_event_loop()
    async with sem:
        try:
            await asyncio.wait_for(loop.getaddrinfo(host, None), timeout=5)
            return host, True
        except Exception:
            return host, False


async def resolve_alive(hosts: set[str], concurrency: int = 100) -> dict[str, bool]:
    """
    Active DNS resolution (subfinder's -active flag equivalent).
    Uses stdlib resolver via getaddrinfo — no extra dependency, but slower than aiodns.
    Capped concurrency to avoid hammering the local resolver.
    """
    sem = asyncio.Semaphore(concurrency)
    tasks = [_resolve_one(h, sem) for h in hosts]
    results = await asyncio.gather(*tasks)
    return dict(results)
