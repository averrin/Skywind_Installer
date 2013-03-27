#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import logging
from PyQt4.QtGui import QWidget, QVBoxLayout, QMainWindow, QIcon, QHBoxLayout, QStatusBar, QSizePolicy, QLabel, QApplication, QPushButton, QPixmap, QFileDialog
from PyQt4.QtCore import Qt, pyqtSignal
from PyQt4.QtWebKit import QWebView
from lxml import etree
from requests import *

logging.basicConfig(format='[%(asctime)s] %(levelname)s:\t\t%(message)s', filename='skywind.log',
                    level=logging.DEBUG,
                    datefmt='%d.%m %H:%M:%S')

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.5'

from checker import *
from installer import Installer
from esm_reader import ESMFile, CryptedESMFile

DEBUG = False

# if len(sys.argv) > 1 and sys.argv[1] == '--debug':      #TODO: make it right
#     DEBUG = True

if hasattr(sys, "frozen") and getattr(sys, "frozen") == "windows_exe":
    print('Compiled version')
    # from resources import ResourceFile, FindResource
    # unrar = FindResource('UNRAR', 1)
else:
    print('From sources')


class GameInfoPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, game, force_browse=False):
        self.game = game
        self.is_steam = check_steam(self.game)
        self.path = get_path(self.game, self.is_steam)

        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())

        self.layout().setAlignment(Qt.AlignTop)

        self.icon = QLabel()
        self.icon.setPixmap(QPixmap('icons/%s.png' % self.game).scaledToWidth(64, Qt.SmoothTransformation))

        self.browse = QPushButton('Change')
        self.browse.clicked.connect(self.changePath)

        self.layout().addWidget(self.icon)

        self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path, self.is_steam)
        self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

        self.exe_info_label = QLabel(self.exe_info)
        self.folder_info_label = QLabel(self.folder_info)
        self.browse.setVisible(False)

        self.layout().addWidget(self.exe_info_label)
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

    def is_valid(self):
        return self.exe_valid and self.folder_valid

    def changePath(self):
        path = QFileDialog.getExistingDirectory(self, u'%s folder' % self.game, '')
        if path:
            self.path = str(path)
            self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path, self.is_steam)
            self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

            self.exe_info_label.setText(self.exe_info)
            self.folder_info_label.setText(self.folder_info)

            self.updated.emit()

    def get_exe_info(self, game, path, is_steam=False):
        info = check_valid_exe(game, path)
        if info[0]:
            return '%s version: <span style="color: green"><b>%s (%s)</b></span>' % (
                game, info[0][1], 'Steam' if is_steam else 'Retail'), True
        else:
            return '<span style="color: red"><b>%s</b></span>' % info[1], False

    def get_folder_info(self, game, path):
        info = check_valid_folder(game, path)
        if info[0]:
            return '<span style="color: green"><b>Installation valid</b></span>', True
        else:
            return '<span style="color: red"><b>%s</b></span>' % info[1], False


class SkywindPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, skyrim, morrowind):
        self.Morrowind = morrowind
        self.Skyrim = skyrim

        self.Skyrim.updated.connect(self.update)

        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())

        self.install_path = self.Skyrim.path
        self.distrib_path = os.path.abspath('.')
        self.install = QPushButton(u'Install')
        self.installer = Installer(self, self.install)

        self.installer.wizard.finished.connect(self.update)
        self.installer.unwizard.finished.connect(self.update)

        self.icon_name = 'Skywind'
        self.icon = QLabel()
        self.icon.setPixmap(QPixmap('icons/%s.png' % self.icon_name).scaledToWidth(64, Qt.SmoothTransformation))

        self.layout().addWidget(self.icon)

        self.info_str, self.is_valid = check_skywind(self.Skyrim.path)

        self.esm = None
        self.new_esm = None

        if self.is_valid:
            self.esm = ESMFile(os.path.join(self.install_path, 'Data', 'Skywind.esm'))
            self.info_str = '<b>Installed:</b> v%s by %s' % (
            self.esm.esm_info['description'], self.esm.esm_info['developer'])
            if os.path.isfile('Skywind.cmf'):
                from secret import key

                self.new_esm = CryptedESMFile(os.path.join(self.distrib_path, 'Skywind.cmf'), key)
                if self.new_esm.esm_info['description'] != self.esm.esm_info['description']:
                    self.info_str += '<br><b>Available:</b> v%s by %s' % (
                        self.new_esm.esm_info['description'],
                        self.new_esm.esm_info['developer']
                    )
                else:
                    self.info_str += '<br>It is latest version.'
                    
            self.info = QLabel(self.info_str)

        self.layout().addWidget(self.info)

        if not DEBUG:
            self.install.setEnabled(self.Morrowind.is_valid())

        self.layout().addWidget(self.install)

        self.updateInstallButton()
        self.updated.emit()

    def update(self, *args):
        self.info_str, self.is_valid = check_skywind(self.Skyrim.path)
        if self.is_valid:
            self.esm = ESMFile(os.path.join(self.install_path, 'Data', 'Skywind.esm'))
            self.info_str = '<b>Installed:</b> v0.%s by %s' % (
                self.esm.esm_info['description'][-2:], self.esm.esm_info['developer'])
            if os.path.isfile('Skywind.cmf'):
                from secret import key

                self.new_esm = CryptedESMFile(os.path.join(self.distrib_path, 'Skywind.cmf'), key)
                self.info_str += '<br><b>Available:</b> v0.%s by %s' % (
                    self.new_esm.esm_info['description'][-2:],
                    self.new_esm.esm_info['developer']
                )
        self.info.setText(self.info_str)
        self.install_path = self.Skyrim.path
        self.updateInstallButton()
        self.updated.emit()

    def updateInstallButton(self):
        try:
            self.install.clicked.disconnect(self.installer.install)
            self.install.clicked.disconnect(self.installer.uninstall)
        except TypeError:
            pass
        if not self.is_valid:
            self.install.setText('Install')
            self.install.clicked.connect(self.installer.install)
        else:
            if self.new_esm is None:
                self.install.setText('Uninstall')
                self.install.clicked.connect(self.installer.uninstall)
            else:
                self.install.setText('Update')


class Browser(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.setLayout(QVBoxLayout())

        self.view = QWebView()
        self.layout().addWidget(self.view)

        self.view.setHtml(self.getReadme())

    def getReadme(self):
        style = 'dark'
        url = 'http://morroblivion.com/forums/skyrim/skywind-mod-releases/3323'
        xpath = '//*[@id="node-3323"]/div[2]/div[2]/div'

        page = get(url)
        tree = etree.HTML(page.content)
        content = tree.xpath(xpath)[0]

        content = etree.tostring(content, pretty_print=True, method="html")

        css = """
        <head>
            <link type="text/css" rel="stylesheet" media="all"
                href="http://morroblivion.com/sites/all/themes/morroblivion-%s/css/style.css?x" />
            <style>
                img {margin: 0px auto; margin-bottom: 10px;}
                .content {width: 612px; margin: 0 auto; background-color: #323232; padding: 10px}
            </style>
        </head>
        """ % style

        content = '%s<body>%s</body>' % (css, content)

        return content


class UI(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle(u"Skywind" if not DEBUG else 'Skywind [DEBUG]')
        self.setWindowIcon(QIcon('icons/app.png'))

        panel = QWidget()
        panel.setLayout(QHBoxLayout())
        self.setCentralWidget(panel)

        games_panel = QWidget()
        games_panel.setLayout(QVBoxLayout())
        # self.setCentralWidget(games_panel)

        games_panel.resize(500, 100)

        self.Morrowind = GameInfoPanel('Morrowind')
        self.Skyrim = GameInfoPanel('Skyrim', force_browse=True)

        games_panel.layout().addWidget(self.Morrowind)
        games_panel.layout().addWidget(self.Skyrim)

        self.Skywind = SkywindPanel(self.Skyrim, self.Morrowind)
        games_panel.layout().addWidget(self.Skywind)

        buttons = QWidget()
        buttons.setLayout(QHBoxLayout())

        games_panel.layout().setAlignment(Qt.AlignTop)

        panel.layout().addWidget(Browser())
        panel.layout().addWidget(games_panel)

        self.statusBar = QStatusBar(self)
        self.statusBar.addPermanentWidget(QWidget().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.setStatusBar(self.statusBar)
        self.statusBar.addPermanentWidget(
            QLabel(u'by <b>Averrin</b> for <b>Skywind Project</b>. Version: %s  ' % __version__)
        )
        self.statusBar.setSizeGripEnabled(False)


def main():
    qtapp = QApplication(sys.argv)
    win = UI()
    win.show()

    qtapp.exec_()


if __name__ == '__main__':
    main()