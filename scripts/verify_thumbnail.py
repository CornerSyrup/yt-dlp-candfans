"""Exercise native thumbnail download and MP4 cover embedding, wholly offline.

Requires an existing official Windows yt-dlp.exe, FFmpeg and ffprobe. Installs
nothing. Only generated colour frames are used. A temporary test-only plugin
intercepts all URL requests and rejects any route absent from the test fixture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


TRANSPORT = r'''
import io
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from yt_dlp import YoutubeDL
from yt_dlp.networking.common import Response

__all__ = []
_root = Path(os.environ['CANDFANS_THUMBNAIL_TEST_ROOT'])

def _fixture_open(self, request):
    url = request if isinstance(request, str) else request.url
    if url == 'https://candfans.jp/api/contents/get-timeline/974904':
        payload = json.dumps({'status': 'SUCCESS', 'data': {'post': {
            'post_id': 974904, 'user_id': 100001,
            'user_code': 'synthetic_creator', 'username': 'Synthetic creator',
            'title': 'Offline thumbnail embedding test', 'contents_text': 'Generated colour clip only.',
            'can_browsing': 1, 'is_downloadable': False,
            'thumbnail_file': '/user/100001/post/974904/thumbnail.jpg',
            'attachments': [{'default': 'https://media.example.invalid/master.m3u8'}],
        }}}).encode()
        content_type = 'application/json'
    elif url == 'https://images.example.invalid/user/100001/post/974904/thumbnail.jpg':
        payload = (_root / 'thumbnail.jpg').read_bytes()
        content_type = 'image/jpeg'
    elif url == 'https://media.example.invalid/master.m3u8':
        payload = (_root / 'master.m3u8').read_bytes()
        content_type = 'application/vnd.apple.mpegurl'
    elif urlsplit(url).hostname == 'media.example.invalid' and urlsplit(url).path.startswith('/segment'):
        name = urlsplit(url).path.removeprefix('/')
        if '/' in name or not name.endswith('.ts') or not (_root / name).is_file():
            raise AssertionError('Unexpected synthetic segment')
        payload = (_root / name).read_bytes()
        content_type = 'video/mp2t'
    else:
        raise AssertionError('Offline thumbnail test blocked an unexpected request')
    with (_root / 'requests.jsonl').open('a', encoding='utf-8') as log:
        log.write(json.dumps({'url': url}) + '\n')
    return Response(io.BytesIO(payload), url, {
        'Content-Type': content_type, 'Content-Length': str(len(payload)),
    })

YoutubeDL.urlopen = _fixture_open
'''


def command(args, *, env=None):
    completed = subprocess.run(list(map(str, args)), capture_output=True, text=True,
                               encoding='utf-8', env=env, timeout=90)
    if completed.returncode:
        raise RuntimeError(f'Command exited {completed.returncode}: {completed.stderr}')
    return completed


def run(executable: Path, archive: Path, ffmpeg: str, ffprobe: str, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='thumbnail-test-', dir=destination) as temp:
        scratch = Path(temp)
        fixtures = scratch / 'fixtures'
        fixtures.mkdir()
        command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                 'color=c=blue:s=160x90:r=10', '-t', '1', '-c:v', 'libx264', '-pix_fmt',
                 'yuv420p', '-f', 'hls', '-hls_time', '1', '-hls_list_size', '0',
                 '-hls_segment_filename', fixtures / 'segment%03d.ts', fixtures / 'master.m3u8'])
        command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                 'color=c=red:s=160x90', '-frames:v', '1', '-q:v', '2', fixtures / 'thumbnail.jpg'])
        plugins = scratch / 'plugins'
        plugins.mkdir()
        (plugins / 'yt-dlp-candfans.zip').write_bytes(archive.read_bytes())
        with zipfile.ZipFile(plugins / 'thumbnail-test-transport.zip', 'w') as helper:
            helper.writestr('yt_dlp_plugins/extractor/zz_candfans_thumbnail_transport.py', TRANSPORT)
        env = os.environ.copy()
        env.pop('YTDLP_NO_PLUGINS', None)
        env['CANDFANS_THUMBNAIL_TEST_ROOT'] = str(fixtures)
        output_video = destination / 'synthetic-thumbnail-demo.mp4'
        # Force overwrite applies only to this script's explicitly named generated demo.
        completed = command([
            executable, '--ignore-config', '--no-plugin-dirs', '--plugin-dirs', plugins,
            '--no-cache-dir', '--no-progress', '--no-mtime', '--force-overwrites',
            '--extractor-args', 'candfanspost:thumbnail_origin=https://images.example.invalid',
            '--embed-thumbnail', '--remux-video', 'mp4', '--ffmpeg-location', ffmpeg,
            '-o', output_video, 'https://candfans.jp/posts/comment/show/974904',
        ], env=env)
        (destination / 'thumbnail-embed.stdout.txt').write_text(completed.stdout, encoding='utf-8')
        (destination / 'thumbnail-embed.stderr.txt').write_text(completed.stderr, encoding='utf-8')
        probe = json.loads(command([
            ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', output_video,
        ]).stdout)
        covers = [stream for stream in probe['streams'] if stream.get('disposition', {}).get('attached_pic') == 1]
        videos = [stream for stream in probe['streams'] if stream.get('codec_type') == 'video'
                  and not stream.get('disposition', {}).get('attached_pic')]
        assert len(covers) == 1 and len(videos) == 1, 'Expected one video and one attached cover'
        assert 'mp4' in probe['format']['format_name'], 'Expected an actual MP4 container'
        extracted_cover = destination / 'embedded-cover.jpg'
        command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', output_video,
                 '-map', f'0:{covers[0]["index"]}', '-c', 'copy', '-frames:v', '1', extracted_cover])
        original_hash = hashlib.sha256((fixtures / 'thumbnail.jpg').read_bytes()).hexdigest()
        embedded_hash = hashlib.sha256(extracted_cover.read_bytes()).hexdigest()
        assert original_hash == embedded_hash, 'Embedded cover differs from the supplied JPEG'
        requests = [json.loads(line) for line in (fixtures / 'requests.jsonl').read_text().splitlines()]
        assert any('images.example.invalid' in item['url'] for item in requests)
        report = {
            'scope': 'Offline synthetic media and thumbnail only; no CandFans live verification',
            'executable_version': command([executable, '--ignore-config', '--version']).stdout.strip(),
            'plugin_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'video': output_video.name, 'video_codec': videos[0]['codec_name'],
            'cover_codec': covers[0]['codec_name'], 'attached_pic': True,
            'cover_bytes_equal': True, 'cover_sha256': original_hash,
            'request_count': len(requests), 'requests': requests,
        }
        (destination / 'thumbnail-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (destination / 'thumbnail-ffprobe.json').write_text(json.dumps(probe, indent=2), encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key != 'requests'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--zip', type=Path, default=Path(__file__).resolve().parents[1] / 'dist' / 'yt-dlp-candfans.zip')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ffmpeg = shutil.which(args.ffmpeg)
    ffprobe = shutil.which(args.ffprobe)
    if not ffmpeg or not ffprobe:
        parser.error('Existing FFmpeg and ffprobe are required; this script does not install them')
    run(args.exe.resolve(), args.zip.resolve(), ffmpeg, ffprobe, args.output.resolve())
