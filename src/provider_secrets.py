"""Keep API keys in the OS vault, never in exported application preferences."""
import sys
import threading
import time

_SESSION = {}
_SERVICE = 'ClicknTranslate.API'
_MISSING = {}
_MISSING_TTL = 15
_STATE_LOCK = threading.RLock()
_WRITE_LOCKS = {}


def _vault():
    # Choose a native encrypted backend explicitly. Never accept a third-party
    # plaintext keyring through automatic plugin discovery.
    if sys.platform == 'win32':
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    if sys.platform == 'darwin':
        from keyring.backends.macOS import Keyring
        return Keyring()
    from keyring.backends.SecretService import Keyring
    return Keyring()


def account(provider, endpoint):
    import hashlib
    return provider + ':' + hashlib.sha256(endpoint.rstrip('/').encode()).hexdigest()


def get_key(provider, endpoint):
    name = account(provider, endpoint)
    with _STATE_LOCK:
        if name in _SESSION:
            return _SESSION[name]
        if _MISSING.get(name, 0) > time.monotonic():
            return ''
    try:
        value = _vault().get_password(_SERVICE, name) or ''
    except Exception:
        with _STATE_LOCK:
            return _SESSION.get(name, '')
    with _STATE_LOCK:
        # A UI rotation/deletion can finish while this native read is waiting.
        # Its newer session value (including an empty tombstone) wins.
        if name in _SESSION:
            return _SESSION[name]
        if value:
            _SESSION[name] = value
            _MISSING.pop(name, None)
        else:
            if len(_MISSING) >= 128:
                _MISSING.pop(next(iter(_MISSING)))
            _MISSING[name] = time.monotonic() + _MISSING_TTL
        return value


def set_key(provider, endpoint, value):
    """Return whether persistence succeeded; unavailable vaults use RAM only."""
    name = account(provider, endpoint)
    with _STATE_LOCK:
        writer = _WRITE_LOCKS.setdefault(name, threading.Lock())
    # Native operations stay outside the shared state lock; only competing
    # writes to this one account must retain the same RAM/vault ordering.
    with writer:
        with _STATE_LOCK:
            _MISSING.pop(name, None)
            _SESSION[name] = value
        try:
            vault = _vault()
            if value:
                vault.set_password(_SERVICE, name, value)
            elif vault.get_password(_SERVICE, name):
                vault.delete_password(_SERVICE, name)
            return True
        except Exception:
            return False
