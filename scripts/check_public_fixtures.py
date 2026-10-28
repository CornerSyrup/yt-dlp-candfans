"""Fail if public fixture data regains real media URLs or credential fields.

This is a narrow regression guard for the curated public fixtures, not a general
secret detector. Real endpoint strings in production code are outside its scope.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


EXPECTED = {
    'auth_unauthenticated_minimal.json', 'fixture_inventory.json',
    'post_974904_sanitised.json', 'timeline_empty.json', 'timeline_page_sanitised.json',
}
SENSITIVE_KEY = re.compile(
    r'(?:^|_)(?:cookies?|session(?:id)?|authorization|password|access_token|refresh_token|csrf|xsrf)(?:$|_)',
    re.IGNORECASE)
URL = re.compile(r'https?://[^\s"<>]+', re.IGNORECASE)


def inspect_value(value, location):
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY.search(key) and child not in (None, '', {}, []):
                raise SystemExit(f'Credential-like field found in fixture at {location}.{key}')
            inspect_value(child, f'{location}.{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            inspect_value(child, f'{location}[{index}]')
    elif isinstance(value, str):
        for match in URL.finditer(value):
            try:
                host = urlsplit(match.group()).hostname or ''
            except ValueError:
                raise SystemExit(f'Malformed URL in fixture at {location}') from None
            if not (host == 'invalid' or host.endswith('.invalid')):
                # Deliberately print only the field location, never its value.
                raise SystemExit(f'Non-reserved absolute URL found in fixture at {location}')


def check(root: Path):
    actual = {path.name for path in root.glob('*.json')}
    if actual != EXPECTED:
        raise SystemExit(f'Unexpected public fixture inventory: {sorted(actual)}')
    fixtures = {}
    for name in sorted(actual):
        fixtures[name] = json.loads((root / name).read_text(encoding='utf-8'))
        inspect_value(fixtures[name], name)
    inventory = fixtures['fixture_inventory.json']
    evidence = inventory.get('source', '').lower()
    if 'sanitised' not in evidence or 'not live-verified' not in evidence:
        raise SystemExit('Fixture inventory must disclose sanitised, unverified evidence')
    digest = hashlib.sha256((root / 'timeline_page_sanitised.json').read_bytes()).hexdigest()
    if inventory.get('sha256_of_sanitised_timeline') != digest:
        raise SystemExit('Sanitised timeline checksum does not match its inventory')
    timeline = fixtures['timeline_page_sanitised.json']['data']
    post = fixtures['post_974904_sanitised.json']['data']['post']
    for item in [*timeline, post]:
        if item.get('user_code') != 'example_creator' or item.get('user_id') != 100001:
            raise SystemExit('Fixture creator identity must remain the synthetic example')
        if item.get('is_downloadable') is not False:
            raise SystemExit('Evidence fixtures must preserve the observed false download flag')
    print(f'Public fixture guard passed: {len(fixtures)} JSON files; reserved URLs and synthetic creator only')


if __name__ == '__main__':
    check(Path(__file__).resolve().parents[1] / 'tests' / 'fixtures')
