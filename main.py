#!/usr/bin/env python3
"""
kalisub - multi-source subdomain enumeration tool
Usage:
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
from utils import print_banner, print_status, print_error, color


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


async def main():
    args = parse_args()
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_error("interrupted", True)
        sys.exit(1)
