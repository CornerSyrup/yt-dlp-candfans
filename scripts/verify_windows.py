"""Offline official-EXE ZIP/CLI smoke tests; no installation or live requests.

The temporary test-only transport replaces YoutubeDL.urlopen, and rejects every
request except fixture API routes and synthetic .invalid manifests. It is never
included in yt-dlp-candfans.zip. Pass an existing Windows yt-dlp.exe explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


TRANSPORT = r'''
import io
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from yt_dlp import YoutubeDL
from yt_dlp.networking.common import Response

__all__ = []
_root = Path(os.environ['CANDFANS_TEST_ROOT'])
_mode = os.environ['CANDFANS_TEST_MODE']

def _fixture_open(self, request):
    url = request if isinstance(request, str) else request.url
    parsed = urlsplit(url)
    if parsed.hostname == 'candfans.jp' and parsed.path == '/api/contents/get-timeline/974904':
        body = json.loads((_root / 'post_974904_sanitised.json').read_text(encoding='utf-8'))
        if _mode == 'allowed':
            post = body['data']['post']
            post.update(is_downloadable=True, title='Synthetic permitted offline test',
                        contents_text='Synthetic permission and manifest; no live evidence.',
                        attachments=[{'default': 'https://media.example.invalid/test/master.m3u8'}],
                        post_attachments=[])
        payload = json.dumps(body).encode()
        content_type = 'application/json'
    elif parsed.hostname == 'candfans.jp' and parsed.path == '/api/contents/get-timeline':
        query = parse_qs(parsed.query)
        assert query.get('user_id') == ['100001'], 'Unexpected creator'
        assert query.get('post_type[]') == ['1'], 'Unexpected timeline filter'
        page = query.get('page')
        assert page in (['1'], ['2']), 'Unexpected pagination'
        name = 'timeline_page_sanitised.json' if page == ['1'] else 'timeline_empty.json'
        payload = (_root / name).read_bytes()
        content_type = 'application/json'
    elif _mode == 'allowed' and url == 'https://media.example.invalid/test/master.m3u8':
        payload = (b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720\n'
                   b'720.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=300000,RESOLUTION=640x360\n360.m3u8\n')
        content_type = 'application/vnd.apple.mpegurl'
    else:
        raise AssertionError('Offline smoke blocked an unexpected request')
    with (_root / 'requests.jsonl').open('a', encoding='utf-8') as log:
        log.write(json.dumps({'mode': _mode, 'url': url}) + '\n')
    return Response(io.BytesIO(payload), url, {'Content-Type': content_type})

YoutubeDL.urlopen = _fixture_open
'''


def run(executable: Path, archive: Path, destination: Path):
    source = Path(__file__).resolve().parents[1]
    destination.mkdir(parents=True, exist_ok=True)
    report = {
        'scope': 'Offline fixtures only; no CandFans live/authenticated requests',
        'executable': str(executable),
        'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        'plugin_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'checks': [],
    }
    # Workspace-local scratch keeps tests independent of protected system Temp.
    with tempfile.TemporaryDirectory(prefix='windows-smoke-', dir=destination) as temp:
        scratch = Path(temp)
        plugins = scratch / 'plugins'
        plugins.mkdir()
        (plugins / 'yt-dlp-candfans.zip').write_bytes(archive.read_bytes())
        payload_root = scratch / 'fixtures'
        payload_root.mkdir()
        for name in ('post_974904_sanitised.json', 'timeline_page_sanitised.json', 'timeline_empty.json'):
            (payload_root / name).write_bytes((source / 'tests' / 'fixtures' / name).read_bytes())
        env = os.environ.copy()
        env.pop('YTDLP_NO_PLUGINS', None)
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        base = [str(executable), '--ignore-config', '--encoding', 'utf-8',
                '--no-plugin-dirs', '--plugin-dirs', str(plugins)]

        def invoke(name, options, mode='sanitised', expected=0):
            env['CANDFANS_TEST_ROOT'] = str(payload_root)
            env['CANDFANS_TEST_MODE'] = mode
            completed = subprocess.run(base + options, capture_output=True, env=env, timeout=60)
            # Early CLI branches such as --list-extractors may still use the
            # runner's code page before the --encoding option is applied.
            completed.stdout = completed.stdout.decode('utf-8', errors='replace')
            completed.stderr = completed.stderr.decode('utf-8', errors='replace')
            (destination / f'{name}.stdout.txt').write_text(completed.stdout, encoding='utf-8')
            (destination / f'{name}.stderr.txt').write_text(completed.stderr, encoding='utf-8')
            assert completed.returncode == expected, f'{name}: exit {completed.returncode}; inspect stderr'
            report['checks'].append({'name': name, 'exit_code': completed.returncode, 'passed': True})
            return completed

        # First discover the production ZIP by itself, without any test helper.
        listed = invoke('list-extractors', ['--verbose', '--list-extractors'])
        report['list_extractors_includes_plugins'] = all(
            name in listed.stdout for name in ('CandFansPost', 'CandFansProfile'))
        # 2026.08.19 prints --list-extractors before loading plugins. Verify the
        # real loader with local information only; this cannot request a site.
        local_info = scratch / 'loader-info.json'
        local_info.write_text(json.dumps({
            'id': 'offline-loader', 'title': 'Offline loader check', 'formats': [],
        }), encoding='utf-8')
        discovered = invoke('zip-discovery', [
            '--verbose', '--simulate', '--ignore-no-formats-error',
            '--load-info-json', str(local_info)])
        assert 'CandFansPostIE' in discovered.stderr and 'CandFansProfileIE' in discovered.stderr
        assert 'yt-dlp-candfans.zip' in discovered.stderr
        report['version'] = invoke('version', ['--version']).stdout.strip()

        with zipfile.ZipFile(plugins / 'fixture-transport.zip', 'w') as helper:
            helper.writestr('yt_dlp_plugins/extractor/zz_candfans_fixture_transport.py', TRANSPORT)

        post_url = 'https://candfans.jp/posts/comment/show/974904'
        common = ['--skip-download', '--dump-json', '--no-warnings', '-N', '8', '-c',
                  '--download-archive', str(scratch / 'archive.txt'), '--remux-video', 'mp4']
        metadata = invoke('metadata-only-sanitised', common + [
            '--ignore-no-formats-error', '--extractor-args', 'candfanspost:metadata_only=true', post_url])
        parsed = json.loads(metadata.stdout)
        expected_post = json.loads((payload_root / 'post_974904_sanitised.json').read_text(encoding='utf-8'))['data']['post']
        assert parsed['title'] == expected_post['title'], 'Unicode metadata was not preserved'
        assert parsed['id'] == '974904' and parsed['duration'] == 1947
        assert parsed['timestamp'] == 1749654958 and parsed['upload_date'] == '20250611'
        assert not parsed.get('formats') and not parsed.get('thumbnail')
        assert 'media.example.invalid' not in metadata.stdout

        blocked = invoke('permission-false-blocked', common + [post_url], expected=1)
        assert 'is_downloadable' in blocked.stderr

        allowed = invoke('synthetic-hls-dry-run', common + [post_url], mode='allowed')
        parsed = json.loads(allowed.stdout)
        assert {item['height'] for item in parsed['formats']} == {360, 720}
        assert all('.invalid' in item['url'] for item in parsed['formats'])

        profile = invoke('profile-flat-sanitised', [
            '--flat-playlist', '--dump-single-json', '--no-warnings',
            '--extractor-args', 'candfansprofile:user_id=100001',
            'https://candfans.jp/example_creator'])
        parsed = json.loads(profile.stdout)
        assert [entry['id'] for entry in parsed['entries']] == [
            '832491', '832478', '832465', '832461', '832159', '832156', '832053', '832050', '832036']
        requests = [json.loads(line) for line in (payload_root / 'requests.jsonl').read_text().splitlines()]
        assert len(requests) == 6, f'Unexpected number of fixture requests: {len(requests)}'
        assert sum('.invalid' in request['url'] for request in requests) == 1
        report['request_count'] = len(requests)
        report['requests'] = requests

    (destination / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'version': report['version'], 'passed': len(report['checks']),
                      'fixture_requests': report['request_count']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True, help='Existing official Windows yt-dlp.exe')
    parser.add_argument('--zip', type=Path, default=Path(__file__).resolve().parents[1] / 'dist' / 'yt-dlp-candfans.zip')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.exe.resolve(), args.zip.resolve(), args.output.resolve())
