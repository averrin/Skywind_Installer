#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import functools
import re
import shutil
import sys
import logging
from PyQt4.QtGui import QWidget, QVBoxLayout, QMainWindow, QIcon, QHBoxLayout, QStatusBar, QSizePolicy, QLabel, QApplication, QPushButton, QPixmap, QFileDialog, QMessageBox, QToolBar, QDockWidget, QStackedWidget, QAction, QToolButton, QTextBrowser
from PyQt4.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt4.QtWebKit import QWebView
from lxml import etree

import os
from bug_report import DebugManager
from config_manager import ConfigManager
from dep_manager import DepManager, Internal, External
from dm import DM

#TODO: debug mode into all processes

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.1.0'

DEBUG = '-debug' in sys.argv
config_folder = 'config'
icons_folder = os.path.join(config_folder, 'icons') + os.sep
contrib_folder = os.path.join(config_folder, 'contrib') + os.sep
temp_folder = os.path.join(config_folder, 'temp') + os.sep
frozen = getattr(sys, "frozen") if hasattr(sys, 'frozen') else False
bug_thread = 'http://morroblivion.com/forums/skyrim/skywind-development/4098'
log_filename = 'transtes.log'

if DEBUG:
    debug = DebugManager('TransTES', __version__)

dm = DepManager()
cm = ConfigManager(ignore_optional=True)

cm.addConfig("Skywind", os.path.join(config_folder, 'Skywind.yml'), optional=True)
cm.addConfig("Skyblivion", os.path.join(config_folder, 'Skyblivion.yml'), optional=True)

dm.addDeps([
    Internal(config_folder, is_folder=True),
    Internal(icons_folder, is_folder=True),
    Internal(contrib_folder, is_folder=True),
    Internal(temp_folder, is_folder=True),
    External('unrar.exe', os.path.expandvars('%SYSTEMROOT%\\unrar.exe'), contrib_folder=contrib_folder),
    External('7z.exe', os.path.expandvars('%SYSTEMROOT%\\7z.exe'), contrib_folder=contrib_folder),
    External('7z.dll', os.path.expandvars('%SYSTEMROOT%\\7z.dll'), contrib_folder=contrib_folder),
    cm
])

if not dm.ok and dm.critical:
    qtapp = QApplication(sys.argv)

    dm_info = QTextBrowser()
    dm_info.append(u'<h3>Installer seems corrupted:</h3>')
    for d in dm.critical:
        dm_info.append(d.info)
    dm_info.show()
    qtapp.exec_()
    sys.exit(0)

from checker import *
from installer import Installer, Encrypted
from esm_reader import ESMFile, CryptedESMFile
from requests import get


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

        self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path, self.is_steam)
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
            self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path, self.is_steam)
            self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

            self.exe_info_label.setText(self.exe_info)
            self.folder_info_label.setText(self.folder_info)

            self.updated.emit()

    def get_exe_info(self, game, path, is_steam=False):
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


class ModInfoPanel(QWidget):
    updated = pyqtSignal()
    gists = {'Skywind': '5338904', 'Skyblivion': '5338932'}

    def getRemoteConfig(self):
        api_url = 'https://api.github.com/gists/'
        url = get(api_url + self.gists[self.name]).json()[u'files'][u'%s.yml' % self.name][u'raw_url']
        cm.addRemoteConfig("%s_remote" % self.name, url)

    def checkUpdates(self):
        logging.info('Checking %s updates' % self.name)
        if "%s_remote" not in cm.configs:
            self.getRemoteConfig()
        remote = cm["%s_remote" % self.name]
        local = cm[self.name]

        if local._dict != remote._dict:
            print('Seems like update for %s' % self.name)
            cm.configs[self.name] = cm["%s_remote" % self.name]
            self.schema = cm[self.name]
        else:
            print('%s is latest version' % self.name)


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

        self.schema = cm[self.name]

        self.installer = Installer(self, self.schema, self.install)
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
            # if not self.folder_valid:
        #     self.led.setPixmap(QPixmap(icons_folder + 'emblems/orange.png'))

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

        if self.is_valid:
            self.checkUpdates()

    def setVersion(self):
        if self.is_valid:
            self.esm = ESMFile(os.path.join(self.install_path, u'Data', u'%s.esm' % self.name))
            if re.match('\d\.\d\.\d', self.esm.esm_info['description']):
                self.info_str = '<b>Installed:</b> v%s by %s' % (
                    self.esm.esm_info['description'], self.esm.esm_info['developer'])
            else:
                self.info_str = '<b>Installed:</b> Unknown version'
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

    def updateInfo(self, *args):
        self.info_str, self.is_valid = check_mod(self.name, self.parent.path)
        # self.setVersion()
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


class Browser(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.setLayout(QVBoxLayout())

        self.view = QWebView()
        self.layout().addWidget(self.view)

        self.toolbar = QToolBar()

        self.config = False

        logging.info('Get readme')

        if os.path.isfile('config/Skywind.yml'):
            self.view.setHtml(self.getReadme('Skywind'))
            button = QToolButton()
            button.setIcon(QIcon(icons_folder + 'Skywind_icon.png'))
            button.clicked.connect(lambda: self.view.setHtml(self.getReadme('Skywind')))
            self.toolbar.addWidget(button)

        if os.path.isfile('config/Skyblivion.yml'):
            if not self.config:
                self.view.setHtml(self.getReadme('Skyblivion'))
            button = QToolButton()
            button.setIcon(QIcon(icons_folder + 'Skyblivion_icon.png'))
            button.clicked.connect(lambda: self.view.setHtml(self.getReadme('Skyblivion')))
            self.toolbar.addWidget(button)

        logging.info('Done with readme')

    def getReadme(self, game):
        self.config = cm[game]
        page = get(self.config.readme.url)
        if page.status_code == 200:
            tree = etree.HTML(page.content)
            content = tree.xpath(self.config.readme.xpath)[0]

            content = etree.tostring(content, pretty_print=True, method="html")

            css = """
            <head>
                <link type="text/css" rel="stylesheet" media="all"
                    href="http://morroblivion.com/sites/all/themes/morroblivion-%s/css/style.css?x" />
                <style>
                    img {
                        margin: 0px auto;
                        margin-bottom: 10px;
                        display: none; /*while qt plugin missed*/
                    }
                    .content {width: 512px; margin: 0 auto; background-color: %s; padding: 10px}
                </style>
            </head>
            """ % (self.config.readme.style, '#323232' if self.config.readme.style == 'dark' else '#eee')

            content = '%s<body>%s</body>' % (css, content)

            return content
        return 'Cant load page.'


class SBAction(QAction):
    def __init__(self, sideBarDock, *args, **kwargs):
        self.sideBarDock = sideBarDock
        sideBarDock.hide()
        QAction.__init__(self, *args, **kwargs)

    def showWidget(self):
        if self.sideBarDock.isHidden():
            if hasattr(self.widget, 'onShow'):
                self.widget.onShow()
            self.sideBarDock.show()
        elif self.sideBarDock.stack.currentWidget() == self.widget:
            self.sideBarDock.hide()
            if hasattr(self.widget, 'onHide'):
                self.widget.onHide()
        if hasattr(self, 'widgetWidth'):
            self.sideBarDock.setFixedWidth(self.widgetWidth)
        else:
            self.sideBarDock.setFixedWidth(500)

        self.sideBarDock.stack.setCurrentWidget(self.widget)
        self.sideBarDock.setTitleBarWidget(self.titleWidget)
        self.widget.setFocus()

    def forceShowWidget(self):
        if hasattr(self.widget, 'onShow'):
            self.widget.onShow()
        self.sideBarDock.show()
        self.sideBarDock.stack.setCurrentWidget(self.widget)
        self.widget.setFocus()


class SideBar(QToolBar):
    def __init__(self, parent):
        self.parent = parent
        QToolBar.__init__(self)
        self.setObjectName('sideBar')
        self.parent.addToolBar(Qt.LeftToolBarArea, self)

        self.setIconSize(
            QSize(48, 48))
        self.setMovable(False)

        self.dock = QDockWidget()
        self.dock.setObjectName('sideBarDock')
        self.dock.stack = QStackedWidget()
        self.stack = self.dock.stack
        self.dock.setWidget(self.stack)
        self.parent.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        self.dock.hide()


class UI(QMainWindow):
    def __init__(self):
        logging.info('Start main UI init')
        QMainWindow.__init__(self)
        self.setWindowTitle(u"TransTES Hub" if not DEBUG else 'TransTES [DEBUG]')
        self.setWindowIcon(QIcon('icons/app.png'))

        panel = QWidget()
        panel.setLayout(QHBoxLayout())
        self.setCentralWidget(panel)

        games_panel = QWidget()
        games_panel.setLayout(QVBoxLayout())
        # self.setCentralWidget(games_panel)

        games_panel.resize(500, 100)

        is_skywind = "Skywind" in cm.configs
        is_skyblivion = "Skyblivion" in cm.configs

        self.Skyrim = GameInfoPanel('Skyrim', force_browse=True)

        if is_skywind:
            self.Morrowind = GameInfoPanel('Morrowind')
            games_panel.layout().addWidget(self.Morrowind)
            self.Skywind = ModInfoPanel('Skywind', self.Skyrim, self.Morrowind)

        if is_skyblivion:
            self.Oblivion = GameInfoPanel('Oblivion')
            games_panel.layout().addWidget(self.Oblivion)
            self.Skyblivion = ModInfoPanel('Skyblivion', self.Skyrim, self.Oblivion)

        logging.info('Done games init')
        logging.info('Start ui building')

        games_panel.layout().addWidget(self.Skyrim)

        games_panel.layout().addWidget(QLabel('<hr>'))
        if is_skywind:
            games_panel.layout().addWidget(self.Skywind)

        if is_skyblivion:
            games_panel.layout().addWidget(self.Skyblivion)

        buttons = QWidget()
        buttons.setLayout(QHBoxLayout())

        games_panel.layout().setAlignment(Qt.AlignTop)

        panel.layout().addWidget(games_panel)

        self.statusBar = QStatusBar(self)
        self.statusBar.addPermanentWidget(QWidget().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.setStatusBar(self.statusBar)
        self.statusBar.addPermanentWidget(
            QLabel(u'by <b>Averrin</b> for <b>Skywind Project</b>. Version: %s  ' % __version__)
        )
        self.statusBar.setSizeGripEnabled(False)

        self.sideBar = SideBar(self)

        self.sizeHint = QSize(500, 100)

        self.dm = DM(os.path.abspath(u'Data Files'))
        # self.dm.onShow = lambda: self.setMaximumWidth(games_panel.width())
        self.readme = Browser()
        # self.readme.onShow = lambda: self.setMaximumWidth(games_panel.width())
        readme = self.createSBAction(QIcon(icons_folder + 'readme.png'), 'Readme', self.readme, toolbar=True,
                                     widgetWidth=700, titleWidget=self.readme.toolbar)
        self.createSBAction(QIcon(icons_folder + 'dm.png'),
                            'Downloads', self.dm, toolbar=True,
                            titleWidget=self.dm.toolbar)

        if DEBUG:
            report = QTextBrowser()
            report.resize(800, 600)
            prefix = u'Please copy this report text and post it into this thread: <a href="%s">Installer bugs</a><br><br>' % bug_thread
            from collections import OrderedDict

            extra = OrderedDict({
                'CWD': os.path.abspath('.'),
                'SKYRIM PATH': self.Skyrim.path
            })
            if is_skywind:
                extra['MORROWIND_PATH'] = self.Morrowind.path
                extra['MORROWIND_IV'] = self.Morrowind.is_valid()
                extra['MORROWIND_EV'] = self.Morrowind.exe_valid
                extra['MORROWIND_FV'] = self.Morrowind.folder_valid
                extra['SKYWIND_DISTRIBPATH'] = self.Skywind.distrib_path
                extra['SKYWIND_INSTALLPATH'] = self.Skywind.install_path

            if is_skyblivion:
                extra['OBLIVION_PATH'] = self.Oblivion.path
                extra['OBLIVION_IV'] = self.Oblivion.is_valid()
                extra['OBLIVION_EV'] = self.Oblivion.exe_valid
                extra['OBLIVION_FV'] = self.Oblivion.folder_valid
                extra['SKYBLIVION_DISTRIBPATH'] = self.Skyblivion.distrib_path
                extra['SKYBLIVION_INSTALLPATH'] = self.Skyblivion.install_path

            report.onShow = lambda: report.setHtml(debug.getReport(prefix=prefix, extra=extra))

            self.createSBAction(QIcon(icons_folder + 'bug.png'),
                                'Bug Report', report, toolbar=True)
        else:
            readme.showWidget()

        logging.info('Done ui building')

    def createSBAction(self, icon, name, widget, keyseq='', toolbar=False, titleWidget=None, widgetWidth=None):
        action = SBAction(self.sideBar.dock, icon, name, self)
        action.widget = widget
        if titleWidget is not None:
            action.titleWidget = titleWidget
        else:
            action.titleWidget = QToolBar()

        if widgetWidth is not None:
            action.widgetWidth = widgetWidth

        self.sideBar.stack.addWidget(widget)
        action.triggered.connect(functools.partial(action.showWidget))
        if keyseq:
            action.setShortcut(keyseq)
        if toolbar:
            self.sideBar.addAction(action)
        self.addAction(action)
        return action


def main():
    win = UI()
    win.show()

    qtapp.exec_()


if __name__ == '__main__':
    qtapp = QApplication(sys.argv)
    if len(sys.argv) > 1:
        if sys.argv[1] == '--hash' and len(sys.argv) > 2:
            fp = sys.argv[2]
            with open(fp, 'rb') as f:
                hash = hashlib.sha256(f.read()).hexdigest()
            msgBox = QTextBrowser()
            msgBox.setText(u'Hash sum calculated\nhash: %s' % hash)
            msgBox.resize(500, 100)
            msgBox.show()
            qtapp.exec_()
            sys.exit(0)
        elif sys.argv[1] == '--encrypt' and len(sys.argv) > 3:
            e = Encrypted('new', '', {})
            from secret import key

            e.encrypt(key, sys.argv[2], sys.argv[3])
            with open(sys.argv[2], 'rb') as f:
                original_hash = hashlib.sha256(f.read()).hexdigest()
            with open(sys.argv[2], 'rb') as f:
                hash = hashlib.sha256(f.read()).hexdigest()

            msgBox = QTextBrowser()
            msgBox.setText(u'File encrypted. Hash sums:\nhash: %s\noriginal_hash: %s' % (hash, original_hash))
            msgBox.resize(500, 100)
            msgBox.show()
            qtapp.exec_()

            sys.exit(0)
    main()