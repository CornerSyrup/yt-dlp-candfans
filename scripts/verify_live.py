"""実際の API と CDN を使う、秘密情報を保存しない Windows EXE 検証。

既存の実行ファイルのみを使用し、インストールは行いません。個人ページは
先頭の投稿の最初の動画、別のクリエイターの単一投稿は全添付動画を全編ダウンロードします。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
from urllib.parse import urlsplit


class VerificationError(Exception):
    """公開しても秘密情報を含まない固定エラーコード。"""


def validate_urls(creator_url, post_url):
    for value, kind in ((creator_url, 'creator'), (post_url, 'post')):
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.netloc != 'candfans.jp'
                or parsed.query or parsed.fragment):
            raise VerificationError('invalid_' + kind + '_url')
        pattern = r'/[A-Za-z0-9_][A-Za-z0-9_.-]*/?' if kind == 'creator' else r'/posts/comment/show/[1-9][0-9]*/?'
        if not re.fullmatch(pattern, parsed.path):
            raise VerificationError('invalid_' + kind + '_url')
    if urlsplit(creator_url).path.strip('/') in {'api', 'posts', 'login', 'settings'}:
        raise VerificationError('invalid_creator_url')


def run_process(args, *, timeout, env=None):
    """タイムアウト時は FFmpeg を含む子プロセスツリーも終了させます。"""
    windows = os.name == 'nt'
    process = subprocess.Popen(list(map(str, args)), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, encoding='utf-8', errors='replace',
                               env=env, start_new_session=not windows)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if windows:
                # 親を先に終了すると Windows が子の関連付けを失うため、ツリーを先に終了します。
                try:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=30, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
        finally:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                # ツリー終了が OS に拒否された場合も、継承された pipe を待ち続けません。
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None:
                        pipe.close()
                process.wait(timeout=30)
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def command(args, *, timeout, env=None):
    try:
        result = run_process(args, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise VerificationError('command_timeout') from None
    except OSError:
        raise VerificationError('command_unavailable') from None
    if result.returncode:
        # stdout/stderr は URL、署名、Cookie を含む可能性があるため公開しません。
        statuses = sorted(set(re.findall(r'HTTP Error ([1-5][0-9]{2})', result.stderr or '')))
        suffix = '_http_' + '_'.join(statuses) if statuses else ''
        raise VerificationError('command_failed_exit_' + str(result.returncode) + suffix)
    return result


def media_tools(location=None):
    if location:
        target = Path(location)
        directory = target if target.is_dir() else target.parent
        suffix = '.exe' if os.name == 'nt' else ''
        tools = [directory / ('ffmpeg' + suffix), directory / ('ffprobe' + suffix)]
        if not all(tool.is_file() for tool in tools):
            raise VerificationError('media_tools_missing')
        return tuple(map(str, tools))
    tools = tuple(shutil.which(name) for name in ('ffmpeg', 'ffprobe'))
    if not all(tools):
        raise VerificationError('media_tools_missing')
    return tools


def verify_video(video, metadata, ffmpeg, ffprobe):
    try:
        probe = json.loads(command([ffprobe, '-v', 'error', '-show_streams',
                                   '-show_format', '-of', 'json', video], timeout=120).stdout)
        streams = probe['streams']
        main = [s for s in streams if s.get('codec_type') == 'video'
                and not s.get('disposition', {}).get('attached_pic')]
        audio = [s for s in streams if s.get('codec_type') == 'audio']
        covers = [s for s in streams if s.get('disposition', {}).get('attached_pic') == 1]
        duration = float(probe['format']['duration'])
        expected = float(metadata['duration'])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise VerificationError('invalid_media_metadata') from None
    if len(main) != 1 or not audio or len(covers) != 1:
        raise VerificationError('missing_video_audio_or_cover')
    if 'mp4' not in probe['format'].get('format_name', ''):
        raise VerificationError('unexpected_container')
    if not all(math.isfinite(v) and v > 0 for v in (duration, expected)):
        raise VerificationError('invalid_duration')
    # HLS のタイムベース差を許容しつつ、短いプレビューへの置換を検出します。
    if abs(duration - expected) > max(3.0, expected * .005):
        raise VerificationError('duration_mismatch')
    command([ffmpeg, '-v', 'error', '-xerror', '-i', video,
             '-map', '0:' + str(main[0]['index']), '-map', '0:a', '-f', 'null', '-'], timeout=1200)
    command([ffmpeg, '-v', 'error', '-xerror', '-i', video,
             '-map', '0:' + str(covers[0]['index']), '-frames:v', '1', '-f', 'null', '-'], timeout=120)
    return {'duration_seconds': duration, 'expected_duration_seconds': expected,
            'full_decode': True, 'audio_present': True, 'attached_pic': True,
            'cover_decode': True, 'video_codec': main[0].get('codec_name'),
            'audio_codecs': [s.get('codec_name') for s in audio],
            'cover_codec': covers[0].get('codec_name')}


def run(executable, archive, cookie_file, creator_url, post_url, output,
        *, ffmpeg_location=None, user_id=None):
    validate_urls(creator_url, post_url)
    if user_id is not None and not re.fullmatch(r'[1-9][0-9]*', user_id):
        raise VerificationError('invalid_user_id')
    if not all(Path(p).is_file() for p in (executable, archive, cookie_file)):
        raise VerificationError('required_file_missing')
    ffmpeg, ffprobe = media_tools(ffmpeg_location)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'live_api_and_cdn', 'profile_item_limit': 1,
              'plugin_sha256': hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
              'passed': False, 'cases': []}
    env = os.environ.copy()
    env.pop('YTDLP_NO_PLUGINS', None)
    for secret_name in ('CANDFANS_COOKIES', 'CANDFANS_CREATOR_URL',
                        'CANDFANS_POST_URL', 'CANDFANS_CREATOR_ID'):
        env.pop(secret_name, None)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    try:
        with tempfile.TemporaryDirectory(prefix='candfans-live-', dir=output.parent) as temp:
            scratch = Path(temp)
            plugins = scratch / 'plugins'
            plugins.mkdir()
            shutil.copyfile(archive, plugins / 'yt-dlp-candfans.zip')
            creators = []
            for name, url in (('creator', creator_url), ('post', post_url)):
                case = {'case': name, 'passed': False}
                report['cases'].append(case)
                folder = scratch / name
                folder.mkdir()
                args = [executable, '--ignore-config', '--encoding', 'utf-8', '--no-plugin-dirs',
                        '--plugin-dirs', plugins, '--no-cache-dir', '--no-progress', '--no-warnings',
                        '--cookies', cookie_file, '--abort-on-unavailable-fragments', '--retries', '3',
                        '--fragment-retries', '3', '--socket-timeout', '30', '--embed-thumbnail',
                        '--remux-video', 'mp4', '--write-info-json', '--ffmpeg-location', ffmpeg,
                        '--windows-filenames', '-o', str(folder / '%(id)s.%(ext)s')]
                if name == 'creator':
                    args += ['--playlist-end', '1']
                    if user_id:
                        args += ['--extractor-args', 'candfansprofile:user_id=' + user_id]
                command(args + [url], timeout=1200, env=env)
                videos = sorted(folder.glob('*.mp4'))
                if not videos:
                    raise VerificationError('no_downloaded_video')
                case['videos'] = []
                for video in videos:
                    try:
                        metadata = json.loads(video.with_suffix('.info.json').read_text(encoding='utf-8'))
                        creator_id = str(metadata['uploader_id'])
                    except (OSError, KeyError, TypeError, json.JSONDecodeError):
                        raise VerificationError('missing_download_metadata') from None
                    if not re.fullmatch(r'[1-9][0-9]*', creator_id):
                        raise VerificationError('invalid_creator_metadata')
                    creators.append((name, creator_id))
                    case['videos'].append(verify_video(video, metadata, ffmpeg, ffprobe))
                case['passed'] = True
            if {identity for name, identity in creators if name == 'creator'} & {
                    identity for name, identity in creators if name == 'post'}:
                raise VerificationError('post_creator_must_differ')
            report['distinct_creators_verified'] = True
            report['passed'] = True
    except VerificationError as error:
        report['failure'] = str(error)
    except OSError:
        report['failure'] = 'local_io_error'
    finally:
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--cookie-file', type=Path, required=True)
    parser.add_argument('--creator-url', required=True)
    parser.add_argument('--post-url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ffmpeg-location')
    parser.add_argument('--user-id')
    args = parser.parse_args()
    try:
        report = run(args.exe.resolve(), args.zip.resolve(), args.cookie_file.resolve(),
                     args.creator_url, args.post_url, args.output.resolve(),
                     ffmpeg_location=args.ffmpeg_location, user_id=args.user_id)
    except VerificationError as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
