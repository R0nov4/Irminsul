#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
waybar_edit.py — surgical editor for the Waybar `custom/weather` module.

Edits ONLY the `on-click` key inside the `custom/weather` object of a
JSONC file (strings, // and /* */ comments are respected). Nothing else
in the file is touched, so other modules are never modified.

usage:
  waybar_edit.py set <config.jsonc> <command>   add or update on-click
  waybar_edit.py remove <config.jsonc>          remove on-click key
  waybar_edit.py get <config.jsonc>             print current value or ""

exit codes: 0 ok/unchanged · 1 file or block missing · 2 usage
"""
import json
import re
import sys
from pathlib import Path

MODULE_KEY = "custom/weather"
ONCLICK_KEY = "on-click"


def scan_block(src: str, key: str):
    """Return (start, end) indices of the { ... } block for the module
    DEFINITION of "key" (skips bare string references in module arrays)."""
    pat = re.compile(r'"' + re.escape(key) + r'"')
    for m in pat.finditer(src):
        i = skip_ws_comments(src, m.end())
        if i >= len(src) or src[i] != ":":
            continue                      # e.g. "custom/weather", in an array
        j = skip_ws_comments(src, i + 1)
        if j >= len(src) or src[j] != "{":
            continue
        return match_braces(src, j)
    return None


def match_braces(src: str, j: int):
    """Brace-match from the '{' at index j, respecting strings & comments."""
    depth = 0
    in_str = in_line = in_blk = esc = False
    k = j
    while k < len(src):
        c = src[k]
        nxt = src[k + 1] if k + 1 < len(src) else ""
        if in_line:
            if c == "\n":
                in_line = False
        elif in_blk:
            if c == "*" and nxt == "/":
                in_blk = False
                k += 1
        elif in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "/" and nxt == "/":
                in_line = True
                k += 1
            elif c == "/" and nxt == "*":
                in_blk = True
                k += 1
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return (j, k + 1)
        k += 1
    return None


def skip_ws_comments(src: str, i: int):
    """Skip whitespace and comments starting at i."""
    while i < len(src):
        c = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if c in " \t\r\n":
            i += 1
        elif c == "/" and nxt == "/":
            j = src.find("\n", i)
            i = len(src) if j < 0 else j + 1
        elif c == "/" and nxt == "*":
            j = src.find("*/", i)
            i = len(src) if j < 0 else j + 2
        else:
            break
    return i


def find_onclick(src: str, block: tuple):
    """Return (key_start, value_start, value_end) for on-click in the block."""
    bs, be = block
    seg = src[bs:be]
    m = re.search(r'"' + ONCLICK_KEY + r'"', seg)
    if not m:
        return None
    key_start = bs + m.start()
    i = skip_ws_comments(src, bs + m.end())
    if i >= len(src) or src[i] != ":":
        return None
    i = skip_ws_comments(src, i + 1)
    if i >= len(src) or src[i] != '"':
        return None            # non-string value — refuse to touch
    j = i + 1
    while j < len(src):
        if src[j] == "\\":
            j += 2
            continue
        if src[j] == '"':
            break
        j += 1
    return (key_start, i, j + 1)   # value includes quotes


def cmd_set(path: Path, command: str) -> int:
    src = path.read_text(encoding="utf-8")
    block = scan_block(src, MODULE_KEY)
    if block is None:
        print(json.dumps({"ok": False, "error": "module block not found"}))
        return 1

    found = find_onclick(src, block)
    if found:
        _, vs, ve = found
        old = src[vs + 1:ve - 1]
        if old == command:
            print(json.dumps({"ok": True, "changed": False, "previous": old}))
            return 0
        new_src = src[:vs + 1] + command + src[ve - 1:]
        path.write_text(new_src, encoding="utf-8")
        print(json.dumps({"ok": True, "changed": True, "previous": old}))
        return 0

    # insert as the LAST key of the block (keeps the closing brace layout)
    bs, be = block
    close = src.rfind("}", bs, be)
    inner = src[bs + 1:close].rstrip()
    tail_ws = src[bs + 1 + len(inner):close]      # original whitespace before '}'
    indent_match = re.search(r'\n([ \t]*)"[^"]+"\s*:', src[bs:be])
    indent = "\n" + (indent_match.group(1) if indent_match else "        ")
    if inner == "" or inner.endswith(","):
        insertion = indent + '"%s": "%s"' % (ONCLICK_KEY, command) + tail_ws
    else:
        insertion = "," + indent + '"%s": "%s"' % (ONCLICK_KEY, command) + tail_ws
    new_src = src[:bs + 1 + len(inner)] + insertion + src[close:]
    path.write_text(new_src, encoding="utf-8")
    print(json.dumps({"ok": True, "changed": True, "previous": None}))
    return 0


def cmd_remove(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    block = scan_block(src, MODULE_KEY)
    if block is None:
        print(json.dumps({"ok": False, "error": "module block not found"}))
        return 1
    found = find_onclick(src, block)
    if not found:
        print(json.dumps({"ok": True, "changed": False}))
        return 0
    ks, vs, ve = found
    # expand left to include preceding comma/whitespace
    i = ks
    while i > 0 and src[i - 1] in " \t\r\n":
        i -= 1
    leading_comma = i > 0 and src[i - 1] == ","
    if leading_comma:
        i -= 1
    # expand right past trailing comma
    j = skip_ws_comments(src, ve)
    trailing_comma = j < len(src) and src[j] == ","
    if trailing_comma:
        j += 1
        while j < len(src) and src[j] in " \t\r\n":
            j += 1
    if not leading_comma and not trailing_comma:
        # only key in the object — just delete the key/value
        pass
    new_src = src[:i] + src[j:]
    path.write_text(new_src, encoding="utf-8")
    print(json.dumps({"ok": True, "changed": True}))
    return 0


def cmd_get(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    block = scan_block(src, MODULE_KEY)
    if block is None:
        print(json.dumps({"ok": False, "error": "module block not found"}))
        return 1
    found = find_onclick(src, block)
    val = src[found[1] + 1:found[2] - 1] if found else ""
    print(json.dumps({"ok": True, "value": val}))
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, cfg = argv[1], Path(argv[2])
    if not cfg.is_file():
        print(json.dumps({"ok": False, "error": f"file not found: {cfg}"}))
        return 1
    if mode == "set" and len(argv) >= 4:
        return cmd_set(cfg, argv[3])
    if mode == "remove":
        return cmd_remove(cfg)
    if mode == "get":
        return cmd_get(cfg)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
