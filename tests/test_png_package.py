"""Package metadata normalization must preserve encoded image content."""

import importlib.util
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("arm_packager", ROOT / "developer-tools/package_arm.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def chunks(data):
    offset = 8
    result = []
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        result.append((data[offset + 4:offset + 8], data[offset:offset + length + 12]))
        offset += length + 12
    return result


class PngPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def image(self, name, timestamp):
        path = self.folder / name
        image = Image.new("RGBA", (3, 2), (17, 51, 81, 100))
        image.putpixel((1, 1), (222, 7, 192, 0))
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("date:create", timestamp)
        metadata.add_text("date:modify", timestamp, zip=True)
        metadata.add_itxt("date:timestamp", timestamp)
        metadata.add_text("Description", "Keep this metadata")
        image.save(path, pnginfo=metadata, dpi=(192, 192))
        return path

    def test_only_time_metadata_changes_and_encoded_pixels_are_preserved(self):
        source = self.image("source.png", "2026-11-27T01:00:00Z")
        original = source.read_bytes()
        target = self.folder / "target.png"
        packager.copy_png(source, target)
        self.assertEqual(source.read_bytes(), original)
        before, after = Image.open(io.BytesIO(original)), Image.open(target)
        self.assertEqual(before.tobytes(), after.tobytes())
        self.assertEqual(after.info["Description"], before.info["Description"])
        self.assertEqual(after.info["dpi"], before.info["dpi"])
        self.assertFalse(any(key.startswith("date:") for key in after.info))
        encoded = lambda data: [chunk for kind, chunk in chunks(data) if kind in (b"IHDR", b"IDAT", b"IEND", b"pHYs")]
        self.assertEqual(encoded(original), encoded(target.read_bytes()))

    def test_different_build_dates_produce_identical_package_bytes(self):
        first = self.image("first.png", "2026-11-27T01:00:00Z")
        second = self.image("second.png", "2026-11-27T09:00:00Z")
        one, two = self.folder / "one.png", self.folder / "two.png"
        packager.copy_png(first, one)
        packager.copy_png(second, two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        again = self.folder / "again.png"
        packager.copy_png(one, again)
        self.assertEqual(one.read_bytes(), again.read_bytes())

    def test_binary_timestamp_chunk_is_removed(self):
        source = self.image("source.png", "2026-11-27")
        data = source.read_bytes()
        payload = b"tIME" + struct.pack(">H5B", 2026, 11, 27, 1, 2, 3)
        chunk = struct.pack(">I", 7) + payload + struct.pack(">I", zlib.crc32(payload))
        source.write_bytes(data[:33] + chunk + data[33:])
        target = self.folder / "target.png"
        packager.copy_png(source, target)
        self.assertNotIn(b"tIME", [kind for kind, _ in chunks(target.read_bytes())])
        self.assertEqual(Image.open(source).tobytes(), Image.open(target).tobytes())

    def test_malformed_png_does_not_write_a_package_asset(self):
        source, target = self.folder / "bad.png", self.folder / "target.png"
        for data in (b"not a PNG", b"\x89PNG\r\n\x1a\n", b"\x89PNG\r\n\x1a\n\x00\x00\x00\x20IDATxxxx"):
            with self.subTest(data=data):
                source.write_bytes(data)
                with self.assertRaises(ValueError):
                    packager.copy_png(source, target)
                self.assertFalse(target.exists())
