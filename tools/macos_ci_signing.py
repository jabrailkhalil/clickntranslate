"""Transfer the existing encrypted signer to Actions; never generate a CI key."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile

from macos_signing import load_identity, run, sign, signing_directory


ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE = ROOT / 'packaging/macos/release-certificate.pem'
EXPECTED_SHA1 = 'E5E6A8042F96479E560AED29881A6F06D4D374A2'
BUNDLE_ID = 'io.github.jabrailkhalil.clickntranslate'
REPOSITORY = 'jabrailkhalil/clickntranslate'
KEYCHAIN_SECRET = 'MACOS_SIGNING_KEYCHAIN_BASE64'
PASSWORD_SECRET = 'MACOS_SIGNING_KEYCHAIN_PASSWORD'
SYSTEM_KEYCHAIN = '/Library/Keychains/System.keychain'


def validate_certificate():
    pem = CERTIFICATE.read_text()
    if hashlib.sha1(ssl.PEM_cert_to_DER_cert(pem)).hexdigest().upper() != EXPECTED_SHA1:
        raise RuntimeError('Release certificate differs from the permanent signer.')
    return pem


def ci_directory():
    # Cleanup and administrator trust are restricted to an ephemeral Actions
    # runner. Never apply these operations to a developer's signing directory.
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('RUNNER_TEMP'):
        raise RuntimeError('This operation requires a GitHub Actions runner.')
    expected = Path(os.environ['RUNNER_TEMP']).resolve() / 'clickntranslate-signing'
    directory = signing_directory()
    if directory.is_symlink() or directory.resolve() != expected:
        raise RuntimeError('CI signing directory must be RUNNER_TEMP/clickntranslate-signing.')
    return directory


def private_file(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(value)


def restore():
    directory = ci_directory()
    pem = validate_certificate()
    # Remove secrets from subprocess environments as soon as they are read.
    encoded = os.environ.pop(KEYCHAIN_SECRET, '')
    password = os.environ.pop(PASSWORD_SECRET, '')
    if not encoded or not password:
        raise RuntimeError('Permanent signing secrets are missing; refusing ad-hoc release signing.')
    keychain_bytes = base64.b64decode(encoded, validate=True)
    directory.mkdir(mode=0o700, exist_ok=False)
    private_file(directory / '.actions-signer', b'ClicknTranslate CI signer\n')
    keychain = directory / 'development.keychain-db'
    private_file(keychain, keychain_bytes)
    private_file(directory / 'keychain-password', password.encode())
    private_file(directory / 'certificate.pem', pem.encode())
    run(['/usr/bin/security', 'unlock-keychain', '-p', password, keychain])
    run(['/usr/bin/security', 'set-keychain-settings', '-lut', '21600', keychain])
    run(['/usr/bin/security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:',
         '-s', '-k', password, keychain])
    # The encrypted keychain carries the key, but trust settings are per Mac.
    # GitHub-hosted runners allow passwordless sudo. Trust this public leaf only
    # for codesign, on the disposable runner; no SSL or Gatekeeper exemptions.
    run(['/usr/bin/sudo', '-n', '/usr/bin/security', 'add-trusted-cert', '-d',
         '-r', 'trustRoot', '-p', 'codeSign', '-a', '/usr/bin/codesign',
         '-k', SYSTEM_KEYCHAIN, directory / 'certificate.pem'])
    identity = {'sha1': EXPECTED_SHA1, 'keychain': str(keychain),
                'certificate': str(directory / 'certificate.pem'),
                'kind': 'persistent self-signed release', 'notarized': False,
                'codesign_trust': 'ephemeral CI admin domain, codeSign, /usr/bin/codesign only'}
    private_file(directory / 'identity.json', (json.dumps(identity, indent=2) + '\n').encode())
    return {'restored': True, 'sha1': load_identity()['sha1']}


def cleanup():
    directory = ci_directory()
    if not directory.exists():
        return {'cleaned': True}
    if not (directory / '.actions-signer').is_file():
        raise RuntimeError('Refusing to remove a signing directory not created by this job.')
    keychain = directory / 'development.keychain-db'
    errors = []
    commands = []
    current = shlex.split(run(['/usr/bin/security', 'list-keychains', '-d', 'user']))
    if str(keychain) in current:
        commands.append(['/usr/bin/security', 'list-keychains', '-d', 'user', '-s',
                         *[item for item in current if item != str(keychain)]])
    certificate = directory / 'certificate.pem'
    if certificate.exists():
        commands.extend([
            ['/usr/bin/sudo', '-n', '/usr/bin/security', 'remove-trusted-cert', '-d', certificate],
            ['/usr/bin/sudo', '-n', '/usr/bin/security', 'delete-certificate', '-Z', EXPECTED_SHA1, SYSTEM_KEYCHAIN],
        ])
    if keychain.exists():
        commands.append(['/usr/bin/security', 'delete-keychain', keychain])
    try:
        for command in commands:
            try:
                run(command)
            except RuntimeError as error:
                errors.append(str(error))
    finally:
        shutil.rmtree(directory)
    if errors:
        raise RuntimeError('Private files removed; keychain/trust cleanup reported: ' + '; '.join(errors))
    return {'cleaned': True}


def requirement():
    return f'identifier "{BUNDLE_ID}" and certificate root = H"{EXPECTED_SHA1.lower()}"'


def verify(app):
    validate_certificate()
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', '-R', '=' + requirement(), app])
    return {'app': str(app), 'sha1': EXPECTED_SHA1, 'requirement': requirement(),
            'architecture': platform.machine(), 'notarized': False}


def probe():
    """Check key portability and update identity, without exercising the app."""
    load_identity()
    with tempfile.TemporaryDirectory(prefix='signing-probe-') as temporary:
        stage = Path(temporary)
        app = stage / 'SigningProbe.app'
        executable = app / 'Contents/MacOS/SigningProbe'
        executable.parent.mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': BUNDLE_ID, 'CFBundleExecutable': 'SigningProbe',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
        }))
        requirements, hashes = [], []
        for version in (1, 2):
            source = stage / 'probe.c'
            source.write_text(f'int main(void) {{ return {version}; }}\n')
            run(['/usr/bin/clang', source, '-o', executable])
            hashes.append(hashlib.sha256(executable.read_bytes()).hexdigest())
            sign(app)
            verify(app)
            result = subprocess.run(['/usr/bin/codesign', '-d', '-r-', str(app)],
                                    capture_output=True, text=True, check=True)
            requirements.append(next(line for line in (result.stdout + result.stderr).splitlines()
                                     if line.startswith('designated =>')))
        if hashes[0] == hashes[1] or requirements[0] != requirements[1]:
            raise RuntimeError('Changed executable did not retain the same signing requirement.')
        run(['/usr/bin/codesign', '--force', '--sign', '-', app])
        run(['/usr/bin/codesign', '--verify', '--strict', app])
        foreign = subprocess.run(['/usr/bin/codesign', '--verify', '-R', '=' + requirement(), str(app)],
                                 capture_output=True)
        if foreign.returncode == 0:
            raise RuntimeError('Ad-hoc replacement incorrectly passed the certificate requirement.')
        return {'architecture': platform.machine(), 'macos': platform.mac_ver()[0],
                'sha1': EXPECTED_SHA1, 'requirement': requirements[0],
                'changed_code_same_identity': True, 'ad_hoc_rejected': True, 'notarized': False}


def upload(gh):
    validate_certificate()
    identity = load_identity()
    if identity['sha1'] != EXPECTED_SHA1:
        raise RuntimeError('Local identity differs from the repository release certificate.')
    # Confirm CLI authentication and repository administration without reading
    # or printing a token. gh secret set encrypts each stdin value locally.
    repository = json.loads(run([gh, 'api', f'repos/{REPOSITORY}']))
    if not repository.get('permissions', {}).get('admin'):
        raise RuntimeError('GitHub CLI needs repository administrator access to configure secrets.')
    password = (signing_directory() / 'keychain-password').read_bytes()
    keychain = Path(identity['keychain'])
    run(['/usr/bin/security', 'lock-keychain', keychain])
    try:
        encoded = base64.b64encode(keychain.read_bytes())
    finally:
        run(['/usr/bin/security', 'unlock-keychain', '-p', password.decode(), keychain])
    if len(encoded) > 48 * 1024:
        raise RuntimeError('Encrypted keychain exceeds the GitHub Actions secret size limit.')
    for name, value in ((KEYCHAIN_SECRET, encoded), (PASSWORD_SECRET, password)):
        result = subprocess.run([gh, 'secret', 'set', name, '--repo', REPOSITORY],
                                input=value, capture_output=True)
        if result.returncode:
            raise RuntimeError(f'Could not store {name}; check GitHub CLI repository access.')
    return {'repository': REPOSITORY, 'stored_secrets': [KEYCHAIN_SECRET, PASSWORD_SECRET],
            'sha1': EXPECTED_SHA1}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['restore', 'cleanup', 'probe', 'verify', 'upload'])
    parser.add_argument('--app', type=Path)
    parser.add_argument('--gh', default='gh')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Signing operations require native macOS.')
    if args.action == 'verify' and not args.app:
        parser.error('verify requires --app')
    result = (verify(args.app) if args.action == 'verify' else upload(args.gh)
              if args.action == 'upload' else globals()[args.action]())
    output = json.dumps(result, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print(output, end='')
