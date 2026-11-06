"""Stdlib-only generation lease for a resident OCR child."""
from contextlib import contextmanager
import os


class WorkerIsolationUnavailable(RuntimeError):
    pass


def owned_job(process):
    """Windows kills the OCR child if its owning application disappears."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes
    class BasicLimits(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                    ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t),
                    ('max_ws', ctypes.c_size_t), ('active', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]
    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class ExtendedLimits(ctypes.Structure):
        _fields_ = [('basic',BasicLimits), ('io',IoCounters),
                    ('process_memory',ctypes.c_size_t), ('job_memory',ctypes.c_size_t),
                    ('peak_process_memory',ctypes.c_size_t), ('peak_job_memory',ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise WorkerIsolationUnavailable('Cannot own OCR process lifetime')
    limits = ExtendedLimits()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no CPU/memory throttling
    if (not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(process._handle))):
        kernel.CloseHandle(handle)
        raise WorkerIsolationUnavailable('OCR process lifetime cannot be protected in this host')
    return lambda: kernel.CloseHandle(handle)


@contextmanager
def shared_lease(path):
    # Parent already holds this lock during spawn/READY. The child retains its
    # own handle until native model access has ended, including parent death.
    if not path:
        yield
        return
    stream = open(path, 'r+b')
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            class Overlapped(ctypes.Structure):
                _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                            ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                            ('hEvent', wintypes.HANDLE)]
            overlapped = Overlapped()
            lock = ctypes.WinDLL('kernel32', use_last_error=True).LockFileEx
            lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                             wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
            lock.restype = wintypes.BOOL
            if not lock(msvcrt.get_osfhandle(stream.fileno()), 1, 0, 1, 0, ctypes.byref(overlapped)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        yield
    finally:
        stream.close()


def resident_bytes():
    """Conservative per-process memory guard, sampled only after a request."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak_ws', 'ws', 'peak_paged',
                    'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        query.restype = wintypes.BOOL
        if query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            # PrivateUsage is commit charge, not resident RAM. Treating it as
            # RSS discarded a ~100 MiB model after every request and defeated
            # reuse even on systems with plenty of free memory.
            return counters.ws
        return None
    try:
        import sys
        if sys.platform.startswith('linux'):
            with open('/proc/self/statm', encoding='ascii') as stream:
                return int(stream.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        import resource
        # macOS reports bytes. Its high-water mark is deliberately conservative.
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (OSError, ValueError, ImportError):
        return None


def memory_pressure_high():
    """Cheap snapshot; callers sample only while an OCR model is in use."""
    try:
        if os.name == 'nt':
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length',ctypes.c_ulong), ('load',ctypes.c_ulong)] + [
                    (name,ctypes.c_ulonglong) for name in ('physical','available_physical',
                    'pagefile','available_pagefile','virtual','available_virtual','extended')]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.WinDLL('kernel32').GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.load >= 85 or status.available_physical < 512 * 1024**2
        elif os.path.isfile('/proc/meminfo'):
            with open('/proc/meminfo', encoding='ascii') as stream:
                for line in stream:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) < 512 * 1024
    except (OSError, ValueError):
        return True
    return False
