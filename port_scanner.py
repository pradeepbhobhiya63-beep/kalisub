"""
port_scanner - simple async TCP connect-scanner for kalisub
"""

import asyncio

from utils import print_status, color

# top ~20 commonly open / interesting ports (used when user picks "common")
COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139,
    143, 443, 445, 993, 995, 1723, 3306, 3389, 5900, 8080,
]

# a few well-known service names for nicer output (not exhaustive)
SERVICE_NAMES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
    1723: "pptp", 3306: "mysql", 3389: "rdp", 5900: "vnc", 8080: "http-alt",
}


def parse_port_spec(spec: str):
    """
    Parse a port spec string into a sorted list of ints.
    Accepts: "common" / "" -> COMMON_PORTS
             "1-1000"      -> range
             "22,80,443"   -> explicit list
             "22,80,1000-2000" -> mixed
    """
    spec = (spec or "").strip().lower()
    if spec in ("", "common", "top", "default"):
        return list(COMMON_PORTS)

    ports = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            ports.update(range(min(start, end), max(start, end) + 1))
        else:
            ports.add(int(part))
    return sorted(p for p in ports if 0 < p < 65536)


async def _scan_one(host: str, port: int, timeout: float) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def scan_ports(
    host: str,
    ports,
    concurrency: int = 200,
    timeout: float = 1.0,
    use_color: bool = True,
    silent: bool = False,
) -> list:
    """
    Scan `ports` on `host` concurrently (bounded by `concurrency`).
    Returns a sorted list of open ports. Prints each open port as it's found
    unless silent=True.
    """
    sem = asyncio.Semaphore(concurrency)
    open_ports = []

    async def worker(port):
        async with sem:
            if await _scan_one(host, port, timeout):
                open_ports.append(port)
                if not silent:
                    svc = SERVICE_NAMES.get(port, "")
                    label = f"{host}:{port}" + (f" ({svc})" if svc else "")
                    print_status(color(f"open  {label}", "green", use_color), use_color)

    await asyncio.gather(*(worker(p) for p in ports))
    return sorted(open_ports)
