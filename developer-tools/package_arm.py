#!/usr/bin/env python3
"""Assemble a versioned ARM runtime package from an already completed build."""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "installation"))
from validate_package import fingerprint, source_inputs, validate


def copy_png(source, destination):
    """Copy PNG chunks verbatim except build-time timestamp metadata."""
    data = source.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG signature: {source}")
    output = bytearray(data[:8])
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError(f"Truncated PNG chunk: {source}")
        timestamp = kind == b"tIME"
        if kind in (b"tEXt", b"zTXt", b"iTXt"):
            keyword = data[offset + 8:offset + 8 + length].split(b"\0", 1)[0].lower()
            timestamp = keyword.startswith(b"date:") or keyword in (b"creation time", b"modification time")
        if not timestamp:
            output.extend(data[offset:end])
        offset = end
        if kind == b"IEND":
            if length or offset != len(data):
                raise ValueError(f"Invalid PNG end: {source}")
            destination.write_bytes(output)
            return
    raise ValueError(f"Missing PNG end: {source}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "out/arm")
    parser.add_argument("--integration-root", type=Path, help="K2-OpenKlipper checkout when building the standalone touchscreen repository")
    args = parser.parse_args()
    integration = args.integration_root.resolve() if args.integration_root else REPO
    component_repo = ROOT if args.integration_root else REPO
    binary = args.build / "openklipper-screen"
    header = binary.read_bytes()[:20]
    if (
        header[:6] != b"\x7fELF\x01\x01"
        or struct.unpack_from("<H", header, 18)[0] != 40
    ):
        raise SystemExit("Expected a 32-bit little-endian ARM executable")
    revision = subprocess.check_output(
        ["git", "-C", str(component_repo), "rev-parse", "HEAD"], text=True
    ).strip()
    inputs = source_inputs(ROOT, integration)
    for name, digest in inputs.items():
        context_file = name in ("VERSION", "install.sh")
        repo = integration if context_file else component_repo
        git_path = name.removeprefix("touchscreen/") if args.integration_root and not context_file else name
        recorded = subprocess.run(
            ["git", "-C", str(repo), "show", "HEAD:" + git_path], capture_output=True, check=False
        )
        if recorded.returncode or hashlib.sha256(recorded.stdout).hexdigest() != digest:
            raise SystemExit(
                "Commit build/runtime source inputs before packaging: " + name
            )
    package = ROOT / "precompiled/armv7"
    if package.exists():
        shutil.rmtree(package)
    (package / "assets").mkdir(parents=True)
    (package / "licenses").mkdir()
    shutil.copy2(binary, package / binary.name)
    (package / binary.name).chmod(0o755)
    for source in (ROOT / "assets/generated").glob("*.png"):
        copy_png(source, package / "assets" / source.name)
    for source in (ROOT / "assets").glob("printer-*.png"):
        copy_png(source, package / "assets" / source.name)
    shutil.copy2(ROOT / "LICENSE", package / "licenses/Touchscreen-LICENSE")
    for source in (ROOT / "assets").glob("*-LICENSE"):
        shutil.copy2(source, package / "licenses" / source.name)
    for source in (args.build / "licenses").glob("*"):
        shutil.copy2(source, package / "licenses" / source.name)
    if (
        not (package / "licenses/LVGL-LICENSE").exists()
        or not (package / "licenses/cJSON-LICENSE").exists()
    ):
        raise SystemExit(
            "Dependency licences missing; reconfigure CMake before packaging"
        )
    digest = fingerprint(inputs)
    version = (integration / "VERSION").read_text().strip() + "+native." + digest[:12]
    (package / "VERSION").write_text(version + "\n")
    manifest = {
        "format": 1,
        "built_from_commit": revision,
        "source_inputs": inputs,
        "source_fingerprint": digest,
        "target": "armv7-linux-gnueabihf",
        "files": {},
    }
    for source in sorted(package.rglob("*")):
        if source.is_file():
            manifest["files"][str(source.relative_to(package))] = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validate(ROOT, package, integration)
    print(package)


if __name__ == "__main__":
    main()
