# kalisub

Multi-source subdomain enumeration tool, `subfinder`-style, built for Kali.

## Why this exists

Started as a single crt.sh scraper. This version restructures it into a
plugin-style architecture (like ProjectDiscovery's `subfinder`) so adding a
new source is just one file, and runs every source **concurrently** with
`asyncio` instead of one after another.

## Sources (v0.1)

- crt.sh
- HackerTarget
- AlienVault OTX
- RapidDNS
- Wayback Machine (CDX API)

## Setup

```bash
cd kalisub
pip install -r requirements.txt --break-system-packages   # or use a venv
```

## Usage

```bash
# basic
python3 main.py -d example.com

# save plain hostname list
python3 main.py -d example.com -o results.txt

# save full JSON (sources + confidence per host)
python3 main.py -d example.com -oJ results.json

# only keep hosts that actually resolve (DNS check)
python3 main.py -d example.com -active

# bulk mode
python3 main.py -dL domains.txt -silent -o all.txt

# only show high-confidence results (found by 50%+ of sources)
python3 main.py -d example.com -min-confidence 0.5
```

## Confidence scoring (the differentiator feature)

Every hit is tagged with how many independent sources found it:

```
score = (sources that found this host) / (total sources)
```

A subdomain that shows up in crt.sh AND HackerTarget AND OTX is far more
trustworthy than one only Wayback found once. This is the first version of
the differentiator — planned next: CVE correlation per resolved host, and
wordlist-based brute force as an additional "source".

## Adding a new source

1. Create `sources/newsource.py`, subclass `Source` from `sources/base.py`,
   implement `async def fetch(self) -> set[str]`.
2. Add it to `ALL_SOURCES` in `sources/__init__.py`.

That's it — it's picked up automatically by the concurrent runner and
included in confidence scoring.

## Notes

- No API keys required for v0.1's sources. `config.py`/`config` dict is
  wired through already for when OTX or others need a key later.
- `-active` uses stdlib DNS resolution (`getaddrinfo`) — no extra
  dependency, but slower than `aiodns`/`massdns`. Fine for a few hundred
  hosts; swap in `aiodns` if you scale up to thousands.
