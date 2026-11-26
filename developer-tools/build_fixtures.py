#!/usr/bin/env python3
"""Refresh preview copies of production artwork and rasterize SVG fixtures."""

import shutil
import subprocess
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "fixtures/assets"


def render(source, destination):
    subprocess.run(
        [
            "convert",
            "-background",
            "none",
            str(source),
            "-trim",
            "+repage",
            "-strip",
            "PNG32:" + str(destination),
        ],
        check=True,
    )


def main():
    render(ASSETS / "demo-part.svg", ASSETS / "demo-part.png")
    render(ASSETS / "demo-part-dark.svg", ASSETS / "demo-part-dark.png")
    # Production PNGs are the reviewed pair; preview generation must not
    # replace either illustration with an older SVG export.
    for source, target in (("printer-with-cfs.png", "demo-printer-combo.png"),
                           ("printer-without-cfs.png", "demo-printer-only.png")):
        shutil.copyfile(ASSETS.parents[2] / "assets" / source, ASSETS / target)


if __name__ == "__main__":
    main()
