"""live runner の実機オフライン統合テスト専用ヘルパー。

生成した 1 秒の映像・音声・画像と、通信を禁止する fixture transport のみを
使います。実際の Windows EXE / FFmpeg / ffprobe を動かしますが、インストール
や live API/CDN へのアクセスは行いません。本番 runner にテストモードは追加しません。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('verify_live', Path(__file__).with_name('verify_live.py'))
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)

TRANSPORT = r'''
import io
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from yt_dlp import YoutubeDL
from yt_dlp.networking.common import Response
__all__ = []
_root = Path(os.environ['CANDFANS_OFFLINE_MEDIA_ROOT'])

def _open(self, request):
    url = request if isinstance(request, str) else request.url
    parsed = urlsplit(url)
    if parsed.hostname == 'candfans.jp' and parsed.path == '/api/contents/get-timeline':
        query = parse_qs(parsed.query)
        assert query.get('user_id') == ['100001']
        assert query.get('post_type[]') == ['1']
        page = query.get('page')
        assert page in (['1'], ['2'])
        body = {'status': 'SUCCESS', 'data': [post(42, 100001)] if page == ['1'] else []}
        payload, kind = json.dumps(body).encode(), 'application/json'
    elif parsed.hostname == 'candfans.jp' and parsed.path in (
            '/api/contents/get-timeline/42', '/api/contents/get-timeline/974904'):
        post_id = int(parsed.path.rsplit('/', 1)[1])
        body = {'status': 'SUCCESS', 'data': {'post': post(post_id, 100001 if post_id == 42 else 200001)}}
        payload, kind = json.dumps(body).encode(), 'application/json'
    elif url == 'https://media.example.invalid/master.m3u8':
        payload, kind = (_root / 'master.m3u8').read_bytes(), 'application/vnd.apple.mpegurl'
    elif url == 'https://images.example.invalid/thumbnail.jpg':
        payload, kind = (_root / 'thumbnail.jpg').read_bytes(), 'image/jpeg'
    elif parsed.hostname == 'media.example.invalid' and parsed.path == '/segment000.ts' and not parsed.query:
        payload, kind = (_root / 'segment000.ts').read_bytes(), 'video/mp2t'
    else:
        raise AssertionError('Offline integration rejected an unexpected network request')
    return Response(io.BytesIO(payload), url, {'Content-Type': kind, 'Content-Length': str(len(payload))})

def post(post_id, creator):
    return {'post_id': post_id, 'user_id': creator, 'user_code': 'offline_creator' if creator == 100001 else 'other_creator',
            'username': 'Offline test creator', 'title': 'Generated offline integration media',
            'contents_text': 'Synthetic video and audio only', 'can_browsing': 1, 'is_downloadable': False,
            'movie_time': 1, 'thumbnail_file': 'https://images.example.invalid/thumbnail.jpg',
            'attachments': [{'default': 'https://media.example.invalid/master.m3u8'}]}
YoutubeDL.urlopen = _open
'''


def run(executable, archive, output, ffmpeg_location=None):
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg, ffprobe = live.media_tools(ffmpeg_location)
    original_command = live.command
    with tempfile.TemporaryDirectory(prefix='live-offline-', dir=output.parent) as temp:
        fixtures = Path(temp)
        original_command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                          'color=c=blue:s=160x90:r=10', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                          '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                          '-f', 'hls', '-hls_time', '1', '-hls_list_size', '0',
                          '-hls_segment_filename', fixtures / 'segment%03d.ts', fixtures / 'master.m3u8'], timeout=90)
        original_command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                          'color=c=red:s=160x90', '-frames:v', '1', '-q:v', '2', fixtures / 'thumbnail.jpg'], timeout=90)
        cookies = fixtures / 'cookies.txt'
        cookies.write_text('# Netscape HTTP Cookie File\n', encoding='utf-8')
        def offline_command(args, **kwargs):
            if '--plugin-dirs' in args:
                plugins = Path(args[args.index('--plugin-dirs') + 1])
                with zipfile.ZipFile(plugins / 'offline-test-only-transport.zip', 'w') as helper:
                    helper.writestr('yt_dlp_plugins/extractor/zz_candfans_offline_transport.py', TRANSPORT)
                kwargs['env'] = dict(kwargs['env'], CANDFANS_OFFLINE_MEDIA_ROOT=str(fixtures))
            return original_command(args, **kwargs)
        with patch.object(live, 'command', offline_command):
            result = live.run(executable, archive, cookies, 'https://candfans.jp/offline_creator',
                              'https://candfans.jp/posts/comment/show/974904', output,
                              ffmpeg_location=ffmpeg_location, user_id='100001')
    result['scope'] = 'offline_integration_real_exe_and_media_tools_generated_media_only'
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg-location')
    args = parser.parse_args()
    raise SystemExit(run(args.exe.resolve(), args.zip.resolve(), args.output.resolve(), args.ffmpeg_location))
