"""live runner 自体のオフライン回帰テスト。通信やインストールは行いません。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('verify_live', Path(__file__).resolve().parents[1] / 'scripts' / 'verify_live.py')
live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live)
CREATOR = 'https://candfans.jp/example_creator'
POST = 'https://candfans.jp/posts/comment/show/42'


def completed(stdout='', stderr='', code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def probe(duration=10, cover=True, audio=True):
    streams = [{'index': 2, 'codec_type': 'video', 'codec_name': 'h264'}]
    if audio:
        streams.append({'index': 4, 'codec_type': 'audio', 'codec_name': 'aac'})
    if cover:
        streams.append({'index': 7, 'codec_type': 'video', 'codec_name': 'png', 'disposition': {'attached_pic': 1}})
    return json.dumps({'streams': streams, 'format': {'duration': str(duration), 'format_name': 'mov,mp4,m4a,3gp,3g2,mj2'}})


class LiveRunnerTests(unittest.TestCase):
    def temporary_directory(self):
        root = Path(__file__).resolve().parents[1] / '.test-tmp'
        root.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def test_url_validation_rejects_external_or_ambiguous_inputs(self):
        live.validate_urls(CREATOR, POST)
        live.validate_urls('https://candfans.jp/creator.name-with_dash', POST)
        for creator, post in [('http://candfans.jp/x', POST), ('https://candfans.jp.evil.invalid/x', POST),
                              ('https://candfans.jp/api', POST), (CREATOR + '?token=private', POST),
                              (CREATOR, 'https://candfans.jp/posts/comment/show/0'),
                              (CREATOR, POST + '#private')]:
            with self.subTest(creator=creator, post=post), self.assertRaises(live.VerificationError):
                live.validate_urls(creator, post)

    def test_http_failure_keeps_only_status_not_sensitive_diagnostics(self):
        with patch.object(live, 'run_process', return_value=completed(
                stderr='HTTP Error 403: https://private.invalid/?token=secret Cookie: private', code=1)):
            with self.assertRaises(live.VerificationError) as error:
                live.command(['exe', '--cookies', 'private'], timeout=1)
        self.assertEqual(str(error.exception), 'command_failed_exit_1_http_403')

    def test_timeout_is_failure_not_success(self):
        with patch.object(live, 'run_process', side_effect=subprocess.TimeoutExpired(['private'], 1)):
            with self.assertRaisesRegex(live.VerificationError, '^command_timeout$'):
                live.command(['exe'], timeout=1)

    def test_full_media_and_cover_decode_use_actual_stream_indices(self):
        command = Mock(side_effect=[completed(probe()), completed(), completed()])
        with patch.object(live, 'command', command):
            result = live.verify_video(Path('private.mp4'), {'duration': 10}, 'ffmpeg', 'ffprobe')
        self.assertTrue(result['full_decode'])
        self.assertTrue(result['cover_decode'])
        main_args = command.call_args_list[1].args[0]
        cover_args = command.call_args_list[2].args[0]
        self.assertIn('0:2', main_args)
        self.assertIn('0:a', main_args)
        self.assertIn('0:7', cover_args)
        self.assertIn('-xerror', main_args)

    def test_missing_cover_audio_or_complete_duration_fails(self):
        for body, expected in [(probe(cover=False), 'missing_video_audio_or_cover'),
                               (probe(audio=False), 'missing_video_audio_or_cover'),
                               (probe(duration=4), 'duration_mismatch')]:
            with self.subTest(expected=expected), patch.object(live, 'command', return_value=completed(body)):
                with self.assertRaisesRegex(live.VerificationError, '^' + expected + '$'):
                    live.verify_video(Path('private.mp4'), {'duration': 10}, 'ffmpeg', 'ffprobe')

    def run_fixture(self, *, same_creator=False, empty=False, failed=False, missing_identity=False):
        with self.temporary_directory() as temp:
            root = Path(temp)
            exe, archive, cookies = [root / name for name in ('yt-dlp.exe', 'plugin.zip', 'cookies.txt')]
            for item in (exe, archive, cookies):
                item.write_bytes(b'private-test-input')
            seen = []
            folders = []
            def command(args, **kwargs):
                for key in ('CANDFANS_COOKIES', 'CANDFANS_CREATOR_URL', 'CANDFANS_POST_URL', 'CANDFANS_CREATOR_ID'):
                    self.assertNotIn(key, kwargs['env'])
                seen.append(args)
                if failed:
                    raise live.VerificationError('command_failed_exit_1_http_403')
                folder = Path(args[args.index('-o') + 1]).parent
                folders.append(folder)
                if not empty:
                    (folder / 'opaque.mp4').write_bytes(b'test-media')
                    identity = '100' if len(seen) == 1 or same_creator else '200'
                    metadata = {'duration': 10}
                    if not missing_identity:
                        metadata['uploader_id'] = identity
                    (folder / 'opaque.info.json').write_text(json.dumps(metadata))
                return completed()
            with patch.dict(live.os.environ, {key: 'sensitive-value' for key in (
                    'CANDFANS_COOKIES', 'CANDFANS_CREATOR_URL', 'CANDFANS_POST_URL', 'CANDFANS_CREATOR_ID')}), \
                    patch.object(live, 'media_tools', return_value=('ffmpeg', 'ffprobe')), \
                    patch.object(live, 'command', side_effect=command), \
                    patch.object(live, 'verify_video', return_value={'full_decode': True, 'attached_pic': True}):
                report = live.run(exe, archive, cookies, CREATOR, POST, root / 'report', user_id='100')
            saved = (root / 'report' / 'summary.json').read_text()
            self.assertEqual(json.loads(saved), report)
            self.assertNotIn(CREATOR, saved)
            self.assertNotIn(POST, saved)
            self.assertNotIn('private-test-input', saved)
            self.assertNotIn('uploader_id', saved)
            self.assertTrue(all(not folder.exists() for folder in folders))
            self.assertEqual([path.name for path in (root / 'report').iterdir()], ['summary.json'])
            return report, seen

    def test_two_real_download_commands_bounded_profile_and_distinct_creators(self):
        report, calls = self.run_fixture()
        self.assertTrue(report['passed'])
        self.assertTrue(report['distinct_creators_verified'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][-1], CREATOR)
        self.assertEqual(calls[1][-1], POST)
        self.assertIn('--playlist-end', calls[0])
        self.assertNotIn('--playlist-end', calls[1])
        self.assertIn('candfansprofile:user_id=100', calls[0])
        for args in calls:
            for option in ('--no-plugin-dirs', '--cookies', '--abort-on-unavailable-fragments',
                           '--embed-thumbnail', '--write-info-json'):
                self.assertIn(option, args)
            self.assertNotIn('--ignore-errors', args)
            self.assertNotIn('--skip-download', args)

    def test_same_creator_is_explicit_failure(self):
        report, _ = self.run_fixture(same_creator=True)
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure'], 'post_creator_must_differ')

    def test_empty_successful_cli_is_not_a_successful_download(self):
        report, calls = self.run_fixture(empty=True)
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure'], 'no_downloaded_video')
        self.assertEqual(len(calls), 1)

    def test_failed_download_has_safe_report_and_does_not_continue(self):
        report, calls = self.run_fixture(failed=True)
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure'], 'command_failed_exit_1_http_403')
        self.assertEqual(len(calls), 1)

    def test_missing_creator_identity_is_explicit_failure(self):
        report, calls = self.run_fixture(missing_identity=True)
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure'], 'missing_download_metadata')
        self.assertEqual(len(calls), 1)

    def test_decode_failure_is_propagated(self):
        with patch.object(live, 'command', side_effect=[completed(probe()),
                live.VerificationError('command_failed_exit_1')]):
            with self.assertRaisesRegex(live.VerificationError, '^command_failed_exit_1$'):
                live.verify_video(Path('private.mp4'), {'duration': 10}, 'ffmpeg', 'ffprobe')

    def test_windows_timeout_kills_tree_before_parent_and_reaps_without_logging(self):
        events = []
        process = Mock(pid=1234)
        def communicate(**kwargs):
            events.append('communicate')
            if kwargs.get('timeout') == 1:
                raise subprocess.TimeoutExpired(['private-token'], 1)
            return ('private-output', 'private-cookie')
        process.communicate.side_effect = communicate
        process.kill.side_effect = lambda: events.append('parent-kill')
        def taskkill(args, **kwargs):
            events.append('tree-kill')
            self.assertEqual(args, ['taskkill', '/PID', '1234', '/T', '/F'])
            self.assertIs(kwargs['stdout'], subprocess.DEVNULL)
            self.assertIs(kwargs['stderr'], subprocess.DEVNULL)
            return completed()
        with patch.object(live.os, 'name', 'nt'), \
                patch.object(live.subprocess, 'Popen', return_value=process), \
                patch.object(live.subprocess, 'run', side_effect=taskkill):
            with self.assertRaisesRegex(live.VerificationError, '^command_timeout$'):
                live.command(['private-exe', 'private-token'], timeout=1)
        self.assertEqual(events, ['communicate', 'tree-kill', 'parent-kill', 'communicate'])

    def test_posix_timeout_kills_new_process_group_and_reaps(self):
        process = Mock(pid=1234)
        process.communicate.side_effect = [subprocess.TimeoutExpired(['private'], 1), ('', '')]
        with patch.object(live.os, 'name', 'posix'), \
                patch.object(live.subprocess, 'Popen', return_value=process) as popen, \
                patch.object(live.os, 'killpg', create=True) as killpg, \
                patch.object(live.signal, 'SIGKILL', 9, create=True):
            with self.assertRaisesRegex(live.VerificationError, '^command_timeout$'):
                live.command(['private-exe'], timeout=1)
        self.assertIs(popen.call_args.kwargs['start_new_session'], True)
        killpg.assert_called_once_with(1234, 9)
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)

    def test_failed_tree_cleanup_cannot_wait_forever_on_inherited_pipes(self):
        process = Mock(pid=1234)
        process.communicate.side_effect = [subprocess.TimeoutExpired(['private'], 1),
                                           subprocess.TimeoutExpired(['private'], 30)]
        with patch.object(live.os, 'name', 'nt'), \
                patch.object(live.subprocess, 'Popen', return_value=process), \
                patch.object(live.subprocess, 'run', side_effect=OSError('private diagnostics')):
            with self.assertRaisesRegex(live.VerificationError, '^command_timeout$'):
                live.command(['private-exe'], timeout=1)
        process.stdout.close.assert_called_once()
        process.stderr.close.assert_called_once()
        process.wait.assert_called_once_with(timeout=30)
