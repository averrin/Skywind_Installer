import sys
from time import sleep
from PyQt4.QtGui import QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel, QProgressBar, QHBoxLayout, QPushButton, QToolBar, QDialog, QGridLayout, QMessageBox, QFileDialog, QFormLayout, QToolButton, QIcon
from PyQt4.QtCore import QThread, pyqtSignal, Qt, pyqtProperty, QUrl
import urllib2
from urlparse import urlparse, parse_qs
import requests

from downloader.HTTPDownload import HTTPDownload, Abort

"""
    http://download.thinkbroadband.com/200MB.zip
    
    https://docs.google.com/file/d/0B8F9egY3lyGdUUhtZnVydmJIVjQ/edit
"""

import os

temp_folder = 'config/temp/'
if not os.path.isdir(temp_folder):
    os.mkdir(temp_folder)

if not os.path.isfile(temp_folder + 'suspended.list'):
    with open(temp_folder + 'suspended.list', 'w') as f:
        f.write('')


class Plugin(object):
    def processURL(self, url, dest):
        return url, dest


GD_API_ID = '836414335615.apps.googleusercontent.com'
GD_API_SECRET = 'G45aJ_akqQT-EPSw9AEeFQT8'
GD_API_CALLBACK = 'urn:ietf:wg:oauth:2.0:oob'


class GDPlugin(Plugin):
    def processURL(self, url, dest):
        size = None

        self.url = url
        self.dest = dest

        if url.startswith('https://docs.google'):

            self.auth_url = 'https://accounts.google.com/o/oauth2/auth?scope=https://www.googleapis.com/auth/drive&response_type=code&redirect_uri=%s&client_id=%s' % (
                GD_API_CALLBACK, GD_API_ID
            )

            if os.path.isfile(temp_folder + 'key'):
                return self._process(url, dest)
            else:
                self.showAuthDialog()

        return url, dest, None, 0


    def _process(self, url, dest):
        headers = None
        size = 0
        with open('config/temp/key', 'r') as f:
            token = f.read().split('#')[1]

            parsed = urlparse(url)
            try:
                file_id = parse_qs(parsed.query)['id'][0]
            except KeyError:
                file_id = url.split('/')[-1]
                if file_id == 'edit':
                    file_id = url.split('/')[-2]

            api_url = 'https://www.googleapis.com/drive/v2/files/%s?access_token=%s' % (file_id, token)
            r = requests.get(api_url)
            r = r.json()

            try:
                url = r['downloadUrl'] + '&access_token=' + token
                dest = os.path.join('.', r['originalFilename'])
                size = int(r['fileSize'])
            except KeyError:

                self.renewToken()
                return self._process(url, dest)

            fn = os.path.basename(dest)
            if os.path.isfile(temp_folder + fn + '.chunk0'):
                arrived = os.path.getsize(temp_folder + fn + '.chunk0')
                headers = ['Range: bytes=%s-%s' % (arrived, size)]

        return url, dest, headers, size

    def renewToken(self):
        with open('config/temp/key', 'r') as f:
            auth = f.read().split('#')
            refresh_token = auth[2]
            refresh_url = 'https://accounts.google.com/o/oauth2/token'
            r = requests.post(refresh_url, data={
                'refresh_token': refresh_token,
                'client_id': GD_API_ID,
                'client_secret': GD_API_SECRET,
                'grant_type': 'refresh_token'})

            print(r)
            token = r.json()['access_token']

            auth[1] = token

        with open('config/temp/key', 'w') as f:
            f.write('#'.join(auth))

    def showAuthDialog(self):
        from PyQt4.QtWebKit import QWebView

        win = QWebView()
        win.titleChanged.connect(self.getKey)
        win.show()
        win.load(QUrl(self.auth_url))

    def getKey(self, title):
        title = str(title.toUtf8())
        print(title)
        if title.startswith('Success code='):
            code = title[len('Success code='):]
            print(code)

            token_url = "https://accounts.google.com/o/oauth2/token"
            r = requests.post(token_url, data={
                'code': code,
                'client_id': GD_API_ID,
                'client_secret': GD_API_SECRET,
                'redirect_uri': GD_API_CALLBACK,
                'grant_type': 'authorization_code'})
            auth = r.json()

            try:
                token = auth['access_token']
                refresh_token = auth['refresh_token']

                with open('config/temp/key', 'w') as f:
                    f.write(code + '#' + token + '#' + refresh_token)
                self._process(self.url, self.dest)
            except KeyError:
                print(auth)


class Downloader(QThread):
    started = pyqtSignal()
    stopped = pyqtSignal()
    flush = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(Exception)
    progress = pyqtSignal(int, int, int, int)

    def __init__(self, src, dest, suspended=False):
        self.src = src
        self.dest = dest
        self.suspended = False

        self.gd = GDPlugin()

        src, self.dest, headers, size = self.gd.processURL(self.src, self.dest)

        QThread.__init__(self)
        self.dwnld = HTTPDownload(
            src, self.dest,
            callback=self.progress.emit,
            bf_callback=self.flush.emit,
            abort_callback=self.stopped.emit,
            suspended=self.suspended,
            headers=headers,
            gd=size
        )

    def run(self):
        self.started.emit()
        try:
            self.dwnld.download(chunks=3, resume=True)
            self.finished.emit()
        except Exception, e:
            if not isinstance(e, Abort):
                import traceback

                traceback.print_exc()
                # raise e
                self.error.emit(e)


class DMItem(QWidget):
    removed = pyqtSignal(object)

    def __init__(self, src, dest, suspended=False):

        QWidget.__init__(self)

        self.src = src
        self.dest = dest
        self.suspended = suspended

        self.initDownloader()

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel('<b>Downloading:</b> %s' % os.path.split(self.dest)[-1]))

        self.controls = QWidget()
        self.controls.setLayout(QHBoxLayout())

        self.progressBar = QProgressBar()
        self.toggle = QToolButton()
        self.toggle.setIcon(QIcon('config/icons/pause.png'))
        self.toggle.clicked.connect(self.toggleDownloading)

        self.remove_button = QToolButton()
        self.remove_button.setIcon(QIcon('config/icons/remove.png'))
        self.remove_button.clicked.connect(self.remove)

        self.controls.layout().addWidget(self.progressBar)
        self.controls.layout().addWidget(self.toggle)
        self.controls.layout().addWidget(self.remove_button)

        self.layout().addWidget(self.controls)
        self.progressBar.setMaximum(100)
        self.info = QLabel('')
        self.layout().addWidget(self.info)

        self.running = False
        self.done = False

    def initDownloader(self):
        self.d = Downloader(self.src, self.dest, self.suspended)
        self.d.progress.connect(self.progress)
        self.d.error.connect(self.error)
        self.d.finished.connect(self.finish)
        self.d.flush.connect(self.flush)
        self.d.stopped.connect(self.stopped)

        self.dest = self.d.dest

    def stopped(self):
        self.info.setText('<b>Paused:</b> %s/%s [%s%%].' % (
            self.sizeof_fmt(self.d.dwnld.arrived), self.sizeof_fmt(self.d.dwnld.size), self.d.dwnld.percent)
        )

    def toggleDownloading(self):
        if self.running:
            if not self.d.dwnld.abort:
                self.d.dwnld.abort = True
            else:
                self.initDownloader()
                self.start()
        else:
            self.start()

        # self.toggle.setText('Start' if self.d.dwnld.abort else 'Pause')
        self.toggle.setIcon(QIcon('config/icons/%s.png' % ('start' if self.d.dwnld.abort else 'pause')))

    def error(self, e):
        if e and e is not None and not isinstance(e, Abort):
            self.finish()
            if type(e) not in [basestring, Exception]:
                try:
                    e = e[1]
                except IndexError:
                    pass
            self.info.setText('<b style="color: red">%s</b>' % e)

    def flush(self):
        self.toggle.setEnabled(False)
        self.progressBar.setMaximum(0)
        self.info.setText('<b>Dumping to:</b> %s' % self.dest)

    def finish(self):
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(100)
        self.info.setText('<b>Done. Saved to</b> %s' % self.dest)
        self.done = True
        self.running = False

    def remove(self):
        self.d.dwnld.abort = True
        self.setVisible(False)
        self.running = False
        self.removed.emit(self)

    def start(self):
        self.d.start()
        self.running = True

    def sizeof_fmt(self, num):
        for x in ['bytes', 'KB', 'MB', 'GB']:
            if 1024.0 > num > -1024.0:
                return "%3.1f%s" % (num, x)
            num /= 1024.0
        return "%3.1f%s" % (num, 'TB')

    def progress(self, speed, arrived, percent, total):
        self.progressBar.setValue(percent)

        self.info.setText('<b>Done:</b> %s/%s [%s%%]. <b>Speed:</b> %s/s' % (
            self.sizeof_fmt(arrived), self.sizeof_fmt(total), percent, self.sizeof_fmt(speed))
        )

        if self.d.dwnld.suspended:
            self.suspended = False
            self.running = False
            self.initDownloader()


class PathPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, default='', button_title='...', select_dir=True):
        QWidget.__init__(self)

        self.select_dir = select_dir

        self.path_input = QLineEdit(default)
        self.browse_button = QPushButton(button_title)

        self.browse_button.clicked.connect(self.browse)

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.path_input)
        self.layout().addWidget(self.browse_button)

        self.layout().setMargin(0)

    def browse(self):
        if self.select_dir:
            path = QFileDialog.getExistingDirectory(self, u'Choose folder', '')
        else:
            path = QFileDialog.getSaveFileName(self, u'Save as', '')
        if path:
            self.setPath(path)

    def setPath(self, path):
        if (self.select_dir and os.path.isdir(path)) or not self.select_dir:
            self.path_input.setText(path)
        else:
            QMessageBox.warning(self, u'Error', u'Incorrect path')
        self.updated.emit()

    @pyqtProperty(str)
    def getPath(self):
        return str(self.path_input.text())


class DM(QWidget):
    def __init__(self, src=''):
        QWidget.__init__(self)
        self.setLayout(QVBoxLayout())

        self.toolbar = QToolBar()

        self.ad = QToolButton()
        self.ad.setIcon(QIcon('config/icons/add.png'))
        self.ad.clicked.connect(self.addDownload)
        self.toolbar.addWidget(self.ad)
        self.ta = QPushButton('Toggle all')
        self.ta.clicked.connect(self.toggle_all)
        self.toolbar.addWidget(self.ta)

        # self.layout().addWidget(self.toolbar)
        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setContentsMargins(0, 0, 0, 0)

        self.items = []

        self.dialog = QDialog()
        self.dialog.setLayout(QFormLayout())
        self.dialog.url = QLineEdit()
        self.dialog.url.setPlaceholderText('http://')
        self.dialog.dest = PathPanel(default=src)
        self.dialog.layout().addRow('URL', self.dialog.url)
        self.dialog.layout().addRow('Save to', self.dialog.dest)

        self.dialog.ab = QPushButton('Add')
        self.dialog.ab.clicked.connect(lambda: self.add(self.dialog.url.text(), self.dialog.dest.getPath, False))
        self.dialog.c = QPushButton('Cancel')
        self.dialog.c.clicked.connect(self.dialog.close)

        self.dialog.controls = QWidget()
        self.dialog.controls.setLayout(QHBoxLayout())
        self.dialog.controls.layout().addWidget(self.dialog.ab)
        self.dialog.controls.layout().addWidget(self.dialog.c)

        self.dialog.layout().addRow('', self.dialog.controls)
        self.dialog.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.dialog.resize(500, 120)

        self.urls = {}

        with open(temp_folder + 'suspended.list') as f:
            _urls = f.read()
            if _urls:
                for l in _urls.split('\n'):
                    if l:
                        s, d = l.split(' ')
                        self.add(s, d, False)

    def removeDownload(self, item):
        del self.urls[item]
        self.saveUrls()

    def saveUrls(self):
        _urls = ''
        with open(temp_folder + 'suspended.list', 'w') as f:
            for p in self.urls.values():
                _urls += '%s %s\n' % p
            f.write(_urls)

    def add(self, src, dest, autostart=True):
        item = DMItem(str(src), str(dest), not autostart)
        item.removed.connect(self.removeDownload)
        self.items.append(item)
        self.layout().addWidget(item)

        self.dialog.close()
        self.urls[item] = (src, dest)

        self.saveUrls()

        if autostart:
            item.start()
        else:
            item.toggle.setIcon(QIcon('config/icons/start.png'))
            item.start()

        return item

    def toggle_all(self):
        for item in self.items:
            item.toggleDownloading()

    def addDownload(self):
        self.dialog.open()


def main():
    qtapp = QApplication(sys.argv)
    import os

    win = DM(os.path.abspath('.'))
    win.layout().addWidget(win.toolbar)
    win.show()

    url = "http://download.thinkbroadband.com/50MB.zip"

    qtapp.exec_()

    for item in win.items:
        if item.done:
            del win.urls[item]
            win.saveUrls()


if __name__ == '__main__':
    main()