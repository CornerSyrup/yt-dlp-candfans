"""CandFans extractors. Site contracts are user supplied; see README evidence notes."""

import datetime
import hashlib
import math
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError


def _numeric_id(value):
    if isinstance(value, bool):
        return None
    value = str(value) if isinstance(value, (int, str)) else ''
    return value if re.fullmatch(r'[1-9]\d*', value) else None


def _text(value):
    return value if isinstance(value, str) else None


def _duration(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _https_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != 'https' or not parts.hostname or parts.username is not None or parts.password is not None:
            return None
        parts.port  # Reject malformed ports rather than passing them to the downloader.
    except ValueError:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


def _hls_url(value):
    absolute = _https_url(value)
    if absolute:
        return absolute
    if not isinstance(value, str) or not value or value.startswith('//') or any(
            c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme or parts.netloc or '#' in value or '\\' in value:
        return None
    known_path = r'/user/[1-9]\d*/post/[1-9]\d*/[^/]+\.m3u8'
    decoded = parts.path
    for _ in range(8):
        if not re.fullmatch(known_path, decoded) or '\\' in decoded or any(
                segment in ('.', '..') for segment in decoded.split('/')) or any(
                ord(c) < 32 or ord(c) == 127 for c in decoded) or re.search(
                r'(?:^|/)(?:sample|preview)(?:[._/-]|$)', decoded, re.IGNORECASE):
            return None
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    else:
        return None
    # The user verified the 974904 main manifest at this origin. Resolve only
    # actual attachment values in the observed path shape, never other fields.
    return urlunsplit(('https', 'video.candfans.jp', parts.path, parts.query, ''))


class _CandFansBaseIE(InfoExtractor):
    _ORIGIN = 'https://candfans.jp'

    def _call_api(self, path, item_id, *, query=None, require_success=True):
        # No Cookie header or auth preflight: yt-dlp's cookie jar owns scoping.
        try:
            response = self._download_json(
                f'{self._ORIGIN}{path}', item_id,
                note='Downloading CandFans API JSON',
                headers={'Accept': 'application/json'}, query=query)
        except ExtractorError as error:
            cause = error.cause
            status = getattr(cause, 'status', None) or getattr(cause, 'code', None)
            if status in (401, 403):
                message = f'HTTP {status}: unauthenticated or access denied; check your authorised Netscape cookies.txt'
            elif status == 429:
                message = 'HTTP 429: rate limited; stop and retry later'
            elif isinstance(status, int) and status >= 500:
                message = f'HTTP {status}: server unavailable; retry later'
            else:
                message = 'request failed; check connectivity and authorised access'
            # Do not reproduce private backend bodies, traces, or signed URLs.
            raise ExtractorError(f'CandFans API {message}', expected=True) from None
        if not isinstance(response, dict):
            raise ExtractorError('CandFans API returned an unexpected JSON schema (expected object)', expected=True)
        if response.get('code') == 'ERROR_UNAUTHENTICATED':
            raise ExtractorError(
                'CandFans API unauthenticated (ERROR_UNAUTHENTICATED); provide authorised Netscape cookies.txt',
                expected=True)
        if (require_success and response.get('status') != 'SUCCESS') or (
                'status' in response and response['status'] != 'SUCCESS') or (
                isinstance(response.get('code'), str) and response['code'].startswith('ERROR')):
            raise ExtractorError('CandFans API reported an error; response details were withheld', expected=True)
        return response

    def _thumbnail_url(self, value):
        # The user verified video.candfans.jp for the 974904 thumbnail sample.
        # Apply it only to that observed path shape, not arbitrary relative files.
        # This is user-supplied evidence, not an extractor live-verification result.
        origins = self._configuration_arg('thumbnail_origin', ie_key='CandFansPost', casesense=True)
        origin = None
        if origins:
            candidate = origins[0] if len(origins) == 1 else None
            safe = _https_url(candidate)
            if safe:
                parts = urlsplit(candidate)
                if parts.path in ('', '/') and not any(c in candidate for c in ('?', '#', '\\')):
                    origin = urlunsplit(('https', parts.netloc, '', '', ''))
            if not origin:
                raise ExtractorError(
                    'candfanspost:thumbnail_origin must be one user-verified HTTPS origin '
                    '(for example https://images.example.invalid), without a path, query, fragment or userinfo',
                    expected=True)
        absolute = _https_url(value)
        if absolute:
            return absolute
        if not isinstance(value, str) or not value or value.startswith('//') or any(
                c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            return None
        try:
            parts = urlsplit(value)
        except ValueError:
            return None
        if parts.scheme or parts.netloc or '#' in value or '\\' in value:
            return None
        path = parts.path
        if not path or path.startswith('//'):
            return None
        if not origin:
            if not re.fullmatch(r'/user/[1-9]\d*/post/[1-9]\d*/thumbnail\.jpg', path):
                return None
            origin = 'https://video.candfans.jp'
        # Reject traversal even when encoded, including nested encodings. The
        # original path is retained for the request; this decoding is validation.
        decoded = path
        for _ in range(8):
            if decoded.startswith('//') or '\\' in decoded or any(
                    segment in ('.', '..') for segment in decoded.split('/')) or any(
                    ord(c) < 32 or ord(c) == 127 for c in decoded):
                return None
            next_decoded = unquote(decoded)
            if next_decoded == decoded:
                break
            decoded = next_decoded
        else:
            return None
        origin_parts = urlsplit(origin)
        return urlunsplit(('https', origin_parts.netloc, '/' + path.lstrip('/'), parts.query, ''))

    def _metadata(self, post, post_id):
        user_id = _numeric_id(post.get('user_id'))
        user_code = _text(post.get('user_code'))
        info = {
            'id': post_id,
            'title': _text(post.get('title')) or f'CandFans {post_id}',
            'description': _text(post.get('contents_text')),
            'uploader': _text(post.get('username')) or user_code,
            'uploader_id': user_id,
            'uploader_url': f'https://candfans.jp/{quote(user_code, safe="")}' if user_code else None,
            'webpage_url': f'https://candfans.jp/posts/comment/show/{post_id}',
            'age_limit': 18,
        }
        date = _text(post.get('post_date'))
        if date:
            try:
                parsed = datetime.datetime.fromisoformat(date.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    # Provisional site-local JST assumption, explicitly documented.
                    parsed = parsed.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
                info['timestamp'] = int(parsed.timestamp())
                info['upload_date'] = parsed.astimezone(datetime.timezone.utc).strftime('%Y%m%d')
            except (ValueError, OverflowError, OSError):
                pass
        thumbnail = self._thumbnail_url(post.get('thumbnail_file'))
        if thumbnail:
            info['thumbnail'] = thumbnail
        categories = []
        for key in ('category_category', 'status_category', 'situation_category'):
            category = post.get(key)
            name = _text(category.get('name')) if isinstance(category, dict) else None
            if name and name not in categories:
                categories.append(name)
        if categories:
            info['categories'] = categories
        return {key: value for key, value in info.items() if value is not None}


class CandFansPostIE(_CandFansBaseIE):
    IE_NAME = 'CandFansPost'
    _VALID_URL = r'https?://candfans\.jp/posts/comment/show/(?P<id>[1-9]\d*)/?(?:[?#].*)?$'

    def _metadata_only(self):
        values = self._configuration_arg('metadata_only', ['false'])
        if len(values) != 1 or values[0].lower() not in ('true', 'false'):
            raise ExtractorError('candfanspost:metadata_only must be true or false', expected=True)
        return values[0].lower() == 'true'

    @staticmethod
    def _media(post):
        attachments = post.get('attachments')
        if not isinstance(attachments, list):
            return []
        excluded = set()
        for value in [post.get('sample_file')] + [
                item.get('preview') for item in attachments if isinstance(item, dict)]:
            if isinstance(value, str):
                try:
                    excluded.add(urlsplit(value).path)
                except ValueError:
                    pass
        media = {}
        for item in attachments:
            if not isinstance(item, dict):
                continue
            variants = []
            for label in ('default', 'low'):
                value = _hls_url(item.get(label))
                if not value:
                    continue
                path = urlsplit(value).path
                if not path.lower().endswith('.m3u8') or path in excluded or re.search(
                        r'(?:^|/)(?:sample|preview)(?:[._/-]|$)', path, re.IGNORECASE):
                    continue
                if not any(previous == value for _, previous in variants):
                    variants.append((label, value))
            if not variants:
                continue
            # Keep the origin to distinguish same-named media on different hosts.
            # The query is excluded so rotating signatures do not change archive IDs.
            parts = urlsplit(variants[0][1])
            hostname = parts.hostname.lower()
            if ':' in hostname:
                hostname = f'[{hostname}]'
            authority = hostname + (f':{parts.port}' if parts.port not in (None, 443) else '')
            identity = urlunsplit(('https', authority, parts.path, '', ''))
            existing = media.setdefault(identity, [])
            for variant in variants:
                if variant not in existing:
                    existing.append(variant)
        return list(media.items())

    @staticmethod
    def _media_duration(post, variants, single):
        paths = {urlsplit(url).path for _, url in variants}
        all_media_paths = [
            {urlsplit(url).path for _, url in media_variants}
            for _, media_variants in CandFansPostIE._media(post)
        ]
        matches = []
        details = post.get('post_attachments')
        for detail in details if isinstance(details, list) else []:
            if not isinstance(detail, dict):
                continue
            default_path = _text(detail.get('default_path'))
            if not default_path or '?' in default_path or '#' in default_path:
                continue
            def path_matches(path):
                return path == default_path or path.endswith('/' + default_path.lstrip('/'))

            # A basename is useful only when it identifies one media item globally.
            if any(path_matches(path) for path in paths) and sum(
                    any(path_matches(path) for path in media_paths) for media_paths in all_media_paths) == 1:
                matches.append(detail)
        if len(matches) == 1:
            duration = _duration(matches[0].get('length'))
            if duration is not None:
                return duration
        if single:
            for key in ('movie_time', 'attachment_length'):
                duration = _duration(post.get(key))
                if duration is not None:
                    return duration
        return None

    def _real_extract(self, url):
        post_id = self._match_id(url)
        response = self._call_api(f'/api/contents/get-timeline/{post_id}', post_id)
        data = response.get('data')
        post = data.get('post') if isinstance(data, dict) else None
        if not isinstance(post, dict):
            raise ExtractorError('CandFans post API schema mismatch: expected data.post object', expected=True)
        if _numeric_id(post.get('post_id')) != post_id:
            raise ExtractorError('CandFans post ID mismatch; refusing unrelated API content', expected=True)
        info = self._metadata(post, post_id)
        if self._metadata_only():
            info['formats'] = []
            duration = _duration(post.get('movie_time'))
            if duration is None:
                duration = _duration(post.get('attachment_length'))
            if duration is not None:
                info['duration'] = duration
            return info
        browsing = post.get('can_browsing')
        if not (browsing is True or type(browsing) is int and browsing == 1):
            raise ExtractorError('CandFans API can_browsing is not granted', expected=True)
        # User-tested evidence: is_downloadable is not a media access gate.
        # Use the returned attachments and actual HTTP/HLS results unchanged.
        media = self._media(post)
        if not media:
            raise ExtractorError(
                'CandFans API returned no usable full HLS attachments. '
                'Preview/sample fallback is disabled', expected=True)
        entries = []
        failures = []
        for identity, variants in media:
            media_id = post_id if len(media) == 1 else f'{post_id}-{hashlib.sha256(identity.encode()).hexdigest()[:16]}'
            entry = dict(info, id=media_id)
            formats = []
            for label, manifest in variants:
                try:
                    extracted = self._extract_m3u8_formats(
                        manifest, media_id, 'mp4', m3u8_id=label, fatal=True)
                except ExtractorError as error:
                    status = getattr(error.cause, 'status', None) or getattr(error.cause, 'code', None)
                    failures.append(f'HTTP {status}' if isinstance(status, int) else 'HLS extraction error')
                    continue
                if not extracted:
                    failures.append('manifest returned no formats')
                elif all(fmt.get('has_drm') for fmt in extracted):
                    failures.append('all formats are marked DRM')
                for fmt in extracted:
                    if not fmt.get('has_drm'):
                        formats.append(fmt)
            if not formats:
                if len(media) > 1:
                    self.report_warning(
                        f'CandFans attachment {media_id} has no playable non-DRM HLS formats; skipping')
                continue
            self._remove_duplicate_formats(formats)
            entry['formats'] = formats
            duration = self._media_duration(post, variants, len(media) == 1)
            if duration is not None:
                entry['duration'] = duration
            if len(media) > 1:
                entry['title'] = f'{info["title"]} [{media_id}]'
            entries.append(entry)
        if not entries:
            raise ExtractorError(
                'CandFans returned no playable HLS formats: ' + ', '.join(dict.fromkeys(failures)), expected=True)
        if len(media) == 1:
            return entries[0]
        return self.playlist_result(entries, post_id, info['title'], info.get('description'))


class CandFansProfileIE(_CandFansBaseIE):
    IE_NAME = 'CandFansProfile'
    _RESERVED = (
        'api', 'posts', 'login', 'logout', 'register', 'signup', 'signin', 'password',
        'forgot-password', 'reset-password', 'terms', 'privacy', 'contact', 'help',
        'faq', 'search', 'settings', 'account', 'mypage', 'notifications', 'messages',
        'about', 'legal', 'support', 'creators', 'ranking', 'home', 'explore', 'news',
        'assets', 'storage', 'css', 'js', 'images', 'user', 'users', 'auth',
        r'favicon\.ico', r'robots\.txt', r'sitemap\.xml',
    )
    _VALID_URL = (
        r'https?://candfans\.jp/(?!(?i:' + '|'.join(_RESERVED) + r')/?(?:[?#]|$))'
        r'(?P<id>[A-Za-z0-9_][A-Za-z0-9_.-]*)/?(?:[?#].*)?$')

    def _resolve_user_id(self, user_code):
        explicit = self._configuration_arg('user_id')
        if explicit:
            if len(explicit) != 1 or not _numeric_id(explicit[0]):
                raise ExtractorError('candfansprofile:user_id must be one positive numeric user ID', expected=True)
            return explicit[0]
        response = self._call_api(
            f'/api/v3/users/by-user-code/{quote(user_code, safe="")}', user_code, require_success=False)
        candidates = set()
        pending = [response]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                # Defensive discovery rule, not a claim about the unknown response schema.
                if value.get('user_code') == user_code:
                    candidate = _numeric_id(value.get('user_id'))
                    if candidate:
                        candidates.add(candidate)
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        if len(candidates) != 1:
            raise ExtractorError(
                'CandFans user-by-code schema is unverified: could not resolve a unique matching '
                'user_code + user_id. Supply a verified ID with candfansprofile:user_id=NUMBER', expected=True)
        return candidates.pop()

    def _entries(self, user_code, user_id):
        seen = set()
        page = 1
        while True:
            response = self._call_api('/api/contents/get-timeline', user_code, query={
                'user_id': user_id, 'post_type[]': 1, 'page': page,
            })
            posts = response.get('data')
            if not isinstance(posts, list):
                raise ExtractorError('CandFans timeline API schema mismatch: expected data array', expected=True)
            if not posts:
                return
            progress = False
            for post in posts:
                post_id = _numeric_id(post.get('post_id')) if isinstance(post, dict) else None
                if not post_id:
                    raise ExtractorError('CandFans timeline contains a malformed post_id', expected=True)
                if _numeric_id(post.get('user_id')) != user_id or post.get('user_code') != user_code:
                    raise ExtractorError('CandFans timeline creator identity mismatch', expected=True)
                if post_id in seen:
                    continue
                seen.add(post_id)
                progress = True
                metadata = self._metadata(post, post_id)
                yield self.url_result(
                    metadata['webpage_url'], ie=CandFansPostIE, video_id=post_id,
                    video_title=metadata['title'], **{
                        key: value for key, value in metadata.items()
                        if key not in ('id', 'title', 'webpage_url')})
            if not progress:
                self.report_warning('CandFans pagination returned no new post IDs; stopping to avoid a repeated-page loop')
                return
            page += 1

    def _real_extract(self, url):
        user_code = self._match_id(url)
        user_id = self._resolve_user_id(user_code)
        return self.playlist_result(
            self._entries(user_code, user_id), playlist_id=user_id,
            playlist_title=user_code, uploader_id=user_id,
            uploader_url=f'{self._ORIGIN}/{quote(user_code, safe="")}')
