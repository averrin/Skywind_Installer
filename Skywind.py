#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import logging

logging.basicConfig(format='[%(asctime)s] %(levelname)s:\t\t%(message)s', filename='skywind.log',
                    level=logging.DEBUG,
                    datefmt='%d.%m %H:%M:%S')

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.3'

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from checker import *

from installer import Installer

DEBUG = False

if len(sys.argv) > 1 and sys.argv[1] == '--debug':      #TODO: make it right
    DEBUG = True


class GameInfoPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, game):
        self.game = game
        self.is_steam = check_steam(self.game)
        self.path = get_path(self.game, self.is_steam)

        QWidget.__init__(self)
        self.setLayout(QHBoxLayout())

        self.layout().setAlignment(Qt.AlignTop)

        self.icon = QLabel()
        self.icon.setPixmap(QPixmap('icons/%s.png' % self.game).scaledToWidth(64, Qt.SmoothTransformation))

        self.path_label = QLabel(self.path)

        self.browse = QPushButton('Change')
        self.browse.clicked.connect(self.changePath)

        # self.layout().addWidget(self.icon)

        self.info_panel = QWidget()
        self.info_panel.setLayout(QVBoxLayout())

        path_panel = QWidget()
        path_panel.setLayout(QHBoxLayout())

        self.layout().addWidget(self.info_panel)
        path_panel.layout().addWidget(self.path_label)
        path_panel.layout().addWidget(self.browse)

        self.info_panel.layout().addWidget(path_panel)

        self.exe_info, self.exe_valid = self.get_exe_info(self.game, self.path, self.is_steam)
        self.folder_info, self.folder_valid = self.get_folder_info(self.game, self.path)

        self.exe_info_label = QLabel(self.exe_info)
        self.folder_info_label = QLabel(self.folder_info)

        self.info_panel.layout().addWidget(self.exe_info_label)
        self.info_panel.layout().addWidget(self.folder_info_label)

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

        self.icon_name = 'Skywind'
        self.icon = QLabel()
        self.icon.setPixmap(QPixmap('icons/%s.png' % self.icon_name).scaledToWidth(64, Qt.SmoothTransformation))

        # self.layout().addWidget(self.icon)

        self.info_str, self.is_valid = check_skywind(self.Skyrim.path)
        self.info = QLabel(self.info_str)

        self.layout().addWidget(self.info)

        if not DEBUG:
            self.install.setEnabled(self.Morrowind.is_valid())

        self.layout().addWidget(self.install)

        self.updateInstallButton()
        self.updated.emit()


    def update(self):
        self.info_str, self.is_valid = check_skywind(self.Skyrim.path)
        self.info.setText(self.info_str)
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
            self.install.setText('Uninstall')
            self.install.clicked.connect(self.installer.uninstall)


class UI(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowTitle(u"Skywind" if not DEBUG else 'Skywind [DEBUG]')
        self.setWindowIcon(QIcon('icons/app.png'))

        panel = QWidget()
        panel.setLayout(QVBoxLayout())
        self.setCentralWidget(panel)

        self.resize(500, 180)

        self.Morrowind = GameInfoPanel('Morrowind')
        self.Skyrim = GameInfoPanel('Skyrim')

        panel.layout().addWidget(self.Morrowind)
        panel.layout().addWidget(self.Skyrim)

        self.Skywind = SkywindPanel(self.Skyrim, self.Morrowind)
        panel.layout().addWidget(self.Skywind)

        buttons = QWidget()
        buttons.setLayout(QHBoxLayout())
        panel.layout().addWidget(buttons)


        # buttons.layout().addWidget(self.install)
        # 
        # exit_button = QPushButton('Exit')
        # exit_button.clicked.connect(sys.exit)
        # buttons.layout().addWidget(exit_button)

        panel.layout().setAlignment(Qt.AlignTop)

        self.statusBar = QStatusBar(self)
        self.statusBar.addPermanentWidget(QWidget().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.setStatusBar(self.statusBar)
        self.statusBar.addPermanentWidget(QLabel(u'Version: %s  ' % __version__))
        self.statusBar.setSizeGripEnabled(False)


def main():
    qtapp = QApplication(sys.argv)
    win = UI()
    win.show()

    qtapp.exec_()


if __name__ == '__main__':
    main()