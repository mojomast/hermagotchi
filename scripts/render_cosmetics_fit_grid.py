#!/usr/bin/env python3
"""Render the launch-003 cosmetic fit grid (10 species x representative slots).

Usage:
    python3 scripts/render_cosmetics_fit_grid.py --out assets/preview/cosmetics_fit_grid_v2.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from asset_px3_compose import FIT_GRID_ITEMS, render_fit_grid  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(HERE.parent / "assets" / "preview" / "cosmetics_fit_grid_v2.png"),
        help="PNG output path",
    )
    parser.add_argument("--cell", type=int, default=160, help="cell size in pixels")
    args = parser.parse_args(argv)
    path = render_fit_grid(args.out, cell=args.cell, items=FIT_GRID_ITEMS)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
