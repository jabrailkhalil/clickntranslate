"""Persistent local development signing, separate from public Developer ID builds."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile


def signing_directory():
    return Path.home() / 'Library/Application Support/ClicknTranslateBuild/signing'


def run(command):
    result = subprocess.run([str(item) for item in command], capture_output=True, text=True)
    if result.returncode:
        # Never include the command: keychain/password arguments are private.
        raise RuntimeError(f'{Path(command[0]).name} failed: {result.stderr.strip() or result.stdout.strip()}')
    return result.stdout


@contextmanager
def searchable_keychain(keychain):
    # codesign's certificate lookup accepts --keychain, but private-key lookup
    # also needs the keychain in the search list. Restore the list afterwards.
    original = shlex.split(run(['/usr/bin/security', 'list-keychains', '-d', 'user']))
    added = str(keychain) not in original
    if added:
        run(['/usr/bin/security', 'list-keychains', '-d', 'user', '-s', *original, keychain])
    try:
        yield
    finally:
        if added:
            current = shlex.split(run(['/usr/bin/security', 'list-keychains', '-d', 'user']))
            run(['/usr/bin/security', 'list-keychains', '-d', 'user', '-s',
                 *[item for item in current if item != str(keychain)]])


def setup():
    directory = signing_directory()
    if (directory / 'identity.json').exists():
        return load_identity()
    if directory.exists() and any(directory.iterdir()):
        raise RuntimeError(f'Incomplete signing setup preserved at {directory}; refusing to replace its key.')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    keychain = directory / 'development.keychain-db'
    password = secrets.token_urlsafe(36)
    password_file = directory / 'keychain-password'
    descriptor = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(password)
    original_keychains = shlex.split(run(['/usr/bin/security', 'list-keychains', '-d', 'user']))
    try:
        run(['/usr/bin/security', 'create-keychain', '-p', password, keychain])
        run(['/usr/bin/security', 'set-keychain-settings', '-lut', '21600', keychain])
        with tempfile.TemporaryDirectory(prefix='identity-', dir=directory) as temporary:
            stage = Path(temporary)
            config = stage / 'openssl.cnf'
            config.write_text('''[req]
distinguished_name = subject
x509_extensions = code_signing
prompt = no
[subject]
CN = ClicknTranslate Local Development
O = ClicknTranslate Local Development
[code_signing]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
subjectKeyIdentifier = hash
''')
            private_key, certificate, archive = stage / 'key.pem', directory / 'certificate.pem', stage / 'identity.p12'
            run(['/usr/bin/openssl', 'req', '-new', '-x509', '-sha256', '-newkey', 'rsa:3072', '-nodes',
                 '-days', '3650', '-config', config, '-keyout', private_key, '-out', certificate])
            run(['/usr/bin/openssl', 'pkcs12', '-export', '-inkey', private_key,
                 '-in', certificate, '-out', archive, '-passout', f'file:{password_file}'])
            run(['/usr/bin/security', 'import', archive, '-k', keychain, '-f', 'pkcs12',
                 '-P', password, '-x', '-T', '/usr/bin/codesign'])
        run(['/usr/bin/security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:',
             '-s', '-k', password, keychain])
        fingerprint = run(['/usr/bin/openssl', 'x509', '-in', certificate, '-noout', '-fingerprint', '-sha1'])
        identity = {'sha1': fingerprint.strip().split('=')[-1].replace(':', ''),
                    'keychain': str(keychain), 'certificate': str(certificate),
                    'kind': 'local self-signed development', 'notarized': False}
        (directory / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        return identity
    finally:
        # security create-keychain may add its result to the user's search list.
        # Keep all other entries, including any concurrent additions, in order.
        current = shlex.split(run(['/usr/bin/security', 'list-keychains', '-d', 'user']))
        filtered = [item for item in current if Path(item) != keychain]
        if str(keychain) not in original_keychains and filtered != current:
            run(['/usr/bin/security', 'list-keychains', '-d', 'user', '-s', *filtered])


def load_identity():
    directory = signing_directory()
    metadata = directory / 'identity.json'
    if not metadata.is_file():
        raise RuntimeError('Stable signing is not configured. Run tools/macos_signing.py setup once, '
                           'or provide MACOS_CODESIGN_IDENTITY for an existing Apple identity.')
    identity = json.loads(metadata.read_text())
    # Restore the same private identity under another builder's home directory.
    identity['keychain'] = str(directory / 'development.keychain-db')
    identity['certificate'] = str(directory / 'certificate.pem')
    certificate = Path(identity['certificate'])
    pem = certificate.read_text()
    import ssl
    actual = hashlib.sha1(ssl.PEM_cert_to_DER_cert(pem)).hexdigest().upper()
    if actual != identity['sha1'] or not Path(identity['keychain']).is_file():
        raise RuntimeError('Local signing identity changed or is incomplete; refusing an ad-hoc fallback.')
    return identity


def enable_signing(identity):
    if identity.get('codesign_trust'):
        return identity
    # Trust this one leaf only for /usr/bin/codesign's code-signing policy in
    # the current user's domain. No SSL trust, system roots or Gatekeeper rules.
    run(['/usr/bin/security', 'add-trusted-cert', '-r', 'trustRoot', '-p', 'codeSign',
         '-a', '/usr/bin/codesign', '-k', identity['keychain'], identity['certificate']])
    identity['codesign_trust'] = 'user domain, codeSign policy, /usr/bin/codesign only'
    (signing_directory() / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    return identity


def sign(app):
    identity = load_identity()
    password = (signing_directory() / 'keychain-password').read_text()
    run(['/usr/bin/security', 'unlock-keychain', '-p', password, identity['keychain']])
    # PyInstaller has signed nested code already. Sign the outer GUI bundle last,
    # retaining a certificate-bound identity instead of an executable cdhash.
    # Preserve the development bundle's existing runtime behavior. Hardened
    # runtime/notarization belong to the separate Developer ID build path.
    with searchable_keychain(identity['keychain']):
        run(['/usr/bin/codesign', '--force', '--sign', identity['sha1'], '--keychain', identity['keychain'],
             '--timestamp=none', app])
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
    return identity


if __name__ == '__main__':
    if sys.platform != 'darwin':
        raise SystemExit('Native macOS signing requires a Mac.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'check', 'sign'])
    parser.add_argument('app', nargs='?')
    args = parser.parse_args()
    if args.action == 'sign' and not args.app:
        parser.error('sign requires an .app path')
    result = enable_signing(setup()) if args.action == 'setup' else sign(args.app) if args.action == 'sign' else load_identity()
    print(json.dumps(result, indent=2))
