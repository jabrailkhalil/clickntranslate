"""App-owned immutable generations and crash-safe component activation."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import time
import uuid
import zipfile

from component_catalog import ComponentError, SAFE_ID, safe_relative


@contextmanager
def _file_lock(path, shared=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(path, 'a+b')
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'0')
                stream.flush()
            # CRT read locks are exclusive on Windows. LockFileEx is required
            # for genuinely shared leases held by concurrent OCR requests.
            class Overlapped(ctypes.Structure):
                _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                            ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                            ('hEvent', wintypes.HANDLE)]
            overlapped = Overlapped()
            lock_file = ctypes.WinDLL('kernel32', use_last_error=True).LockFileEx
            lock_file.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            lock_file.restype = wintypes.BOOL
            if not lock_file(msvcrt.get_osfhandle(stream.fileno()), 1 | (0 if shared else 2),
                             0, 1, 0, ctypes.byref(overlapped)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            import fcntl
            fcntl.flock(stream.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except OSError as exc:
        stream.close()
        raise ComponentError('operation_busy') from exc
    try:
        yield
    finally:
        stream.close()


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class ComponentStore:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @contextmanager
    def lock(self):
        """One writer across all app/installer processes, with immediate feedback."""
        self.root.mkdir(parents=True, exist_ok=True)
        with _file_lock(self.root / 'install.lock'):
            yield

    @contextmanager
    def database(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.root / 'state.sqlite'), timeout=5)
        db.execute('PRAGMA synchronous=FULL')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS active(component TEXT PRIMARY KEY, generation TEXT, previous TEXT);
            CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, component TEXT, generation TEXT, phase TEXT);
        ''')
        try:
            with db:
                yield db
        finally:
            db.close()

    def generation(self, name):
        if not SAFE_ID.fullmatch(str(name or '')):
            raise ComponentError('invalid_generation')
        parent = self.root / 'generations'
        folder = (parent / name).resolve()
        if not folder.is_relative_to(parent.resolve()) or folder == parent.resolve():
            raise ComponentError('invalid_generation')
        return folder

    @contextmanager
    def lease(self, generation):
        folder = self.generation(generation)
        try:
            with _file_lock(self.root / 'leases' / (generation + '.lock'), shared=True):
                if not folder.is_dir():
                    raise ComponentError('component_removed')
                yield
        finally:
            if (self.root / 'gc-pending').exists():
                try:
                    with self.lock():
                        self.collect_unused()
                except ComponentError:
                    pass  # another operation owns the store and will collect later

    def collect_unused(self):
        """Called under writer lock; preserve active/previous and running workers."""
        with self.database() as db:
            keep = {r[0] for r in db.execute('SELECT generation FROM active')}
            keep.update(r[0] for r in db.execute('SELECT previous FROM active') if r[0])
            keep.update(r[0] for r in db.execute('SELECT generation FROM operations'))
        incomplete = False
        for folder in (self.root / 'generations').glob('*'):
            if not folder.is_dir() or folder.name in keep or not SAFE_ID.fullmatch(folder.name):
                continue
            if not (folder / 'receipt.json').is_file():
                continue  # unregistered files are not silently treated as ours
            try:
                checked = self.generation(folder.name)
                with _file_lock(self.root / 'leases' / (folder.name + '.lock')):
                    shutil.rmtree(checked)
            except (ComponentError, OSError):
                incomplete = True
        referenced = set()
        for receipt_path in (self.root / 'generations').glob('*/receipt.json'):
            try:
                referenced.update(item['sha256'] for item in json.loads(receipt_path.read_text(encoding='utf-8'))['files'])
            except (ValueError, OSError, KeyError):
                return  # unknown receipt: preserve cache rather than guessing
        for path in (self.root / 'objects').glob('*'):
            if path.name not in referenced and path.is_file():
                try:
                    checked = self.object_path(path.name)
                    if not checked.is_symlink():
                        checked.unlink()
                except (ComponentError, OSError):
                    incomplete = True
        marker = self.root / 'gc-pending'
        if incomplete:
            marker.touch()
        else:
            marker.unlink(missing_ok=True)

    def active(self, component):
        if not (self.root / 'state.sqlite').is_file():
            return None
        with self.database() as db:
            row = db.execute('SELECT generation FROM active WHERE component=?', (component,)).fetchone()
        if not row:
            return None
        folder = self.generation(row[0])
        try:
            receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
            if receipt['component'] != component or receipt['generation'] != row[0]:
                raise ValueError('receipt mismatch')
            python = folder / safe_relative(receipt['python'])
            worker = folder / safe_relative(receipt['worker'])
            if not python.is_file() or not worker.is_file():
                raise ValueError('incomplete runtime')
            return {'folder': folder, 'command': [str(python), str(worker)], 'receipt': receipt}
        except (OSError, ValueError, KeyError) as exc:
            raise ComponentError('installed_component_damaged', component) from exc

    def recover(self):
        """Run under lock: abandoned candidates never replaced the active pointer."""
        with self.database() as db:
            rows = db.execute('SELECT id, generation, phase FROM operations').fetchall()
            live = {r[0] for r in db.execute('SELECT generation FROM active')}
            live.update(r[0] for r in db.execute('SELECT previous FROM active') if r[0])
            for operation, generation, phase in rows:
                if generation not in live:
                    folder = self.generation(generation)
                    if folder.exists():
                        shutil.rmtree(folder)
                db.execute('DELETE FROM operations WHERE id=?', (operation,))

    def object_path(self, digest):
        from component_catalog import SHA256
        if not SHA256.fullmatch(digest):
            raise ComponentError('invalid_artifact')
        return self.root / 'objects' / digest

    def obtain(self, digest, artifact, download, check_cancel):
        path = self.object_path(digest)
        if path.is_file() and path.stat().st_size == artifact['size'] and file_digest(path) == digest:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        last_error = None
        for url in artifact['urls']:
            check_cancel()
            partial = self.root / 'downloads' / digest
            partial.parent.mkdir(parents=True, exist_ok=True)
            try:
                download(url, str(partial))
                check_cancel()
                if partial.stat().st_size != artifact['size'] or file_digest(partial) != digest:
                    partial.unlink(missing_ok=True)
                    raise ComponentError('checksum_mismatch', digest)
                os.replace(partial, path)
                return path
            except ComponentError:
                raise
            except Exception as exc:
                check_cancel()  # cancellation is never swallowed as a mirror error
                last_error = exc
        raise ComponentError('download_failed', type(last_error).__name__) from last_error

    @staticmethod
    def extract(archive, destination, limit):
        """Restrict paths, Windows device names, links, collisions and zip bombs."""
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > 100000 or sum(i.file_size for i in entries) > limit:
                raise ComponentError('unsafe_archive', 'expanded size')
            names = set()
            for info in entries:
                safe_relative(info.orig_filename.rstrip('/'))
                name = info.filename.rstrip('/')
                safe_relative(name)
                for part in name.split('/'):
                    device = part.split('.')[0].upper()
                    if part.endswith((' ', '.')) or device in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1,10)), *('LPT'+str(n) for n in range(1,10))}:
                        raise ComponentError('unsafe_archive', 'reserved path')
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or name.casefold() in names:
                    raise ComponentError('unsafe_archive', 'link/duplicate')
                names.add(name.casefold())
                target = destination.joinpath(*name.split('/'))
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(info) as source, open(target, 'xb') as output:
                        shutil.copyfileobj(source, output)
                        output.flush()
                        os.fsync(output.fileno())
                    if mode & stat.S_IXUSR:
                        target.chmod(target.stat().st_mode | stat.S_IXUSR)

    def install(self, catalog, bundle, download, validate, check_cancel=lambda: None, progress=lambda *_: None):
        """The caller holds lock, including catalog refresh and candidate selection."""
        self.recover()
        try:
            old = self.active(bundle['component'])
        except ComponentError:
            old = None
        if old and old['receipt']['bundle'] == bundle['id']:
            validate(old['folder'], old['receipt'])
            return old
        expanded = sum(catalog['artifacts'][f['sha256']].get('unpacked_size', catalog['artifacts'][f['sha256']]['size']) for f in bundle['files'])
        compressed = sum(catalog['artifacts'][f['sha256']]['size'] for f in bundle['files'] if not self.object_path(f['sha256']).exists())
        if shutil.disk_usage(self.root).free < expanded + compressed + 64 * 1024**2:
            raise ComponentError('not_enough_space')
        generation = uuid.uuid4().hex
        folder = self.generation(generation)
        receipt = {**bundle, 'bundle': bundle['id'], 'generation': generation, 'installed_at': int(time.time())}
        with self.database() as db:
            db.execute('INSERT INTO operations VALUES (?,?,?,?)', (generation, bundle['component'], generation, 'preparing'))
        committed = False
        try:
            folder.mkdir(parents=True)
            for index, item in enumerate(bundle['files']):
                check_cancel()
                progress(index, len(bundle['files']))
                artifact = catalog['artifacts'][item['sha256']]
                source = self.obtain(item['sha256'], artifact, download, check_cancel)
                target = folder / safe_relative(item['destination'])
                if item['kind'] == 'zip':
                    self.extract(source, target, artifact['unpacked_size'])
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    with open(target, 'r+b') as synced:
                        os.fsync(synced.fileno())
            check_cancel()
            validate(folder, receipt)
            check_cancel()
            with open(folder / 'receipt.json', 'w', encoding='utf-8') as output:
                json.dump(receipt, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            with self.database() as db:
                row = db.execute('SELECT generation,previous FROM active WHERE component=?', (bundle['component'],)).fetchone()
                previous = row[0] if row and old else row[1] if row else None
                db.execute('INSERT OR REPLACE INTO active VALUES (?,?,?)', (bundle['component'], generation, previous))
                db.execute('DELETE FROM operations WHERE id=?', (generation,))
            committed = True
            try:
                self.collect_unused()
            except (OSError, ComponentError):
                (self.root / 'gc-pending').touch()
            return self.active(bundle['component'])
        except BaseException:
            if committed:
                raise  # never delete a generation after its active pointer was committed
            # Keep the durable operation for startup recovery if deletion fails.
            try:
                shutil.rmtree(folder)
                with self.database() as db:
                    db.execute('DELETE FROM operations WHERE id=?', (generation,))
            except OSError:
                pass
            raise

    def remove(self, component):
        """Deactivate, then free only files not held by another component/worker."""
        with self.lock():
            with self.database() as db:
                db.execute('DELETE FROM active WHERE component=?', (component,))
            self.collect_unused()

    def rollback(self, component, validate, catalog):
        with self.lock(), self.database() as db:
            row = db.execute('SELECT generation, previous FROM active WHERE component=?', (component,)).fetchone()
            if not row or not row[1]:
                raise ComponentError('no_previous_version')
            folder = self.generation(row[1])
            receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
            allowed = any(item['id'] == receipt['bundle'] and item['component'] == component
                          and not item.get('revoked') for item in catalog['bundles'])
            if not allowed:
                raise ComponentError('previous_version_not_approved')
            validate(folder, receipt)
            db.execute('UPDATE active SET generation=?,previous=? WHERE component=?', (row[1], row[0], component))
