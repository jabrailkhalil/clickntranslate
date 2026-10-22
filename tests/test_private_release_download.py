"""Draft-update QA must never send its repository token to the download CDN."""
from unittest import mock
from urllib.error import HTTPError
import pytest
from tools import qa_published_update as qa


def test_draft_asset_redirect_starts_a_request_without_authorization(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'test-only-token')
    asset = {'url': f'https://api.github.com/repos/{qa.REPO}/releases/assets/123'}
    location = 'https://release-assets.githubusercontent.com/path/file.zip?test=1'
    redirect = HTTPError(asset['url'], 302, 'Found', {'Location': location}, None)
    with mock.patch.object(qa.urllib.request, 'build_opener') as opener, \
         mock.patch.object(qa.urllib.request, 'urlopen') as public:
        opener.return_value.open.side_effect = redirect
        assert qa.asset_response({'draft': True}, asset) is public.return_value
        initial = opener.return_value.open.call_args.args[0]
        assert initial.get_header('Authorization') == 'Bearer test-only-token'
        assert public.call_args.args == (location,)
        assert public.call_args.kwargs == {'timeout': 120}


@pytest.mark.parametrize('location', ['http://release-assets.githubusercontent.com/file',
                                    'https://githubusercontent.com.attacker.test/file'])
def test_untrusted_draft_redirect_is_rejected(monkeypatch, location):
    monkeypatch.setenv('GH_TOKEN', 'test-only-token')
    asset = {'url': f'https://api.github.com/repos/{qa.REPO}/releases/assets/123'}
    with mock.patch.object(qa.urllib.request, 'build_opener') as opener, \
         mock.patch.object(qa.urllib.request, 'urlopen') as public:
        opener.return_value.open.side_effect = HTTPError(asset['url'], 302, 'Found', {'Location': location}, None)
        with pytest.raises(RuntimeError, match='redirect'):
            qa.asset_response({'draft': True}, asset)
        public.assert_not_called()
