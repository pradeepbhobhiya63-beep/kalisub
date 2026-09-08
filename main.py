#!/usr/bin/env python3
"""
kalisub - multi-source recon toolkit (subdomain enum + port scanner)

Interactive mode (menu-driven, recommended for everyday use):
    python3 main.py

Direct CLI mode (subdomain enum only, for scripting/automation):
    python3 main.py -d example.com
    python3 main.py -d example.com -o results.txt
    python3 main.py -d example.com -oJ results.json -active
    python3 main.py -dL domains.txt -silent
"""

import argparse
import asyncio
import json
import sys

from core import enumerate_subdomains, resolve_alive, confidence_score
from sources import ALL_SOURCES
from port_scanner import scan_ports, parse_port_spec
from dir_bruteforce import brute_directory, load_wordlist
from utils import print_banner, print_status, print_error, color


# ---------------------------------------------------------------------------
# CLI flag parsing (only used in direct CLI mode, i.e. when args are passed)
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="kalisub - multi-source subdomain enumeration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("-d", "--domain", help="single target domain")
    target.add_argument("-dL", "--domain-list", help="file with one domain per line")

    p.add_argument("-o", "--output", help="write plain hostnames to file")
    p.add_argument("-oJ", "--output-json", help="write full results (with confidence + sources) as JSON")
    p.add_argument("-active", action="store_true", help="resolve DNS to only keep live/resolvable hosts")
    p.add_argument("-silent", action="store_true", help="only print hostnames, no banner/status logs")
    p.add_argument("-nc", "--no-color", action="store_true", help="disable colored output")
    p.add_argument("-min-confidence", type=float, default=0.0,
                    help="drop results below this confidence score (0.0-1.0)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Subdomain enumeration core (unchanged logic, shared by both modes)
# ---------------------------------------------------------------------------

async def process_domain(domain: str, args, config: dict) -> dict:
    use_color = not args.no_color
    silent = args.silent

    if not silent:
        print_status(f"target: {domain}", use_color)

    host_to_sources = await enumerate_subdomains(domain, config, use_color, silent)

    alive_map = {}
    if args.active:
        if not silent:
            print_status(f"resolving {len(host_to_sources)} hosts...", use_color)
        alive_map = await resolve_alive(set(host_to_sources.keys()))
        host_to_sources = {h: s for h, s in host_to_sources.items() if alive_map.get(h)}

    enriched = {}
    total = len(ALL_SOURCES)
    for host, srcs in host_to_sources.items():
        # root domain is always fully trusted, not scored by source count
        score = 1.0 if host == domain else confidence_score(len(srcs), total)
        if score < args.min_confidence:
            continue
        enriched[host] = {
            "sources": sorted(srcs),
            "confidence": score,
            "alive": alive_map.get(host) if args.active else None,
        }
    return enriched


def print_results(domain: str, results: dict, use_color: bool, silent: bool):
    for host in sorted(results.keys()):
        info = results[host]
        if silent:
            print(host)
            continue
        conf = info["confidence"]
        conf_color = "green" if conf >= 0.5 else ("yellow" if conf >= 0.25 else "dim")
        tag = color(f"[{conf:.2f}]", conf_color, use_color)
        print(f"{host} {tag}")


def write_outputs(domain: str, results: dict, args):
    if args.output:
        with open(args.output, "a") as f:
            for host in sorted(results.keys()):
                f.write(host + "\n")
    if args.output_json:
        with open(args.output_json, "a") as f:
            f.write(json.dumps({domain: results}) + "\n")


# ---------------------------------------------------------------------------
# Direct CLI mode (original behaviour, kept as-is for scripting)
# ---------------------------------------------------------------------------

async def run_cli_mode(args):
    use_color = not args.no_color
    config = {}  # reserved for API keys later (e.g. OTX key), loaded from ~/.config/kalisub/config.yaml

    if not args.silent:
        print_banner(use_color)

    domains = [args.domain] if args.domain else None
    if args.domain_list:
        try:
            with open(args.domain_list) as f:
                domains = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print_error(f"file not found: {args.domain_list}", use_color)
            sys.exit(1)

    for domain in domains:
        results = await process_domain(domain, args, config)
        print_results(domain, results, use_color, args.silent)
        write_outputs(domain, results, args)
        if not args.silent:
            print_status(f"{len(results)} subdomains for {domain}", use_color)


# ---------------------------------------------------------------------------
# Interactive menu mode -> [1] Subdomain Find   [2] Port Scanner
# ---------------------------------------------------------------------------

def show_menu(use_color: bool) -> str:
    print()
    print(color("  [1] Subdomain Find", "cyan", use_color))
    print(color("  [2] Port Scanner", "cyan", use_color))
    print(color("  [3] Directory / File Bruteforcer", "cyan", use_color))
    print(color("  [0] Exit", "dim", use_color))
    print()
    try:
        return input("kalisub> ").strip()
    except EOFError:
        return "0"


async def handle_subdomain_menu(use_color: bool):
    domain = input("\nTarget domain: ").strip()
    if not domain:
        print_error("no domain given", use_color)
        return

    active = input("Resolve only live/alive hosts? (y/N): ").strip().lower() == "y"
    out_file = input("Save hostnames to file (blank = skip): ").strip()

    # build a minimal args-like object so we can reuse process_domain() as-is
    ns = argparse.Namespace(
        active=active,
        silent=False,
        no_color=not use_color,
        min_confidence=0.0,
    )
    config = {}

    print()
    results = await process_domain(domain, ns, config)
    print_results(domain, results, use_color, silent=False)

    if out_file:
        with open(out_file, "a") as f:
            for host in sorted(results.keys()):
                f.write(host + "\n")
        print_status(f"saved {len(results)} hosts -> {out_file}", use_color)

    print_status(f"{len(results)} subdomains for {domain}", use_color)


async def handle_port_scanner_menu(use_color: bool):
    host = input("\nTarget host/IP: ").strip()
    if not host:
        print_error("no target given", use_color)
        return

    spec = input("Ports (blank = common top 20, or e.g. 1-1000, 22,80,443): ").strip()
    try:
        ports = parse_port_spec(spec)
    except ValueError:
        print_error("couldn't parse that port spec", use_color)
        return
    if not ports:
        print_error("no valid ports to scan", use_color)
        return

    conc_raw = input("Concurrency (blank = 200): ").strip()
    try:
        concurrency = int(conc_raw) if conc_raw else 200
    except ValueError:
        concurrency = 200

    print()
    print_status(f"scanning {len(ports)} port(s) on {host}...", use_color)
    open_ports = await scan_ports(
        host, ports, concurrency=concurrency, use_color=use_color, silent=False
    )

    print()
    if open_ports:
        joined = ", ".join(str(p) for p in open_ports)
        print_status(f"{len(open_ports)} open port(s) on {host}: {joined}", use_color)
    else:
        print_status(f"no open ports found on {host}", use_color)


async def handle_dir_bruteforce_menu(use_color: bool):
    base_url = input("\nTarget base URL (e.g. https://example.com): ").strip()
    if not base_url:
        print_error("no URL given", use_color)
        return
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    wl_path = input("Custom wordlist file (blank = built-in ~45 common paths): ").strip()
    try:
        words = load_wordlist(wl_path or None)
    except FileNotFoundError:
        print_error(f"wordlist not found: {wl_path}", use_color)
        return

    ext_raw = input("Extensions to also try, comma-separated (blank = none, e.g. .php,.bak): ").strip()
    extensions = [e if e.startswith(".") else f".{e}" for e in ext_raw.split(",") if e.strip()] or None

    conc_raw = input("Concurrency (blank = 30): ").strip()
    try:
        concurrency = int(conc_raw) if conc_raw else 30
    except ValueError:
        concurrency = 30

    print()
    print_status(f"bruteforcing {len(words)} word(s) on {base_url}...", use_color)
    try:
        results = await brute_directory(
            base_url, wordlist=words, extensions=extensions,
            concurrency=concurrency, use_color=use_color, silent=False,
        )
    except Exception as e:
        print_error(f"scan failed: {e}", use_color)
        return

    print()
    if results:
        print_status(f"{len(results)} interesting path(s) found on {base_url}", use_color)
    else:
        print_status(f"nothing interesting found on {base_url}", use_color)


async def run_menu_mode():
    use_color = True
    print_banner(use_color)

    while True:
        choice = show_menu(use_color)
        if choice == "1":
            await handle_subdomain_menu(use_color)
        elif choice == "2":
            await handle_port_scanner_menu(use_color)
        elif choice == "3":
            await handle_dir_bruteforce_menu(use_color)
        elif choice in ("0", "q", "quit", "exit"):
            print_status("bye", use_color)
            break
        else:
            print_error("invalid choice, pick 1, 2, 3 or 0", use_color)


# ---------------------------------------------------------------------------

async def main():
    # no CLI args -> interactive [1]/[2] menu
    # any CLI args -> original flag-driven subdomain enum (for scripting)
    if len(sys.argv) == 1:
        await run_menu_mode()
    else:
        args = parse_args()
        await run_cli_mode(args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_error("interrupted", True)
        sys.exit(1)
