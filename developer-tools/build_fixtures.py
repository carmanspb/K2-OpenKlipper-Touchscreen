#!/usr/bin/env python3
"""Refresh preview copies of production artwork and rasterize SVG fixtures."""

import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
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
    # The reviewed CFS illustration is a production PNG, not an SVG export.
    # Copy it so regenerating fixtures cannot restore the old illustration.
    shutil.copyfile(ASSETS.parents[2] / "assets/printer-with-cfs.png", ASSETS / "demo-printer-combo.png")
    tree = ET.parse(ASSETS.parents[2] / "assets/printer.svg")
    root = tree.getroot()
    root.remove(next(child for child in root if child.get("id") == "cfs"))
    with tempfile.TemporaryDirectory(prefix="native-fixture-art-") as directory:
        source = Path(directory) / "printer.svg"
        tree.write(source, encoding="unicode")
        render(source, ASSETS / "demo-printer-only.png")
        render(source, ASSETS.parents[2] / "assets/printer-without-cfs.png")


if __name__ == "__main__":
    main()
