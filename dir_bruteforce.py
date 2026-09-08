"""
dir_bruteforce - async directory/file bruteforcer for kalisub

Requires: aiohttp (pip install aiohttp, if not already a project dependency)
"""

import asyncio
import random
import string

import aiohttp

from utils import print_status, color

# small built-in wordlist covering the usual high-value paths.
# for real engagements, pass a bigger list (raft-small/medium from SecLists) via -w.
DEFAULT_WORDLIST = [
    "admin", "login", "administrator", "wp-admin", "wp-login.php",
    "api", "api/v1", "backup", "backups", "config", "config.php",
    ".env", ".env.bak", ".git", ".git/config", ".git/HEAD",
    "uploads", "upload", "dashboard", "dev", "staging", "test",
    "robots.txt", "sitemap.xml", ".htaccess", "server-status",
    "phpinfo.php", "info.php", "db", "database", "sql", "old",
    "tmp", "temp", "logs", "log", "debug", "swagger", "swagger-ui",
    "graphql", "console", ".well-known/security.txt", "vendor",
    "node_modules", ".DS_Store", "web.config", "install", "setup",
]

# status codes worth reporting (skip plain 404s / 5xx noise)
INTERESTING_STATUSES = {200, 201, 204, 301, 302, 307, 308, 401, 403}


def load_wordlist(path: str = None) -> list:
    if not path:
        return list(DEFAULT_WORDLIST)
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def _random_path() -> str:
    junk = "".join(random.choices(string.ascii_lowercase, k=12))
    return f"{junk}-kalisub-nonexistent"


async def _fetch(session, url, timeout):
    try:
        async with session.get(url, timeout=timeout, allow_redirects=False) as resp:
            body = await resp.read()
            return resp.status, len(body), resp.headers.get("Location")
    except Exception:
        return None, None, None


async def _detect_baseline(session, base_url, timeout):
    """Hit a random non-existent path first, so we can filter out soft-404
    pages (servers that return 200 for everything instead of a real 404)."""
    url = f"{base_url}/{_random_path()}"
    return await _fetch(session, url, timeout)


async def brute_directory(
    base_url: str,
    wordlist=None,
    extensions=None,
    concurrency: int = 30,
    timeout: float = 5.0,
    use_color: bool = True,
    silent: bool = False,
) -> list:
    """
    Bruteforce paths under base_url (e.g. "https://example.com").
    Returns a list of {path, status, length, location} dicts for hits,
    filtering out responses that match the detected soft-404 baseline.
    """
    base_url = base_url.rstrip("/")
    words = wordlist or DEFAULT_WORDLIST
    exts = extensions or [""]

    paths = set()
    for w in words:
        for ext in exts:
            if not ext or "." in w:
                paths.add(w)
            else:
                paths.add(f"{w}{ext}")

    found = []
    sem = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(headers={"User-Agent": "kalisub-dirb/1.0"}) as session:
        baseline_status, baseline_len, _ = await _detect_baseline(session, base_url, timeout)
        if not silent and baseline_status is not None:
            print_status(
                f"baseline check -> status {baseline_status}, length {baseline_len}b "
                f"(hits matching this exactly are treated as soft-404 and skipped)",
                use_color,
            )

        async def worker(path):
            async with sem:
                url = f"{base_url}/{path}"
                status, length, location = await _fetch(session, url, timeout)
                if status is None or status not in INTERESTING_STATUSES:
                    return
                if status == baseline_status and length == baseline_len:
                    return  # matches the soft-404 baseline, ignore
                found.append({"path": path, "status": status, "length": length, "location": location})
                if not silent:
                    tag_color = "green" if status < 300 else ("yellow" if status < 400 else "dim")
                    tag = color(f"[{status}]", tag_color, use_color)
                    extra = f" -> {location}" if location else ""
                    print_status(f"{base_url}/{path} {tag} ({length}b){extra}", use_color)

        await asyncio.gather(*(worker(p) for p in paths))

    found.sort(key=lambda x: x["path"])
    return found
