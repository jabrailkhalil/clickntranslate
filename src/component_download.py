"""Bounded, resumable transport for authenticated component artifacts."""
import json
from pathlib import Path
import re
import time

from component_catalog import ComponentError


class ComponentDownloader:
    def __init__(self, check_cancel=lambda: None, progress=lambda *_: None):
        self.check_cancel = check_cancel
        self.progress = progress

    @staticmethod
    def metadata_path(path):
        path = Path(path)
        return path.with_name(path.name + '.resume.json')

    @classmethod
    def complete(cls, path):
        cls.metadata_path(path).unlink(missing_ok=True)

    def artifact(self, url, destination, specification):
        import requests
        path = Path(destination)
        expected = specification['size']
        metadata = self.metadata_path(path)
        last_error = None
        for attempt in range(3):
            self.check_cancel()
            if path.is_symlink() or metadata.is_symlink():
                raise ComponentError('invalid_path', 'download link')
            offset = path.stat().st_size if path.exists() else 0
            if offset > expected:
                path.unlink()
                offset = 0
            if offset == expected:
                return  # ComponentStore verifies the complete digest next.
            headers = {'Accept-Encoding':'identity', 'User-Agent':'ClicknTranslate components'}
            if offset:
                try:
                    state = json.loads(metadata.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    state = {}
                if (not isinstance(state, dict) or not isinstance(state.get('url'), str)
                        or state['url'] != url):
                    # A failed mirror's unverified prefix must not poison the
                    # next source. Unknown provenance also needs a clean GET.
                    path.unlink(missing_ok=True)
                    metadata.unlink(missing_ok=True)
                    offset = 0
                else:
                    headers['Range'] = f'bytes={offset}-'
                    etag = state.get('etag', '')
                    # Only strong HTTP entity tags belong in If-Range. A
                    # damaged optional cache must not poison every retry with
                    # an unencodable or otherwise invalid request header.
                    if isinstance(etag, str) and re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', etag):
                        headers['If-Range'] = etag
            try:
                with requests.get(url, headers=headers, stream=True, timeout=(15, 15)) as response:
                    if response.status_code == 416:
                        # A rejected saved range must not trap every retry at
                        # the same offset. The full transfer is verified later.
                        path.unlink(missing_ok=True)
                        metadata.unlink(missing_ok=True)
                        raise requests.RequestException('The saved download range was rejected')
                    response.raise_for_status()
                    if response.status_code == 206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        if (not offset or not match or int(match[1]) != offset
                                or int(match[2]) != expected - 1 or int(match[3]) != expected
                                or response.headers.get('Content-Encoding', 'identity') != 'identity'):
                            path.unlink(missing_ok=True)
                            metadata.unlink(missing_ok=True)
                            raise requests.RequestException('Invalid resume response')
                    elif response.status_code == 200:
                        offset = 0  # A server may ignore Range or reject If-Range.
                    else:
                        raise requests.RequestException('Unexpected download status')
                    etag = response.headers.get('ETag', '')
                    metadata.write_text(json.dumps({'url':url, 'etag':etag}), encoding='utf-8')
                    done = offset
                    last_progress = 0
                    with path.open('ab' if offset else 'wb') as output:
                        for block in response.iter_content(8192):
                            self.check_cancel()
                            if not block:
                                continue
                            if done + len(block) > expected:
                                raise ComponentError('download_failed', 'artifact exceeds approved size')
                            output.write(block)
                            done += len(block)
                            now = time.monotonic()
                            if now - last_progress >= .1 or done == expected:
                                self.progress(url, done, expected)
                                last_progress = now
                    if done != expected:
                        raise requests.RequestException('Incomplete download')
                    self.complete(path)
                    return
            except requests.RequestException as error:
                self.check_cancel()
                last_error = error
                deadline = time.monotonic() + .25 * (attempt + 1)
                while time.monotonic() < deadline:
                    self.check_cancel()
                    time.sleep(.025)
        raise last_error  # ComponentStore may try another approved mirror.
