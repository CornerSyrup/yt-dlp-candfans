"""Offline evidence tests; every unmocked extractor network request is fatal.

Public fixtures are sanitised derivatives of supplied evidence, preserving shapes,
post IDs, timestamps, durations and permission flags, with neutral text and URLs.
Mutated dicts and .invalid manifests below are synthetic, including
is_downloadable=True and user lookup bodies. They are not live API verification.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request
import zipfile

from yt_dlp import YoutubeDL
from yt_dlp.cookies import YoutubeDLCookieJar
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.networking.exceptions import HTTPError
from yt_dlp.networking.common import Response
from yt_dlp.utils import ExtractorError
from yt_dlp_plugins.extractor.candfans import CandFansPostIE, CandFansProfileIE


FIXTURES = Path(__file__).parent / 'fixtures'
POST_URL = 'https://candfans.jp/posts/comment/show/974904'
PROFILE_URL = 'https://candfans.jp/example_creator'
IDS = ['832491', '832478', '832465', '832461', '832159', '832156', '832053', '832050', '832036']


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def synthetic_post(**changes):
    body = fixture('post_974904_sanitised.json')
    body['data']['post'].update({
        'is_downloadable': True,
        'attachments': [{'default': 'https://media.example.invalid/a.m3u8', 'low': None}],
        'post_attachments': [],
    })
    body['data']['post'].update(changes)
    return body


class OfflineCase(unittest.TestCase):
    def setUp(self):
        # Extractor requests not explicitly replaced by a test must never use network.
        self.network = patch.object(InfoExtractor, '_request_webpage', side_effect=AssertionError('Unexpected network request'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.ydl = YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}, auto_init=False)
        self.addCleanup(self.ydl.close)

    def ie(self, cls=CandFansPostIE, args=None):
        if args:
            self.ydl.params['extractor_args'] = args
        return cls(self.ydl)

    def temporary_directory(self):
        # Stay inside the source workspace, including on Windows app sandboxes.
        parent = Path(__file__).resolve().parents[1] / '.test-tmp'
        parent.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=parent)

    def post(self, body, *, args=None, hls=None, url=POST_URL):
        ie = self.ie(args=args)
        ie._download_json = Mock(return_value=copy.deepcopy(body))
        ie._extract_m3u8_formats = Mock(return_value=hls if hls is not None else [{
            'url': 'https://media.example.invalid/variant.m3u8', 'format_id': 'hls-720',
            'ext': 'mp4', 'protocol': 'm3u8_native', 'height': 720,
        }])
        return ie, ie._real_extract(url)

    def profile(self, pages, *, lookup=None, args=None):
        ie = self.ie(CandFansProfileIE, args=args)
        pages = copy.deepcopy(pages)
        lookup = lookup if lookup is not None else {'status': 'SUCCESS', 'data': {'user_id': 100001, 'user_code': 'example_creator'}}
        def download(url, video_id, *pos, **kw):
            if '/by-user-code/' in url:
                return copy.deepcopy(lookup)
            page = kw.get('query', {}).get('page')
            if page is None:
                self.fail(f'No explicit page query: {url}')
            if int(page) > len(pages):
                self.fail(f'Pagination requested unexpected page {page}')
            return copy.deepcopy(pages[int(page) - 1])
        ie._download_json = Mock(side_effect=download)
        return ie, ie._real_extract(PROFILE_URL)


class URLTests(OfflineCase):
    def test_creator_and_posts(self):
        self.assertTrue(CandFansProfileIE.suitable(PROFILE_URL))
        self.assertFalse(CandFansPostIE.suitable(PROFILE_URL))
        for post_id in ('974904', '1322820'):
            with self.subTest(post_id=post_id):
                url = f'https://candfans.jp/posts/comment/show/{post_id}'
                self.assertTrue(CandFansPostIE.suitable(url))
                self.assertFalse(CandFansProfileIE.suitable(url))

    def test_reserved_routes_and_lookalike_hosts(self):
        for url in ('https://candfans.jp/api/contents/get-timeline/974904',
                    'https://candfans.jp/login', 'https://candfans.jp/posts',
                    'https://candfans.jp/api', 'https://candfans.jp/settings',
                    'https://candfans.jp.evil.invalid/example_creator'):
            with self.subTest(url=url):
                self.assertFalse(CandFansProfileIE.suitable(url))

    def test_url_only_1322820_is_not_fixture_974904(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=fixture('post_974904_sanitised.json'))
        ie._extract_m3u8_formats = Mock()
        with self.assertRaises(ExtractorError):
            ie._real_extract('https://candfans.jp/posts/comment/show/1322820')
        ie._extract_m3u8_formats.assert_not_called()


class PostTests(OfflineCase):
    def test_sanitised_false_permission_blocks_before_hls(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=fixture('post_974904_sanitised.json'))
        ie._extract_m3u8_formats = Mock()
        with self.assertRaises(ExtractorError) as err:
            ie._real_extract(POST_URL)
        self.assertTrue(err.exception.expected)
        self.assertIn('download', str(err.exception).lower())
        ie._extract_m3u8_formats.assert_not_called()

    def test_sanitised_metadata_only_preserves_unicode_and_jst_assumption(self):
        body = fixture('post_974904_sanitised.json')
        post = body['data']['post']
        ie, result = self.post(body, args={'candfanspost': {'metadata_only': ['true']}})
        self.assertEqual(result['id'], '974904')
        self.assertEqual(result['title'], post['title'])
        self.assertEqual(result['description'], post['contents_text'])
        self.assertEqual(result['timestamp'], 1749654958)
        self.assertEqual(result['upload_date'], '20250611')
        self.assertEqual(result['duration'], 1947)
        self.assertEqual(result['uploader_id'], '100001')
        self.assertEqual(result['uploader'], post['username'])
        self.assertEqual(result['uploader_url'], PROFILE_URL)
        self.assertEqual(result['webpage_url'], POST_URL)
        self.assertEqual(result['formats'], [])
        self.assertEqual(result['thumbnail'], 'https://video.candfans.jp/user/100001/post/974904/thumbnail.jpg')
        self.assertNotIn('media.example.invalid', json.dumps(result))
        self.assertNotIn('.m3u8', json.dumps(result))
        ie._extract_m3u8_formats.assert_not_called()

    def test_synthetic_explicit_permission_extracts_main_hls(self):
        ie, result = self.post(synthetic_post())
        self.assertTrue(result['formats'])
        self.assertEqual(ie._extract_m3u8_formats.call_args.args[0], 'https://media.example.invalid/a.m3u8')

    def test_known_relative_attachment_default_and_low_use_verified_hls_origin(self):
        # Synthetic permission=True and filename, not a live download assertion.
        path = '/user/100001/post/974904/synthetic-main.m3u8?signature=synthetic'
        for field in ('default', 'low'):
            with self.subTest(field=field):
                ie, result = self.post(synthetic_post(attachments=[{field: path}]))
                self.assertTrue(result['formats'])
                self.assertEqual(ie._extract_m3u8_formats.call_count, 1)
                self.assertEqual(ie._extract_m3u8_formats.call_args.args[0], 'https://video.candfans.jp' + path)
                self.assertEqual(ie._extract_m3u8_formats.call_args.kwargs['m3u8_id'], field)

    def test_false_permission_blocks_known_relative_hls_before_manifest(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=synthetic_post(
            is_downloadable=False,
            attachments=[{'default': '/user/100001/post/974904/synthetic-main.m3u8'}],
        ))
        ie._extract_m3u8_formats = Mock()
        with self.assertRaises(ExtractorError) as err:
            ie._real_extract(POST_URL)
        self.assertTrue(err.exception.expected)
        ie._extract_m3u8_formats.assert_not_called()

    def test_metadata_only_known_relative_hls_never_fetches_or_exposes_manifest(self):
        ie, result = self.post(synthetic_post(attachments=[{
            'default': '/user/100001/post/974904/synthetic-main.m3u8',
        }]), args={'candfanspost': {'metadata_only': ['true']}})
        self.assertEqual(result['formats'], [])
        self.assertNotIn('.m3u8', json.dumps(result))
        ie._extract_m3u8_formats.assert_not_called()

    def test_empty_attachments_never_fall_back_to_known_relative_contents_path(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=synthetic_post(
            attachments=[], contents_path1='/user/100001/post/974904/synthetic-main.m3u8',
        ))
        ie._extract_m3u8_formats = Mock()
        with self.assertRaises(ExtractorError):
            ie._real_extract(POST_URL)
        ie._extract_m3u8_formats.assert_not_called()

    def test_unknown_or_unsafe_relative_hls_paths_are_never_requested(self):
        for path in ('/relative/main.m3u8', 'user/100001/post/974904/main.m3u8',
                     '//unverified.example.invalid/user/100001/post/974904/main.m3u8',
                     '///unverified.example.invalid/user/100001/post/974904/main.m3u8',
                     '/user/100001/post/974904/../main.m3u8',
                     '/user/100001/post/974904/%2e%2e%2fmain.m3u8',
                     '/user/100001/post/974904/%252e%252e%252fmain.m3u8',
                     '/user/100001/post/974904/folder%2fmain.m3u8',
                     '/user/100001/post/974904/folder%5cmain.m3u8',
                     '/user/100001/post/974904/folder\\main.m3u8',
                     '/user/100001/post/974904/main\n.m3u8',
                     '/user/100001/post/974904/main.m3u8#fragment',
                     '/user/0/post/974904/main.m3u8', '/user/100001/post/0/main.m3u8',
                     '/user/100001/post/974904/sample.m3u8',
                     '/user/100001/post/974904/preview.m3u8'):
            with self.subTest(path=path):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(attachments=[{'default': path}]))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_unverified_permission_values_are_not_truthy_bypass(self):
        for value in (False, None, 0, 1, 'true', 'false', '1'):
            with self.subTest(value=value):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(is_downloadable=value))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_denied_viewing_never_extracts_hls(self):
        for value in (False, None, 0, '1', 'true'):
            with self.subTest(value=value):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(can_browsing=value))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_missing_permission_is_blocked(self):
        body = synthetic_post()
        del body['data']['post']['is_downloadable']
        with self.assertRaises(ExtractorError):
            self.post(body)

    def test_empty_missing_and_preview_only_never_fall_back(self):
        for attachments in ([], None, [{'preview': 'https://media.example.invalid/preview.m3u8'}],
                            [{'default': None, 'low': None}], [{'default': '/relative/main.m3u8'}]):
            with self.subTest(attachments=attachments):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(attachments=attachments))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_low_hls_is_main_fallback_not_preview(self):
        ie, result = self.post(synthetic_post(attachments=[{'low': 'https://media.example.invalid/low.m3u8', 'preview': 'https://media.example.invalid/sample.m3u8'}]))
        self.assertEqual(ie._extract_m3u8_formats.call_args.args[0], 'https://media.example.invalid/low.m3u8')
        self.assertTrue(result['formats'])

    def test_failed_hls_does_not_become_preview(self):
        with self.assertRaises(ExtractorError):
            self.post(synthetic_post(), hls=[])

    def test_malformed_post_responses(self):
        for body in (None, [], {}, {'status': 'SUCCESS', 'data': []},
                     {'status': 'SUCCESS', 'data': {'post': None}},
                     {'status': 'SUCCESS', 'data': {'post': {'post_id': 42}}}):
            with self.subTest(body=body):
                with self.assertRaises(ExtractorError):
                    self.post(body)

    def test_body_api_error_and_unauthenticated(self):
        for body in (fixture('auth_unauthenticated_minimal.json'),
                     {'status': 'ERROR', 'message': 'synthetic API error'},
                     {'status': 'ERROR', 'code': 'ERROR_FORBIDDEN'}):
            with self.subTest(body=body):
                with self.assertRaises(ExtractorError) as err:
                    self.post(body)
                self.assertTrue(err.exception.expected)

    def test_http_errors_are_expected_and_do_not_leak_body(self):
        for code in (401, 403, 429, 500):
            with self.subTest(code=code):
                ie = self.ie()
                cause = HTTPError(Response(io.BytesIO(b'private backend trace'), 'https://candfans.jp/api/contents/get-timeline/974904', {}, code))
                ie._download_json = Mock(side_effect=ExtractorError('request failed', cause=cause))
                with self.assertRaises(ExtractorError) as err:
                    ie._real_extract(POST_URL)
                self.assertTrue(err.exception.expected)
                self.assertNotIn('private backend trace', str(err.exception))

    def test_multi_attachment_ids_survive_reordering_tokens_and_duplicates(self):
        first = [{'default': 'https://media.example.invalid/a.m3u8?token=one'},
                 {'default': 'https://media.example.invalid/b.m3u8?token=one'}]
        _, result = self.post(synthetic_post(attachments=first))
        self.assertEqual(result['_type'], 'playlist')
        entries = list(result['entries'])
        ids = [item['id'] for item in entries]
        self.assertEqual(len(set(ids)), 2)
        self.assertNotIn('974904', ids)
        second = [{'default': 'https://media.example.invalid/b.m3u8?token=two'},
                  {'default': 'https://media.example.invalid/a.m3u8?token=two'},
                  {'default': 'https://media.example.invalid/a.m3u8?token=three'}]
        _, reordered = self.post(synthetic_post(attachments=second))
        reordered_ids = [item['id'] for item in reordered['entries']]
        self.assertEqual(set(ids), set(reordered_ids))
        self.assertEqual(len(reordered_ids), 2)
        for entry in entries:
            self.assertEqual(entry['webpage_url'], POST_URL)

    def test_partially_unavailable_multi_keeps_available_entry_and_stable_id(self):
        attachments = [
            {'default': 'https://media.example.invalid/a.m3u8?token=private-a'},
            {'default': 'https://media.example.invalid/b.m3u8?token=private-b'},
        ]
        _, complete = self.post(synthetic_post(attachments=attachments))
        expected_id = list(complete['entries'])[0]['id']
        for failure in ([], ExtractorError('private-b signed https://media.example.invalid/b.m3u8?token=private-b')):
            with self.subTest(failure_type=type(failure).__name__):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(attachments=attachments))
                ie._extract_m3u8_formats = Mock(side_effect=[
                    [{'url': 'https://media.example.invalid/available.m3u8', 'ext': 'mp4'}], failure,
                ])
                ie.report_warning = Mock()
                result = ie._real_extract(POST_URL)
                self.assertEqual(result['_type'], 'playlist')
                entries = list(result['entries'])
                self.assertEqual([item['id'] for item in entries], [expected_id])
                self.assertNotEqual(expected_id, '974904')
                self.assertTrue(ie.report_warning.called)
                warnings = ' '.join(str(call.args) for call in ie.report_warning.call_args_list)
                self.assertNotIn('private-b', warnings)
                self.assertNotIn('https://', warnings)
                self.assertEqual(ie._extract_m3u8_formats.call_count, 2)

    def test_all_multi_attachments_unavailable_returns_expected_error(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=synthetic_post(attachments=[
            {'default': 'https://media.example.invalid/a.m3u8?token=private-a'},
            {'default': 'https://media.example.invalid/b.m3u8?token=private-b'},
        ]))
        ie._extract_m3u8_formats = Mock(return_value=[])
        with self.assertRaises(ExtractorError) as err:
            ie._real_extract(POST_URL)
        self.assertTrue(err.exception.expected)
        self.assertEqual(ie._extract_m3u8_formats.call_count, 2)
        self.assertNotIn('private-', str(err.exception))

    def test_invalid_date_does_not_crash_metadata(self):
        _, result = self.post(synthetic_post(post_date='not-a-date'))
        self.assertIsNone(result.get('timestamp'))

    def test_api_uses_normal_cookie_jar_without_global_cookie_header(self):
        ie, _ = self.post(synthetic_post())
        call = ie._download_json.call_args
        self.assertEqual(call.args[0], 'https://candfans.jp/api/contents/get-timeline/974904')
        self.assertEqual(call.kwargs['headers'], {'Accept': 'application/json'})
        self.assertEqual(ie._download_json.call_count, 1)  # No account-PII preflight.

    def test_relative_thumbnail_omitted_absolute_api_url_retained(self):
        for value, expected in (('/thumbnail.jpg', None),
                                ('//unverified.invalid/thumbnail.jpg', None),
                                ('https://images.example.invalid/thumbnail.jpg', 'https://images.example.invalid/thumbnail.jpg')):
            with self.subTest(value=value):
                _, result = self.post(synthetic_post(thumbnail_file=value))
                self.assertEqual(result.get('thumbnail'), expected)

    def test_invalid_or_insecure_media_url_not_requested(self):
        for value in ('http://media.example.invalid/main.m3u8',
                      'https://user:password@media.example.invalid/main.m3u8',
                      'https://media.example.invalid:invalid/main.m3u8',
                      'https://media.example.invalid/white space.m3u8',
                      'file:///local/video.m3u8', 'javascript:alert(1)',
                      'https://media.example.invalid/video.mp4'):
            with self.subTest(value=value):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(attachments=[{'default': value}]))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_preview_url_disguised_as_default_is_rejected(self):
        for path in ('sample.m3u8', 'preview.m3u8'):
            with self.subTest(path=path):
                ie = self.ie()
                ie._download_json = Mock(return_value=synthetic_post(attachments=[{'default': f'https://media.example.invalid/{path}'}]))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError):
                    ie._real_extract(POST_URL)
                ie._extract_m3u8_formats.assert_not_called()

    def test_same_path_on_distinct_hosts_is_not_duplicate_media(self):
        _, result = self.post(synthetic_post(attachments=[
            {'default': 'https://one.example.invalid/a.m3u8'},
            {'default': 'https://two.example.invalid/a.m3u8'},
        ]))
        self.assertEqual(len({item['id'] for item in result['entries']}), 2)

    def test_attachment_duration_matches_path_not_list_position(self):
        _, result = self.post(synthetic_post(
            attachments=[{'default': 'https://media.example.invalid/a.m3u8'}, {'default': 'https://media.example.invalid/b.m3u8'}],
            post_attachments=[{'default_path': 'b.m3u8', 'length': 20}, {'default_path': 'a.m3u8', 'length': 10}],
        ))
        self.assertEqual([item.get('duration') for item in result['entries']], [10, 20])

    def test_ambiguous_attachment_duration_not_assigned_by_index(self):
        _, result = self.post(synthetic_post(
            attachments=[{'default': 'https://one.example.invalid/a.m3u8'}, {'default': 'https://two.example.invalid/a.m3u8'}],
            post_attachments=[{'default_path': 'a.m3u8', 'length': 10}],
        ))
        self.assertTrue(all('duration' not in item for item in result['entries']))

    def test_metadata_only_option_is_strict_boolean(self):
        for value in ('yes', '1', 'anything'):
            with self.subTest(value=value):
                with self.assertRaises(ExtractorError):
                    self.post(synthetic_post(), args={'candfanspost': {'metadata_only': [value]}})

    def test_drm_formats_filtered_and_drm_only_rejected(self):
        with self.assertRaises(ExtractorError):
            self.post(synthetic_post(), hls=[{'url': 'https://media.example.invalid/locked.m3u8', 'has_drm': True}])
        _, result = self.post(synthetic_post(), hls=[
            {'url': 'https://media.example.invalid/locked.m3u8', 'has_drm': True},
            {'url': 'https://media.example.invalid/clear.m3u8', 'has_drm': False},
        ])
        self.assertEqual([fmt['url'] for fmt in result['formats']], ['https://media.example.invalid/clear.m3u8'])

    def test_real_hls_parser_with_synthetic_in_memory_manifest(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=synthetic_post())
        manifest = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720\n720/index.m3u8\n'
        response = Response(io.BytesIO(manifest.encode()), 'https://media.example.invalid/a.m3u8', {'Content-Type': 'application/vnd.apple.mpegurl'}, 200)
        ie._request_webpage = Mock(return_value=response)
        result = ie._real_extract(POST_URL)
        self.assertEqual(result['formats'][0]['height'], 720)
        self.assertEqual(result['formats'][0]['url'], 'https://media.example.invalid/720/index.m3u8')

    def test_real_hls_parser_recognises_synthetic_drm_without_key_request(self):
        ie = self.ie()
        ie._download_json = Mock(return_value=synthetic_post())
        manifest = '#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXT-X-KEY:METHOD=SAMPLE-AES,URI="skd://synthetic.invalid/key",KEYFORMAT="com.apple.streamingkeydelivery"\n#EXTINF:10,\nsegment.ts\n#EXT-X-ENDLIST\n'
        response = Response(io.BytesIO(manifest.encode()), 'https://media.example.invalid/a.m3u8', {'Content-Type': 'application/vnd.apple.mpegurl'}, 200)
        ie._request_webpage = Mock(return_value=response)
        with self.assertRaises(ExtractorError):
            ie._real_extract(POST_URL)
        self.assertEqual(ie._request_webpage.call_count, 1)


class ThumbnailTests(OfflineCase):
    ORIGIN = 'https://images.example.invalid'
    ORIGINAL_PATH = '/user/100001/post/974904/thumbnail.jpg'

    def thumbnail_args(self, origin=None, metadata_only=False):
        config = {'thumbnail_origin': [self.ORIGIN if origin is None else origin]}
        if metadata_only:
            config['metadata_only'] = ['true']
        return {'candfanspost': config}

    def test_sanitised_known_thumbnail_uses_user_verified_default_without_fetch(self):
        ie, result = self.post(fixture('post_974904_sanitised.json'), args={
            'candfanspost': {'metadata_only': ['true']},
        })
        self.assertEqual(result['thumbnail'], 'https://video.candfans.jp' + self.ORIGINAL_PATH)
        self.assertEqual(result['formats'], [])
        ie._extract_m3u8_formats.assert_not_called()
        self.assertEqual(ie._download_json.call_count, 1)

    def test_default_thumbnail_origin_only_matches_verified_path_pattern(self):
        for path in ('/thumbnail.jpg', '/user/100001/thumbnail.jpg',
                     '/user/100001/post/974904/cover.jpg', '/user/100001/post/974904/thumbnail.png',
                     '/user/0/post/974904/thumbnail.jpg', '/user/100001/post/0/thumbnail.jpg',
                     '/user/name/post/974904/thumbnail.jpg', 'user/100001/post/974904/thumbnail.jpg',
                     '//unknown.example.invalid/user/100001/post/974904/thumbnail.jpg',
                     '/user/100001/post/974904/../thumbnail.jpg',
                     '/user/100001/post/974904/thumbnail.jpg#fragment'):
            with self.subTest(path=path):
                ie, result = self.post(synthetic_post(thumbnail_file=path), args={
                    'candfanspost': {'metadata_only': ['true']},
                })
                self.assertNotIn('thumbnail', result)
                ie._extract_m3u8_formats.assert_not_called()

    def test_default_thumbnail_origin_retains_api_query_without_altering_origin(self):
        path = self.ORIGINAL_PATH + '?version=synthetic'
        _, result = self.post(synthetic_post(thumbnail_file=path), args={
            'candfanspost': {'metadata_only': ['true']},
        })
        self.assertEqual(result['thumbnail'], 'https://video.candfans.jp' + path)

    def test_profile_known_thumbnails_use_default_origin_without_image_requests(self):
        page = fixture('timeline_page_sanitised.json')
        ie, result = self.profile([page, fixture('timeline_empty.json')])
        entries = list(result['entries'])
        self.assertEqual(len(entries), 9)
        for post, entry in zip(page['data'], entries):
            self.assertEqual(entry['thumbnail'], 'https://video.candfans.jp' + post['thumbnail_file'])
        self.assertEqual(ie._download_json.call_count, 3)  # Lookup plus two API pages only.

    def test_explicit_https_origin_resolves_sanitised_thumbnail_in_metadata_only(self):
        for origin in (self.ORIGIN, self.ORIGIN + '/'):
            with self.subTest(origin=origin):
                ie, result = self.post(fixture('post_974904_sanitised.json'), args=self.thumbnail_args(origin, metadata_only=True))
                self.assertEqual(result['thumbnail'], self.ORIGIN + self.ORIGINAL_PATH)
                self.assertEqual(result['formats'], [])
                ie._extract_m3u8_formats.assert_not_called()
                self.assertEqual(ie._download_json.call_count, 1)

    def test_bare_relative_path_stays_on_explicit_origin(self):
        _, result = self.post(synthetic_post(thumbnail_file='user/100001/post/974904/thumbnail.jpg'), args=self.thumbnail_args())
        self.assertEqual(result['thumbnail'], self.ORIGIN + self.ORIGINAL_PATH)

    def test_api_absolute_https_thumbnail_is_retained_with_or_without_origin(self):
        absolute = 'https://api-images.example.invalid/cover.jpg?signature=synthetic'
        for args in (None, self.thumbnail_args()):
            with self.subTest(args=args):
                _, result = self.post(synthetic_post(thumbnail_file=absolute), args=args)
                self.assertEqual(result['thumbnail'], absolute)

    def test_profile_reads_post_thumbnail_origin_configuration(self):
        page = fixture('timeline_page_sanitised.json')
        _, result = self.profile([page, fixture('timeline_empty.json')], args=self.thumbnail_args())
        entries = list(result['entries'])
        self.assertEqual(len(entries), 9)
        for original, entry in zip(page['data'], entries):
            self.assertEqual(entry['thumbnail'], self.ORIGIN + original['thumbnail_file'])
            self.assertEqual(entry['ie_key'], 'CandFansPost')

    def test_multi_attachment_entries_share_resolved_thumbnail(self):
        for args, origin in ((None, 'https://video.candfans.jp'), (self.thumbnail_args(), self.ORIGIN)):
            with self.subTest(origin=origin):
                _, result = self.post(synthetic_post(attachments=[
                    {'default': 'https://media.example.invalid/a.m3u8'},
                    {'default': 'https://media.example.invalid/b.m3u8'},
                ]), args=args)
                entries = list(result['entries'])
                self.assertEqual(len(entries), 2)
                self.assertTrue(all(item['thumbnail'] == origin + self.ORIGINAL_PATH for item in entries))

    def test_invalid_thumbnail_origins_raise_expected_configuration_error(self):
        invalid = (
            '', 'http://images.example.invalid', 'ftp://images.example.invalid',
            '//images.example.invalid', 'images.example.invalid',
            'https://images.example.invalid/path', 'https://images.example.invalid/?query=1',
            'https://images.example.invalid/#fragment', 'https://images.example.invalid?',
            'https://images.example.invalid#', 'https://user:pass@images.example.invalid',
            'https://@images.example.invalid', 'https://images.example.invalid:bad',
            'https://images.example.invalid\\path', 'https://images.example.invalid/white space',
            'https://images.example.invalid\n', 'https://[malformed',
        )
        for origin in invalid:
            with self.subTest(origin=origin):
                ie = self.ie(args=self.thumbnail_args(origin, metadata_only=True))
                ie._download_json = Mock(return_value=fixture('post_974904_sanitised.json'))
                ie._extract_m3u8_formats = Mock()
                with self.assertRaises(ExtractorError) as err:
                    ie._real_extract(POST_URL)
                self.assertTrue(err.exception.expected)
                ie._extract_m3u8_formats.assert_not_called()

    def test_multiple_thumbnail_origin_values_rejected(self):
        args = {'candfanspost': {'thumbnail_origin': [self.ORIGIN, 'https://other.example.invalid'], 'metadata_only': ['true']}}
        with self.assertRaises(ExtractorError) as err:
            self.post(fixture('post_974904_sanitised.json'), args=args)
        self.assertTrue(err.exception.expected)

    def test_unsafe_thumbnail_paths_are_omitted_without_network(self):
        paths = (
            '//unverified.example.invalid/cover.jpg', '///unverified.example.invalid/cover.jpg',
            '\\unverified.example.invalid\\cover.jpg', '/user\\cover.jpg',
            '/user/../cover.jpg', '/user/./cover.jpg', '../cover.jpg',
            '/user/%2e%2e/cover.jpg', '/user/%252e%252e/cover.jpg',
            'http://unverified.example.invalid/cover.jpg', 'javascript:alert(1)',
            'https://user:password@unverified.example.invalid/cover.jpg',
            '/user/cover\n.jpg', None, 123, {}, [],
        )
        for path in paths:
            with self.subTest(path=path):
                ie, result = self.post(synthetic_post(thumbnail_file=path), args=self.thumbnail_args(metadata_only=True))
                self.assertNotIn('thumbnail', result)
                ie._extract_m3u8_formats.assert_not_called()


class ProfileTests(OfflineCase):
    def test_sanitised_nine_then_empty_lazy(self):
        ie, result = self.profile([fixture('timeline_page_sanitised.json'), fixture('timeline_empty.json')])
        # Lookup can run at playlist creation; the timeline itself must be lazy.
        self.assertFalse(any('/get-timeline' in call.args[0] for call in ie._download_json.call_args_list))
        entries = iter(result['entries'])
        first = next(entries)
        self.assertEqual(first['id'], IDS[0])
        timeline_calls = [call for call in ie._download_json.call_args_list if '/get-timeline' in call.args[0]]
        self.assertEqual(len(timeline_calls), 1)
        self.assertEqual([first['id']] + [item['id'] for item in entries], IDS)
        timeline_calls = [call for call in ie._download_json.call_args_list if '/get-timeline' in call.args[0]]
        self.assertEqual([call.kwargs['query']['page'] for call in timeline_calls], [1, 2])
        self.assertEqual(first['ie_key'], 'CandFansPost')
        self.assertEqual(first['url'], f'https://candfans.jp/posts/comment/show/{IDS[0]}')

    def test_multi_page_deduplicates_ids(self):
        original = fixture('timeline_page_sanitised.json')
        p1 = {'status': 'SUCCESS', 'data': original['data'][:3]}
        p2 = {'status': 'SUCCESS', 'data': original['data'][2:5]}
        _, result = self.profile([p1, p2, fixture('timeline_empty.json')])
        self.assertEqual([item['id'] for item in result['entries']], IDS[:5])

    def test_repeated_page_stops_without_infinite_pagination(self):
        page = fixture('timeline_page_sanitised.json')
        ie, result = self.profile([page, page])
        self.assertEqual([item['id'] for item in result['entries']], IDS)
        self.assertLessEqual(len(ie._download_json.call_args_list), 3)

    def test_unrecognised_timeline_schema_not_silently_empty(self):
        for body in ({'status': 'SUCCESS', 'data': {}}, {'status': 'SUCCESS', 'data': None},
                     {'status': 'SUCCESS', 'data': [{'title': 'no post ID'}]}):
            with self.subTest(body=body):
                _, result = self.profile([body])
                with self.assertRaises(ExtractorError):
                    list(result['entries'])

    def test_unknown_lookup_schema_requires_explicit_fallback(self):
        for body in ({'status': 'SUCCESS', 'data': {'id': 100001}},
                     {'status': 'SUCCESS', 'data': {'user_id': 100001}},
                     {'status': 'SUCCESS', 'data': {'user_id': 100001, 'user_code': 'different'}},
                     {'status': 'SUCCESS', 'data': []}):
            with self.subTest(body=body):
                with self.assertRaises(ExtractorError):
                    ie, result = self.profile([fixture('timeline_empty.json')], lookup=body)
                    list(result['entries'])

    def test_synthetic_unique_explicit_record_in_nested_shape(self):
        body = {'status': 'SUCCESS', 'data': {'creator': {'user_code': 'example_creator', 'user_id': 100001}}}
        _, result = self.profile([fixture('timeline_empty.json')], lookup=body)
        self.assertEqual(list(result['entries']), [])

    def test_conflicting_lookup_records_rejected(self):
        body = {'status': 'SUCCESS', 'data': [
            {'user_code': 'example_creator', 'user_id': 123},
            {'user_code': 'example_creator', 'user_id': 456},
        ]}
        with self.assertRaises(ExtractorError):
            _, result = self.profile([fixture('timeline_empty.json')], lookup=body)
            list(result['entries'])

    def test_explicit_user_id_fallback_does_not_fetch_unknown_lookup(self):
        ie, result = self.profile([fixture('timeline_empty.json')], args={'candfansprofile': {'user_id': ['777']}})
        list(result['entries'])
        calls = ie._download_json.call_args_list
        self.assertTrue(calls)
        self.assertFalse(any('/by-user-code/' in call.args[0] for call in calls))
        self.assertEqual(str(calls[0].kwargs['query']['user_id']), '777')

    def test_fallback_user_id_must_be_numeric(self):
        with self.assertRaises(ExtractorError):
            _, result = self.profile([fixture('timeline_empty.json')], args={'candfansprofile': {'user_id': ['../other']}})
            list(result['entries'])

    def test_timeline_creator_identity_mismatch_rejected(self):
        body = fixture('timeline_page_sanitised.json')
        body['data'][0]['user_id'] = 999
        _, result = self.profile([body])
        with self.assertRaises(ExtractorError):
            list(result['entries'])


class InfrastructureTests(OfflineCase):
    def test_netscape_cookie_jar_domain_path_secure_scoping(self):
        # Synthetic names/values and reserved .invalid hosts; never inspect real cookies.
        with self.temporary_directory() as directory:
            path = Path(directory) / 'cookies.txt'
            path.write_text('# Netscape HTTP Cookie File\n.example.invalid\tTRUE\t/api\tTRUE\t0\tsynthetic_session\tnot-a-real-secret\n', encoding='utf-8')
            jar = YoutubeDLCookieJar(str(path))
            jar.load(ignore_discard=True, ignore_expires=True)
            for url, expected in (
                ('https://site.example.invalid/api/post', True),
                ('https://site.example.invalid/elsewhere', False),
                ('http://site.example.invalid/api/post', False),
                ('https://unrelated.invalid/api/post', False),
            ):
                request = Request(url)
                jar.add_cookie_header(request)
                self.assertEqual(request.has_header('Cookie'), expected, url)

    def test_sanitised_fixture_inventory_hash(self):
        inventory = fixture('fixture_inventory.json')
        digest = hashlib.sha256((FIXTURES / 'timeline_page_sanitised.json').read_bytes()).hexdigest()
        self.assertEqual(digest, inventory['sha256_of_sanitised_timeline'])
        page = fixture('timeline_page_sanitised.json')
        self.assertEqual([str(p['post_id']) for p in page['data']], IDS)
        self.assertTrue(all(p['is_downloadable'] is False for p in page['data']))

    def test_build_reproducible_namespace_zip(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'build.py'
        spec = importlib.util.spec_from_file_location('candfans_build', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.temporary_directory() as directory:
            one, two = Path(directory) / 'one.zip', Path(directory) / 'two.zip'
            module.build(one)
            module.build(two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with zipfile.ZipFile(one) as archive:
                self.assertIn('yt_dlp_plugins/extractor/candfans.py', archive.namelist())
                self.assertFalse(any('__init__' in name or '__pycache__' in name for name in archive.namelist()))
                self.assertIsNone(archive.testzip())


if __name__ == '__main__':
    unittest.main()
