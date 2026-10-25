"""Copy feedback receiver shared by imported main and the __main__ entry point.

Registration happens on the GUI thread. Workers only emit the registered Qt
signal; they never enumerate or inspect application widgets.
"""
import weakref


_receiver_ref = None


def register_copy_feedback(receiver):
    global _receiver_ref
    _receiver_ref = weakref.ref(receiver)


def emit_copy_feedback(language, *, failed=False):
    global _receiver_ref
    reference = _receiver_ref
    receiver = reference() if reference is not None else None
    if receiver is None:
        return False
    try:
        signal = getattr(receiver, '_copy_failure_signal' if failed else '_copy_notification_signal', None)
        if signal is None:
            return False
        signal.emit(language)
        return True
    except RuntimeError:
        # The native QObject can be deleted while its Python wrapper still
        # exists. Do not clear a newer owner's registration during shutdown.
        if _receiver_ref is reference:
            _receiver_ref = None
        return False
