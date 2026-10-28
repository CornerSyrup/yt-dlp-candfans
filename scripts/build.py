"""Reproducible offline plugin archive; no third-party build dependencies."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def build(destination: Path | None = None) -> Path:
    root = Path(__file__).resolve().parents[1]
    destination = destination or root / 'dist' / 'yt-dlp-candfans.zip'
    files = sorted((root / 'yt_dlp_plugins' / 'extractor').glob('*.py'))
    if not files:
        raise SystemExit('No extractor source found')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            if file.name.startswith('_'):
                continue
            info = zipfile.ZipInfo(file.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3  # Fixed Unix metadata, including on Windows.
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, file.read_bytes(), compresslevel=9)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(build(args.output).resolve())
