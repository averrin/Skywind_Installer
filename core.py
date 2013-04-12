#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import re


__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.0'

from utils.esm_reader import ESMFile, CryptedESMFile
from requests import get
from utils.async import background_job

import logging
from PyQt4.QtGui import QWidget, QVBoxLayout, QMainWindow, QIcon, QHBoxLayout, QStatusBar, QSizePolicy, QLabel, QApplication, QPushButton, QPixmap, QFileDialog, QMessageBox, QToolBar, QDockWidget, QStackedWidget, QAction, QToolButton, QTextBrowser
from PyQt4.QtCore import Qt, pyqtSignal, QSize, QThread

from utils.checker import *
from installer import Installer


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


class ModInfoPanel(QWidget):
    updated = pyqtSignal()
    get_updates = pyqtSignal(object)

    def getRemoteConfig(self):
        config_url = cm['config']['%s_url' % self.name.lower()]
        if config_url.startswith('https://api.github.com/gists/'):
            url = get(config_url).json()[u'files'][u'%s.yml' % self.name][u'raw_url']
        else:
            url = config_url
        cm.addRemoteConfig("%s_remote" % self.name, url)

    @background_job('get_updates', error_callback=lambda x: print(x))
    def checkUpdates(self):
        logging.info('Checking %s updates' % self.name)
        if "%s_remote" not in cm.configs:
            self.getRemoteConfig()
        remote = cm["%s_remote" % self.name]
        local = cm[self.name]

        if local._dict != remote._dict:
            cm.configs[self.name] = cm["%s_remote" % self.name]
            self.schema = cm[self.name]
            return True, self
        else:
            return False, self

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

from TransTES import icons_folder, DEBUG, cm