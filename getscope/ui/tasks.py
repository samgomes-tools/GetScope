"""Execução de funções em segundo plano, com sinais para a interface."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_KEEP = set()


class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class FuncWorker(QRunnable):
    def __init__(self, fn, *args, with_progress=False, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw
        self.with_progress = with_progress
        self.sig = _Sig()

    @Slot()
    def run(self):
        try:
            if self.with_progress:
                self.kw["progress"] = lambda a, b: self.sig.progress.emit(int(a), int(b))
            r = self.fn(*self.args, **self.kw)
            self.sig.done.emit(r)
        except Exception as e:  # noqa: BLE001
            self.sig.failed.emit(str(e) or e.__class__.__name__)
        finally:
            _KEEP.discard(self)


def run(fn, *args, done=None, failed=None, progress=None, **kw):
    w = FuncWorker(fn, *args, with_progress=progress is not None, **kw)
    if done:
        w.sig.done.connect(done)
    if failed:
        w.sig.failed.connect(failed)
    if progress:
        w.sig.progress.connect(progress)
    w.setAutoDelete(False)
    _KEEP.add(w)
    QThreadPool.globalInstance().start(w)
    return w
