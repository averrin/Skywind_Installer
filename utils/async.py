from PyQt4.QtCore import pyqtSignal, QThread


class Worker(QThread):
    done = pyqtSignal(object)
    error = pyqtSignal(Exception)

    def __init__(self, job):
        QThread.__init__(self)
        self.job = job

    def run(self):
        try:
            ret = self.job()
            self.done.emit(ret)
        except Exception, e:
            self.error.emit(e)


workers_pool = []


def async(job, callback, error_callback=None):
    w = Worker(job)
    workers_pool.append(w)
    w.done.connect(callback)
    if error_callback is not None:
        w.error.connect(error_callback)
    w.start()


def background_job(callback, error_callback=None):
    def decorator(func):
        func.callback = callback
        func.error_callback = error_callback

        def wrapper(self, *args, **kwargs):
            if isinstance(func.callback, basestring):
                callback = getattr(self, func.callback)
            else:
                callback = func.callback

            if func.error_callback is not None:
                if isinstance(func.error_callback, basestring):
                    error_callback = getattr(self, func.error_callback)
                else:
                    error_callback = func.error_callback
            else:
                error_callback = None

            if isinstance(callback, pyqtSignal):
                callback = lambda x: callback.emit(x)

            if isinstance(error_callback, pyqtSignal):
                error_callback = lambda x: error_callback.emit(x)
            return async(lambda: func(self, *args, **kwargs), callback, error_callback=error_callback)

        return wrapper

    return decorator