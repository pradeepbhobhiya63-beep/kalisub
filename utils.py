import sys

BANNER = r"""
  _         _ _           _     
| | ____ _| (_)___ _   _| |__  
| |/ / _` | | / __| | | | '_ \ 
|   < (_| | | \__ \ |_| | |_) |
|_|\_\__,_|_|_|___/\__,_|_.__/

     subdomain enumeration
"""

COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def color(text: str, name: str, use_color: bool = True) -> str:
    if not use_color:
        return text
    return f"{COLORS.get(name, '')}{text}{COLORS['reset']}"


def print_banner(use_color: bool = True):
    print(color(BANNER, "cyan", use_color), file=sys.stderr)


def print_status(msg: str, use_color: bool = True):
    print(color(f"[*] {msg}", "yellow", use_color), file=sys.stderr)


def print_error(msg: str, use_color: bool = True):
    print(color(f"[!] {msg}", "red", use_color), file=sys.stderr)
