#!/usr/bin/env python3
"""svg-check: inspect SVG research figures and report what a reviewer checks by eye.

Standard library only. The script reads each SVG with xml.etree and reports
the facts that research-figures/SKILL.md and references/design-patterns.md
ask you to check before delivery: the viewBox, embedded raster images, text
that was converted to paths, the number of font families, the spread of font
sizes, colors outside the default palette, the number of non-neutral colors,
and text placed outside the viewBox. It cannot judge whether the figure says
the right thing, whether the data are current, or whether a font license is
kept.

The default palette comes from design-patterns.md "Default visual parameters". It is a
starting point, not a rule: pass --palette "#hex,#hex" for a brand palette or
--no-palette to skip the palette comparison.

Usage:
    svg-check.py [--summary] [--json] [--baseline N] [--disable rule1,rule2]
                 [--palette "#hex,#hex,..."] [--no-palette]
                 PATH [PATH ...]        (files, or directories searched for *.svg)
    svg-check.py --list-rules
    svg-check.py --selftest

--summary prints a per-file summary (viewBox, element counts, fonts, font
sizes, colors) whether or not there are findings.

Exit status: 1 when hard findings exceed --baseline, 0 otherwise.
Advisory findings never change the exit status.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

HARD, ADV = "hard", "advisory"

SKILL = "research-figures/SKILL.md"
DP = "research-figures/references/design-patterns.md"

DEFAULT_PALETTE = ["#22333A", "#596971", "#5B748C", "#267F6B", "#A76B3B", "#B86B68",
                   "#DFE6EA", "#F4F7FA", "#FCFAF7", "#F2F8F5"]
MAX_FONTS = 2
MAX_SIZE_RATIO = 4.0
MIN_FONT_PX = 8.0
SMALL_CANVAS = 1200
MAX_COLORS = 8
NEUTRAL_SPREAD = 12
MANY_PATHS = 20

# rule id -> (severity, source, message)
RULES = {
    "svg-parse": (HARD, SKILL + " > Export and acceptance (if rendering fails, fix it or state the limitation)",
                  "The SVG does not parse as XML. Fix the file, then check it again."),
    "viewbox": (HARD, SKILL + " > Visual decisions > Design for the final size",
                "The root element has no viewBox. Without a viewBox, the figure cannot be checked at the paper column width or the README width."),
    "title-desc": (ADV, SKILL + " > Export and acceptance (self-contained SVG)",
                   "Missing <title> or <desc>. A self-contained SVG carries a title and a one-sentence description for the README and for screen readers."),
    "raster-embed": (HARD, SKILL + " > Build and modify, step 2; references/sprout.md",
                     "Vector first. Do not deliver a PNG as the editable figure (SKILL.md, sprout.md)."),
    "text-as-paths": (ADV, SKILL + " > Export and acceptance (separate live-text SVG from text-as-paths SVG)",
                      "The text may be converted to paths. Keep a version with editable text."),
    "font-count": (ADV, SKILL + " > Visual decisions > Give the text a hierarchy; " + DP + " > Default visual parameters",
                   "More than %d font families. The default is one font for text and one monospace font for code." % MAX_FONTS),
    "font-size-spread": (ADV, DP + " > Default visual parameters",
                         "Set the font sizes for the target print size. Do not take the canvas px as the final paper font size."),
    "palette": (ADV, DP + " > Default visual parameters",
                "These colors are not in the default palette. The palette is a starting point, not a rule. The user's brand colors take priority."),
    "color-count": (ADV, DP + " > Common failures and targeted fixes",
                    "More than %d non-neutral colors. When everything has a color block, keep only the main hierarchy. Group the secondary explanations with normal text and space."
                    % MAX_COLORS),
    "text-outside-viewbox": (ADV, SKILL + " > Export and acceptance (clipped text, edge margins, page boundary)",
                             "The text coordinates are outside the viewBox. This check ignores transform. If a parent element has a transform, confirm by eye."),
}

HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
CSS_DECL = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;}]+)")
NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    severity: str
    message: str
    excerpt: str


@dataclass
class Info:
    """Facts collected from one SVG."""
    file: str
    viewbox: tuple = ()            # (minx, miny, w, h) or ()
    width: str = ""
    height: str = ""
    counts: dict = None            # tag -> count
    has_title: bool = False
    has_desc: bool = False
    rasters: list = None           # href values of raster images
    fonts: dict = None             # first family -> count
    sizes: list = None             # font sizes in px
    colors: dict = None            # #rrggbb -> count
    outside: list = None           # (x, y, text excerpt)


def _local(tag):
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else tag


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _size_px(value):
    """Convert a font-size string to px. Returns None for units it cannot resolve."""
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*([a-z%]*)\s*$", value or "", re.I)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).lower()
    if unit in ("", "px"):
        return n
    if unit == "pt":
        return n * 4.0 / 3.0
    return None


def _first_family(stack):
    fam = stack.split(",")[0].strip().strip("'\"").strip()
    return fam or None


def _norm_color(value):
    """Normalize a color token to #rrggbb, or return None."""
    if value is None:
        return None
    v = value.strip().lower()
    m = RGB.match(v)
    if m:
        return "#%02x%02x%02x" % tuple(min(int(x), 255) for x in m.groups())
    m = HEX.match(v)
    if not m or m.end() != len(v):
        return None
    h = v[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def _is_neutral(color):
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return max(r, g, b) - min(r, g, b) <= NEUTRAL_SPREAD


def _decls(style):
    return {k.strip().lower(): v.strip() for k, v in CSS_DECL.findall(style or "")}


def inspect_svg(text, filename="<svg>"):
    """Parse an SVG string and collect the facts that the rules use."""
    root = ET.fromstring(text)
    info = Info(filename, counts={}, rasters=[], fonts={}, sizes=[], colors={}, outside=[])
    vb = root.get("viewBox")
    if vb:
        parts = [_num(p) for p in vb.replace(",", " ").split()]
        if len(parts) == 4 and all(p is not None for p in parts):
            info.viewbox = tuple(parts)
    info.width, info.height = root.get("width", ""), root.get("height", "")

    def add_color(v):
        c = _norm_color(v)
        if c:
            info.colors[c] = info.colors.get(c, 0) + 1

    def add_font(v):
        f = _first_family(v)
        if f:
            info.fonts[f] = info.fonts.get(f, 0) + 1

    def add_size(v):
        px = _size_px(v)
        if px is not None and px > 0:
            info.sizes.append(px)

    for el in root.iter():
        tag = _local(el.tag)
        info.counts[tag] = info.counts.get(tag, 0) + 1
        if tag == "title":
            info.has_title = True
        if tag == "desc":
            info.has_desc = True
        if tag == "style" and el.text:
            for k, v in CSS_DECL.findall(el.text):
                k = k.strip().lower()
                if k in ("fill", "stroke", "stop-color"):
                    add_color(v)
                elif k == "font-family":
                    add_font(v)
                elif k == "font-size":
                    add_size(v)
            continue
        if tag == "image":
            href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href") or ""
            low = href.lower()
            if low.startswith("data:image/") or low.endswith((".png", ".jpg", ".jpeg")):
                info.rasters.append(href if len(href) <= 60 else href[:57] + "...")
        for attr in ("fill", "stroke", "stop-color"):
            add_color(el.get(attr))
        if el.get("font-family"):
            add_font(el.get("font-family"))
        if el.get("font-size"):
            add_size(el.get("font-size"))
        decls = _decls(el.get("style"))
        for k in ("fill", "stroke", "stop-color"):
            if k in decls:
                add_color(decls[k])
        if "font-family" in decls:
            add_font(decls["font-family"])
        if "font-size" in decls:
            add_size(decls["font-size"])
        if tag == "text" and info.viewbox:
            x = el.get("x", "").split()[0] if el.get("x") else None
            y = el.get("y", "").split()[0] if el.get("y") else None
            if x and y and NUMBER.match(x) and NUMBER.match(y):
                xf, yf = float(x), float(y)
                minx, miny, w, h = info.viewbox
                if xf < minx or xf > minx + w or yf < miny or yf > miny + h:
                    excerpt = "".join(el.itertext()).strip()
                    info.outside.append((xf, yf, excerpt[:40]))
    return info


def lint(info, disabled=(), palette=None):
    """Apply the rules to an Info. palette=None disables the palette rule."""
    findings = []

    def emit(rule, excerpt, extra=""):
        if rule in disabled:
            return
        sev, _, msg = RULES[rule]
        if extra:
            msg = msg + " " + extra
        findings.append(Finding(info.file, 1, 1, rule, sev, msg, excerpt))

    if not info.viewbox:
        emit("viewbox", "viewBox=%r" % (info.viewbox or None))
    if not (info.has_title and info.has_desc):
        missing = [t for t, ok in (("<title>", info.has_title), ("<desc>", info.has_desc)) if not ok]
        emit("title-desc", "missing " + " and ".join(missing))
    for href in info.rasters:
        emit("raster-embed", href)
    n_text, n_path = info.counts.get("text", 0), info.counts.get("path", 0)
    if n_text == 0 and n_path > MANY_PATHS:
        emit("text-as-paths", "text 0, path %d" % n_path)
    if len(info.fonts) > MAX_FONTS:
        emit("font-count", ", ".join(sorted(info.fonts)), "%d families." % len(info.fonts))
    if info.sizes:
        lo, hi = min(info.sizes), max(info.sizes)
        vbw = info.viewbox[2] if info.viewbox else None
        reasons = []
        if hi / lo > MAX_SIZE_RATIO:
            reasons.append("max/min font size ratio %.1f exceeds %g" % (hi / lo, MAX_SIZE_RATIO))
        if lo < MIN_FONT_PX and vbw is not None and vbw < SMALL_CANVAS:
            reasons.append("smallest font size %g px is under %g px (viewBox width %g)" % (lo, MIN_FONT_PX, vbw))
        if reasons:
            emit("font-size-spread", "min %g px, max %g px" % (lo, hi), "；".join(reasons) + "。")
    colored = {c: n for c, n in info.colors.items() if c not in ("#ffffff", "#000000")}
    if palette is not None:
        pal = {_norm_color(p) for p in palette}
        off = {c: n for c, n in colored.items() if c not in pal}
        if off:
            listed = ", ".join("%s x%d" % (c, n) for c, n in sorted(off.items(), key=lambda kv: -kv[1]))
            emit("palette", listed, "%d colors." % len(off))
    non_neutral = [c for c in colored if not _is_neutral(c)]
    if len(non_neutral) > MAX_COLORS:
        emit("color-count", ", ".join(sorted(non_neutral)), "%d colors." % len(non_neutral))
    for x, y, excerpt in info.outside:
        emit("text-outside-viewbox", "x=%g y=%g %r" % (x, y, excerpt))
    return findings


def summary(info, palette=None):
    """Return the per-file summary as a list of lines."""
    lines = [info.file]
    if info.viewbox:
        minx, miny, w, h = info.viewbox
        lines.append("  viewBox: %g %g %g %g (%g x %g)" % (minx, miny, w, h, w, h)
                     + ("; width=%s height=%s" % (info.width, info.height) if info.width or info.height else ""))
    else:
        lines.append("  viewBox: none" + ("; width=%s height=%s" % (info.width, info.height)
                                         if info.width or info.height else ""))
    lines.append("  elements: " + ", ".join("%s %d" % (t, info.counts.get(t, 0))
                                             for t in ("text", "path", "rect", "g", "image")))
    if info.fonts:
        lines.append("  fonts: " + ", ".join("%s (x%d)" % (f, n) for f, n in
                                             sorted(info.fonts.items(), key=lambda kv: -kv[1])))
    else:
        lines.append("  fonts: none declared")
    if info.sizes:
        distinct = sorted(set(info.sizes))
        lines.append("  font sizes: %g to %g px (%s)" % (min(info.sizes), max(info.sizes),
                                                        ", ".join("%g" % s for s in distinct)))
    else:
        lines.append("  font sizes: none declared")
    colored = {c: n for c, n in info.colors.items() if c not in ("#ffffff", "#000000")}
    non_neutral = sorted(c for c in colored if not _is_neutral(c))
    lines.append("  colors: %d distinct (%d non-neutral), white/black not counted" % (len(colored), len(non_neutral)))
    for c, n in sorted(colored.items(), key=lambda kv: (-kv[1], kv[0])):
        tag = ""
        if palette is not None:
            tag = " palette" if c in {_norm_color(p) for p in palette} else " off-palette"
        lines.append("    %s x%d%s%s" % (c, n, " neutral" if _is_neutral(c) else "", tag))
    if info.rasters:
        lines.append("  raster images: " + ", ".join(info.rasters))
    if info.outside:
        lines.append("  text outside viewBox: %d" % len(info.outside))
    return lines


def check_file(path, disabled=(), palette=None, want_summary=False):
    try:
        with open(path, encoding="utf-8") as fh:
            info = inspect_svg(fh.read(), path)
    except (ET.ParseError, OSError, UnicodeDecodeError) as exc:
        if want_summary:
            print("%s\n  (not parsed: %s)" % (path, exc))
        if "svg-parse" in disabled:
            return []
        return [Finding(path, 1, 1, "svg-parse", HARD, RULES["svg-parse"][2], str(exc))]
    if want_summary:
        print("\n".join(summary(info, palette)))
    return lint(info, disabled, palette)


# ----------------------------------------------------------------------------- cli

def report(findings, as_json, baseline):
    hard = sum(1 for f in findings if f.severity == HARD)
    adv = len(findings) - hard
    if as_json:
        print(json.dumps({"hard": hard, "advisory": adv, "baseline": baseline,
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print('%s:%d:%d: %s %s: %s  "%s"' % (f.file, f.line, f.col, f.severity, f.rule,
                                                f.message, f.excerpt))
        print("%d hard, %d advisory (baseline %d)" % (hard, adv, baseline))
    return 1 if hard > baseline else 0


def list_rules():
    print("%-22s %-9s %s" % ("rule", "severity", "source"))
    for rid, (sev, src, msg) in RULES.items():
        print("%-22s %-9s %s" % (rid, sev, src))
        print("%-22s %-9s   %s" % ("", "", msg))


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                files += [os.path.join(dirpath, n) for n in sorted(filenames) if n.lower().endswith(".svg")]
        else:
            files.append(p)
    return files


CLEAN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400" role="img">
  <title id="title">Checkpoint and resume</title>
  <desc id="desc">A task runs, saves a checkpoint, fails, and resumes from the checkpoint.</desc>
  <defs>
    <style>
      .label { font-family: Nunito, Arial, sans-serif; font-size: 16px; fill: #22333A; }
      .code { font-family: 'IBM Plex Mono', monospace; font-size: 13px; fill: #596971; }
    </style>
  </defs>
  <rect width="800" height="400" fill="#FCFAF7"/>
  <rect x="40" y="40" width="200" height="80" rx="8" fill="#F4F7FA" stroke="#DFE6EA"/>
  <rect x="300" y="40" width="200" height="80" rx="8" fill="#F2F8F5" stroke="#267F6B"/>
  <path d="M240 80 L300 80" stroke="#5B748C" fill="none"/>
  <text class="label" x="60" y="85">task</text>
  <text class="label" x="320" y="85" font-size="20">resume</text>
  <text class="code" x="60" y="140">run.py</text>
</svg>
"""


def selftest():
    def rules_for(svg, palette=DEFAULT_PALETTE):
        return {f.rule for f in lint(inspect_svg(svg, "case.svg"), palette=palette)}

    cases = [
        # (svg, rules that must appear, rules that must not appear)
        (CLEAN_SVG, set(), set(RULES)),
        (CLEAN_SVG.replace(' viewBox="0 0 800 400"', ""), {"viewbox"}, set()),
        (CLEAN_SVG.replace("<title id=\"title\">Checkpoint and resume</title>", ""), {"title-desc"}, set()),
        (CLEAN_SVG.replace("</svg>", '<image href="data:image/png;base64,AAAA" width="10" height="10"/></svg>'),
         {"raster-embed"}, set()),
        (CLEAN_SVG.replace("</svg>", '<image xmlns:xlink="http://www.w3.org/1999/xlink" '
                           'xlink:href="figure.png" width="10" height="10"/></svg>'),
         {"raster-embed"}, set()),
        (CLEAN_SVG.replace("</svg>", '<image href="icon.svg" width="10" height="10"/></svg>'),
         set(), {"raster-embed"}),
        (re.sub(r"<text.*?</text>", "", CLEAN_SVG).replace(
            "</svg>", '<path d="M0 0 L1 1" stroke="#5B748C"/>' * 25 + "</svg>"),
         {"text-as-paths"}, set()),
        (CLEAN_SVG.replace("</svg>", '<text x="10" y="300" font-family="Georgia, serif">a</text></svg>'),
         {"font-count"}, set()),
        (CLEAN_SVG.replace('font-size="20"', 'font-size="72"'), {"font-size-spread"}, set()),
        (CLEAN_SVG.replace("font-size: 13px", "font-size: 6px"), {"font-size-spread"}, set()),
        (CLEAN_SVG.replace("font-size: 13px", "font-size: 6px").replace(
            'viewBox="0 0 800 400"', 'viewBox="0 0 2400 1200"'), set(), {"font-size-spread"}),
        (CLEAN_SVG.replace("#5B748C", "#FF0000"), {"palette"}, set()),
        (CLEAN_SVG.replace("#5B748C", "rgb(255, 0, 0)"), {"palette"}, set()),
        (CLEAN_SVG.replace("#5B748C", "#ffffff"), set(), {"palette"}),
        (CLEAN_SVG.replace("</svg>", "".join('<rect width="1" height="1" fill="#%02x40%02x"/>' % (i * 20, 200 - i * 20)
                                             for i in range(9)) + "</svg>"),
         {"color-count"}, set()),
        (CLEAN_SVG.replace("</svg>", '<text x="900" y="50" class="label">lost</text></svg>'),
         {"text-outside-viewbox"}, set()),
        (CLEAN_SVG.replace("</svg>", '<text x="10" y="-5" class="label">lost</text></svg>'),
         {"text-outside-viewbox"}, set()),
    ]
    failed = 0
    for k, (svg, must, must_not) in enumerate(cases):
        got = rules_for(svg)
        miss, extra = must - got, must_not & got
        if miss or extra:
            failed += 1
            print("FAIL case %d: missing=%s unexpected=%s got=%s" % (k, sorted(miss), sorted(extra), sorted(got)))
    # palette override and --no-palette
    extra_cases = 0
    extra_cases += 1
    if "palette" in rules_for(CLEAN_SVG.replace("#5B748C", "#FF0000"), palette=["#ff0000"] + DEFAULT_PALETTE):
        failed += 1
        print("FAIL palette override")
    extra_cases += 1
    if "palette" in rules_for(CLEAN_SVG.replace("#5B748C", "#FF0000"), palette=None):
        failed += 1
        print("FAIL --no-palette")
    # parse error through check_file, and a clean file on disk
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "bad.svg")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("<svg><title>x</title>")
        extra_cases += 1
        if {f.rule for f in check_file(bad)} != {"svg-parse"}:
            failed += 1
            print("FAIL svg-parse")
        good = os.path.join(tmp, "good.svg")
        with open(good, "w", encoding="utf-8") as fh:
            fh.write(CLEAN_SVG)
        extra_cases += 1
        if check_file(good, palette=DEFAULT_PALETTE):
            failed += 1
            print("FAIL clean file on disk")
        extra_cases += 1
        if not summary(inspect_svg(CLEAN_SVG, good), DEFAULT_PALETTE):
            failed += 1
            print("FAIL summary")
    total = len(cases) + extra_cases
    print("selftest: %d/%d passed" % (total - failed, total))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inspect SVG research figures and report what a reviewer checks by eye.")
    ap.add_argument("paths", nargs="*", help="SVG files or directories")
    ap.add_argument("--summary", action="store_true", help="print a per-file summary regardless of findings")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", type=int, default=0, help="tolerate N hard findings")
    ap.add_argument("--disable", default="", help="comma-separated rule ids to silence")
    ap.add_argument("--palette", default=None, help='comma-separated hex colors that replace the default palette')
    ap.add_argument("--no-palette", action="store_true", help="skip the palette comparison")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.list_rules:
        list_rules()
        return 0
    if not args.paths:
        ap.error("give at least one SVG file or directory")
    disabled = {d.strip() for d in args.disable.split(",") if d.strip()}
    unknown = disabled - set(RULES)
    if unknown:
        ap.error("unknown rule id(s): %s" % ", ".join(sorted(unknown)))
    palette = None if args.no_palette else list(DEFAULT_PALETTE)
    if args.palette and not args.no_palette:
        palette = [p.strip() for p in args.palette.split(",") if p.strip()]
        bad = [p for p in palette if _norm_color(p) is None]
        if bad:
            ap.error("not a hex color: %s" % ", ".join(bad))
    findings = []
    for path in collect(args.paths):
        findings += check_file(path, disabled, palette, args.summary)
    if args.summary and not args.json:
        print()
    findings.sort(key=lambda f: (f.file, f.rule))
    return report(findings, args.json, args.baseline)


if __name__ == "__main__":
    sys.exit(main())
