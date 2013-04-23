#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import re
from time import sleep
from PyQt4.QtWebKit import QWebView

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.0'

from utils.esm_reader import ESMFile, CryptedESMFile
from utils.async import background_job, async

import logging
from PyQt4.QtGui import QWidget, QVBoxLayout, QMainWindow, QIcon, QHBoxLayout, QStatusBar, QSizePolicy, QLabel, QApplication, QPushButton, QPixmap, QFileDialog, QMessageBox, QToolBar, QDockWidget, QStackedWidget, QAction, QToolButton, QTextBrowser, QProgressBar
from PyQt4.QtCore import Qt, pyqtSignal, QSize, QThread, QUrl

from utils.checker import *
from installer import Installer, Component
from ui.hub import AsyncItem, HubItem


def showBrowserWindow(parent, url, handler=None, encoded=False):
    win = QMainWindow()
    browser = QWebView()
    win.setCentralWidget(browser)
    win.browser = browser
    if encoded:
        url = QUrl.fromEncoded(url)
    else:
        url = QUrl(url)

    if handler is not None:
        browser.titleChanged.connect(handler)
        browser.urlChanged.connect(handler)

    browser.load(url)
    browser.show()
    win.show()
    parent.browser = win
    return win


class GameInfoPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, game, force_browse=False):
        logging.info('Init %s info panel' % game)
        self.game = game
        self.is_steam = check_steam(self.game)
        self.path = get_path(self.game, self.is_steam)

        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())

        self.layout().setAlignment(Qt.AlignTop)

        self.icon = QLabel()
        self.icon.setPixmap(QPixmap(icons_folder + '%s.png' % self.game).scaledToHeight(80, Qt.SmoothTransformation))

        self.browse = QPushButton('Change')
        self.browse.clicked.connect(self.changePath)

        self.layout().addWidget(self.icon)

        self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path)
        self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

        self.exe_info_label = QLabel(self.exe_info)
        self.folder_info_label = QLabel(self.folder_info)
        self.browse.setVisible(False)

        info_panel = QWidget()
        info_panel.setLayout(QVBoxLayout())
        info_panel.layout().addWidget(QLabel('<h3>%s</h3>' % game))
        info_panel.setContentsMargins(0, 0, 0, 0)
        self.led = QLabel()
        self.led.setPixmap(QPixmap(icons_folder + 'emblems/gray.png'))
        if self.exe_valid:
            self.led.setPixmap(QPixmap(icons_folder + 'emblems/green.png'))
        if not self.folder_valid:
            self.led.setPixmap(QPixmap(icons_folder + 'emblems/orange.png'))

        sub_panel = QWidget()
        sub_panel.setLayout(QHBoxLayout())
        sub_panel.layout().addWidget(self.led)
        sub_panel.layout().addWidget(self.exe_info_label)

        sub_panel.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)

        info_panel.layout().addWidget(sub_panel)

        self.layout().addWidget(info_panel)

        self.layout().addWidget(self.browse)
        # panel.layout().addWidget(self.folder_info_label, 1, 0)

        if not os.path.isdir(self.path):
            self.folder_info_label.setVisible(False)
            self.browse.setVisible(True)

        if not self.exe_valid or not self.folder_valid or force_browse:
            self.browse.setVisible(True)

        if self.exe_valid and not self.folder_valid:
            self.exe_info_label.setText(self.folder_info)

        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setMargin(0)
        self.layout().setMargin(0)

    def is_valid(self):
        return self.exe_valid and self.folder_valid

    def changePath(self):
        path = QFileDialog.getExistingDirectory(self, u'%s folder' % self.game, '')
        if path:
            self.is_steam = False
            self.path = unicode(path)
            self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path)
            self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

            self.exe_info_label.setText(self.exe_info)
            self.folder_info_label.setText(self.folder_info)

            self.updated.emit()

    def get_exe_info(self, game, path):
        info = check_valid_exe(game, path)
        if info[0]:
            return 'Version: <span style="color: green"><b>%s</b></span>' % info[0][1], True
        else:
            return '<span style="color: red"><b>%s</b></span>' % info[1], False

    def get_folder_info(self, game, path):
        info = check_valid_folder(game, path)
        if info[0]:
            return '<span style="color: green"><b>Installation valid</b></span>', True
        else:
            return '<span style="color: red"><b>%s</b></span>' % info[1], False


class ComponentItem(HubItem):
    def __init__(self, component, version):
        self.component = component
        self.version = version
        HubItem.__init__(self)
        self.setLayout(QHBoxLayout())
        self.icon = QLabel()
        icon = QPixmap(icons_folder + 'components/%s.png' % self.component.type).scaledToWidth(48)
        self.icon.setPixmap(icon)
        self.layout().addWidget(self.icon)
        self.title = QLabel('<h3>%s</h3>' % self.component.name)
        self.desc = QLabel(self.component.description)
        sub_panel = QWidget()
        sub_panel.setLayout(QVBoxLayout())
        sub_panel.layout().addWidget(self.title)
        sub_panel.layout().addWidget(self.desc)
        self.layout().addWidget(sub_panel)

        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setMargin(0)
        sub_panel.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.layout().setMargin(0)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.layout().addWidget(spacer)

        self.dl = QPushButton(u'Download')
        self.dl.clicked.connect(self.beforeDownload)
        self.install = QPushButton(u'Install')
        self.install.clicked.connect(self.startInstall)

        self.progressBar = QProgressBar()
        self.progressBar.setMaximum(0)
        self.layout().insertWidget(3, self.progressBar)
        self.progressBar.hide()

        fn = os.path.join(self.component.src_folder, 'status.yml')
        if not os.path.exists(self.component.src_folder):
            os.mkdir(self.component.src_folder)
            with open(fn, 'w') as f:
                f.write('installed:')
        cm.addConfig(self.version, fn)

        if not self.component.available:
            self.layout().addWidget(self.dl)
        else:
            if self.component.name in cm[self.version].installed and cm[self.version].installed[self.component.name]:
                pass
            else:
                self.layout().addWidget(self.install)

    def beforeDownload(self):
        # print(self.component.src_folder, os.path.exists(self.component.src_folder))
        cm[self.version]._dict['started'] = {self.component.name: True}

        self.startDownload()

    def startInstall(self):
        self.install.setEnabled(False)
        self.progressBar.setMaximum(0)
        self.progressBar.show()
        async(
            lambda: self.component.install(self.game.install_path, print),
            self.afterInstall,
            print
        )

        self.install.hide()

    def afterInstall(self):
        cm[self.version]._dict['installed'] = {self.component.name: True}

        cm[self.version].save(open(os.path.join(self.component.src_folder, 'status.yml'), 'w'))
        cm.reloadConfig(self.version)
        self.desc.setText(u'<span style="color: green">Successfully installed.</span>')
        self.progressBar.hide()

    def startDownload(self):
        self.downloader = Downloader(self.component.url, os.path.join(self.component.src_folder, self.component.name))

        self.downloader.progress.connect(self.progress)
        self.downloader.error.connect(print)
        self.downloader.flush.connect(self.flush)
        self.downloader.finished.connect(self.finish)
        self.dl.hide()
        self.progressBar.show()
        self.progressBar.setMaximum(100)
        self.downloader.start()

    def flush(self):
        # self.toggle.setEnabled(False)
        self.progressBar.setMaximum(0)
        self.desc.setText('<b>Dumping to disc</b>')

    def finish(self):
        cm[self.version]._dict['started'] = {self.component.name: False}
        cm[self.version].save(open(os.path.join(self.component.src_folder, 'status.yml'), 'w'))
        cm.reloadConfig(self.version)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(100)
        self.progressBar.hide()
        self.desc.setText(self.component.description)
        self.layout().addWidget(self.install)

    def sizeof_fmt(self, num):
        for x in ['bytes', 'KB', 'MB', 'GB']:
            if 1024.0 > num > -1024.0:
                return "%3.1f%s" % (num, x)
            num /= 1024.0
        return "%3.1f%s" % (num, 'TB')

    def progress(self, speed, arrived, percent, total):
        self.progressBar.setValue(percent)

        self.desc.setText('<b>Done:</b> %s/%s [%s%%]. <b>Speed:</b> %s/s' % (
            self.sizeof_fmt(arrived), self.sizeof_fmt(total), percent, self.sizeof_fmt(speed))
        )


class NewsItem(HubItem):
    def __init__(self, news):
        self.news = news
        HubItem.__init__(self)
        self.setLayout(QHBoxLayout())
        self.icon = QLabel()
        icon = QPixmap(icons_folder + 'components/news.png').scaledToWidth(48)
        self.icon.setPixmap(icon)
        self.layout().addWidget(self.icon)
        self.title = QLabel('<h3>%s</h3>' % self.news.title)
        self.desc = QLabel(self.news.description)
        sub_panel = QWidget()
        sub_panel.setLayout(QVBoxLayout())
        sub_panel.layout().addWidget(self.title)
        sub_panel.layout().addWidget(self.desc)
        self.layout().addWidget(sub_panel)

        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setMargin(0)
        self.layout().setMargin(0)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.layout().addWidget(spacer)

        view = QPushButton(u'View')
        self.layout().addWidget(view)
        view.clicked.connect(lambda: showBrowserWindow(self, self.news.url, None))


class UpdateItem(AsyncItem):
    def __init__(self, game):
        AsyncItem.__init__(self)
        self.game = game
        self.name = game.name
        self.led = QLabel()
        self.led.setPixmap(QPixmap(icons_folder + 'emblems/gray.png'))
        self.title = QLabel('<h3>%s</h3>' % self.name)
        self.info = QLabel('Checking updates')
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.led)
        sub_panel = QWidget()
        sub_panel.setLayout(QVBoxLayout())
        sub_panel.layout().addWidget(self.title)
        sub_panel.layout().addWidget(self.info)
        sub_panel.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.layout().addWidget(sub_panel)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.layout().addWidget(spacer)

        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setMargin(0)
        self.layout().setMargin(0)

        self.error.connect(self.onError)

        self.have_update = False

    def job(self):
        logging.info('Checking %s updates' % self.name)
        if "%s_remote" not in cm.configs:
            self.getRemoteConfig()
        remote = cm["%s_remote" % self.name]
        local = cm[self.name]

        if local._dict != remote._dict:
            cm.configs[self.name] = cm["%s_remote" % self.name]
            return True
        else:
            return False

    def onError(self, e):
        self.info.setText('<span style="color: red"><b>Error:</b> %s</span>' % e)

    def onReady(self, ret):

        if not ret:

            if self.getVersion():
                self.led.setPixmap(QPixmap(icons_folder + 'emblems/green.png'))
                self.info.setText('You have latest version')
                self.dont_show = True
            else:
                self.led.setPixmap(QPixmap(icons_folder + 'emblems/orange.png'))
                self.info.setText('You can install release version')
        else:
            self.led.setPixmap(QPixmap(icons_folder + 'emblems/orange.png'))
            self.info.setText('Updates available')
            self.have_update = True

        self.getUpdate()

        if 'news' in cm[self.name]._dict:
            for n in cm[self.name].news.values():
                self.hub.addItem(NewsItem(n))

    def getUpdate(self):
        cm['%s_remote' % self.name].save(open(os.path.join(config_folder, '%s.yml' % self.name), 'w'))
        cm.addConfig(self.name, os.path.join(config_folder, '%s.yml' % self.name))

        try:
            self.showComponents()
        except Exception as e:
            logging.error(e)
            self.info.setText('<span style="color: red"><b>Error:</b> %s</span>' % 'Wrong format of %s.yml' % self.name)

        # self.Update()

    def getVersion(self):
        return self.game.version

    def showComponents(self):
        versions = sorted(cm[self.name].versions)
        current_verson = self.getVersion()
        if current_verson:
            next_version = versions[versions.index(current_verson) + 1]
            self.info.setText('Next version: %s' % next_version)
        else:
            next_version = versions[0]

        _components = cm[self.name].versions[next_version].components
        components = []
        for c in _components:
            components.append(
                Component.create(
                    c,
                    os.path.join(data_folder, next_version),
                    _components[c]
                )
            )
        self.components = components
        for i, component in enumerate(components):
            item = ComponentItem(component, version=next_version)
            item.game = self.game
            item.pos = self.pos + i
            self.hub.addItem(item)


    def Update(self):
        self.have_update = False
        # self.led.setPixmap(QPixmap(icons_folder + 'emblems/green.png'))
        # self.info.setText('You have latest version')
        # self.gu.hide()

    def getRemoteConfig(self):
        config_url = cm['config']['%s_url' % self.name.lower()]
        if config_url.startswith('https://api.github.com/gists/'):
            id = config_url.split('/')[-1]
            Gists.fetchGistInfo(id)
            url = Gists.getDirectLink(id, '%s.yml' % self.name)
        else:
            url = config_url
        cm.addRemoteConfig("%s_remote" % self.name, url)


class ModInfoPanel(QWidget):
    updated = pyqtSignal()
    get_updates = pyqtSignal(object)
    spawn_item = pyqtSignal(object)

    def checkUpdates(self):
        self.spawn_item.emit(UpdateItem(self))

    def __init__(self, name, parent_game, child_game):
        logging.info('Init %s info panel' % name)
        self.name = name
        self.child = child_game
        self.parent = parent_game

        self.parent.updated.connect(self.updateInfo)
        self.child.updated.connect(self.updateInfo)

        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())

        self.install_path = self.parent.path
        self.distrib_path = os.path.abspath(u'Data Files')
        self.install = QPushButton(u'Install')
        self.uninstall = QPushButton(u'Uninstall')

        self.installer = Installer(self, cm[self.name], self.install)
        self.uninstall.clicked.connect(self.installer.uninstall)

        self.installer.wizard.finished.connect(self.updateInfo)
        self.installer.unwizard.finished.connect(self.updateInfo)

        self.icon_name = self.name
        self.icon = QLabel()
        self.icon.setPixmap(
            QPixmap(icons_folder + '%s.png' % self.icon_name).scaledToHeight(64, Qt.SmoothTransformation))

        self.layout().addWidget(self.icon)

        self.info_str, self.is_valid = check_mod(self.name, self.parent.path)

        self.esm = None
        self.new_esm = None

        self.info = QLabel(self.info_str)

        info_panel = QWidget()
        info_panel.setLayout(QVBoxLayout())
        info_panel.layout().addWidget(QLabel('<h3>%s</h3>' % self.name))
        info_panel.setContentsMargins(0, 0, 0, 0)
        self.led = QLabel()
        self.led.setPixmap(QPixmap(icons_folder + 'emblems/gray.png'))
        if self.is_valid:
            self.led.setPixmap(QPixmap(icons_folder + 'emblems/green.png'))

        sub_panel = QWidget()
        sub_panel.setLayout(QHBoxLayout())
        sub_panel.setContentsMargins(0, 0, 0, 0)
        sub_panel.layout().addWidget(self.led)
        sub_panel.layout().addWidget(self.info)

        sub_panel.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)

        info_panel.layout().addWidget(sub_panel)

        self.layout().addWidget(info_panel)

        self.setVersion()

        if not DEBUG:
            self.install.setEnabled(self.child.is_valid())

        buttons = QWidget()
        buttons.setLayout(QHBoxLayout())
        buttons.layout().addWidget(self.install)
        buttons.layout().addWidget(self.uninstall)
        info_panel.layout().addWidget(buttons)
        self.uninstall.setVisible(False)

        self.updateInstallButton()
        self.updated.emit()

        self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sub_panel.layout().setMargin(0)
        self.layout().setMargin(0)

        # if self.is_valid:
        # self.checkUpdates()

    def setVersion(self):
        if self.is_valid:
            self.esm = ESMFile(os.path.join(self.install_path, u'Data', u'%s.esm' % self.name))
            if re.match('\d\.\d\.\d', self.esm.esm_info['description']):
                self.info_str = '<b>Installed:</b> v%s by %s' % (
                    self.esm.esm_info['description'], self.esm.esm_info['developer'])
                self.version = self.esm.esm_info['description']
            else:
                self.info_str = '<b>Installed:</b> Unknown version'
                self.version = False
            if os.path.isfile(os.path.join(self.distrib_path, '%s.cmf' % self.name)):
                from secret import key

                self.new_esm = CryptedESMFile(os.path.join(self.distrib_path, u'%s.cmf' % self.name), key)
                if self.new_esm.esm_info['description'] != self.esm.esm_info['description']:
                    self.led.setPixmap(QPixmap(icons_folder + 'emblems/orange.png'))
                    self.info_str += '<br><b>Available:</b> v%s by %s' % (
                        self.new_esm.esm_info['description'],
                        self.new_esm.esm_info['developer']
                    )
                else:
                    self.info_str += '<br>It is latest version.'

            self.info.setText(self.info_str)
        else:
            self.version = False

    def updateInfo(self):
        self.info_str, self.is_valid = check_mod(self.name, self.parent.path)
        self.info.setText(self.info_str)
        self.install_path = self.parent.path
        self.updateInstallButton()
        self.setVersion()
        self.updated.emit()

    def updateInstallButton(self):
        try:
            self.install.clicked.disconnect(self.installer.install)
        except TypeError:
            pass
        if not self.is_valid:
            self.install.setText('Install')
            self.install.clicked.connect(self.installer.install)
            self.uninstall.setVisible(False)
        else:
            self.install.setText('Update')
            self.install.clicked.connect(self.installer.install)
            self.uninstall.setVisible(True)

        if self.child.is_valid():
            self.install.setEnabled(True)
        else:
            self.install.setEnabled(False)


from Launcher import icons_folder, DEBUG, cm, config_folder, data_folder, Gists
from utils.oauth import LimitExceeded
from dm import Downloader