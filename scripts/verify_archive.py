"""Validate the installable ZIP, reproducibility and optional SHA256SUMS output.

Uses only the Python standard library. The release asset contains the production
extractor alone; fixtures, test transports and credentials cannot enter the ZIP.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path
import tempfile
import zipfile

from build import build


PAYLOAD = 'yt_dlp_plugins/extractor/candfans.py'


def verify(archive: Path, checksums: Path | None = None) -> str:
    root = Path(__file__).resolve().parents[1]
    archive = archive.resolve()
    with zipfile.ZipFile(archive) as package:
        if package.namelist() != [PAYLOAD]:
            raise SystemExit(f'Unexpected ZIP namespace or extra payload: {package.namelist()}')
        if package.testzip() is not None:
            raise SystemExit('ZIP CRC verification failed')
        source = package.read(PAYLOAD)
    if source != (root / PAYLOAD).read_bytes():
        raise SystemExit('ZIP extractor does not match the checked-out source')
    tree = ast.parse(source.decode('utf-8'))
    public_classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)
                      and not node.name.startswith('_')}
    if public_classes != {'CandFansPostIE', 'CandFansProfileIE'}:
        raise SystemExit(f'Unexpected public extractor classes: {sorted(public_classes)}')
    scratch_parent = root / '.test-tmp'
    scratch_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='candfans-rebuild-', dir=scratch_parent) as directory:
        rebuilt = build(Path(directory) / archive.name)
        if rebuilt.read_bytes() != archive.read_bytes():
            raise SystemExit('Repeated build differs from the supplied ZIP')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksums is not None:
        checksums.parent.mkdir(parents=True, exist_ok=True)
        checksums.write_text(f'{digest}  {archive.name}\n', encoding='utf-8', newline='\n')
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--checksums', type=Path)
    arguments = parser.parse_args()
    print(f'{verify(arguments.archive, arguments.checksums)}  {arguments.archive.name}')
