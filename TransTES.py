#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import functools
import hashlib
import sys
import logging
from PyQt4.QtGui import QWidget, QVBoxLayout, QMainWindow, QIcon, QHBoxLayout, QStatusBar, QSizePolicy, QLabel, QApplication, QPushButton, QPixmap, QFileDialog, QMessageBox, QToolBar, QDockWidget, QStackedWidget, QAction, QToolButton, QTextBrowser
from PyQt4.QtCore import Qt, pyqtSignal, QSize, QThread
import os
from managers import DebugManager, ConfigManager, DepManager, Internal, External


__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.1.0'

config_folder = 'config'
icons_folder = os.path.join(config_folder, 'icons') + os.sep
contrib_folder = os.path.join(config_folder, 'contrib') + os.sep
temp_folder = os.path.join(config_folder, 'temp') + os.sep
frozen = getattr(sys, "frozen") if hasattr(sys, 'frozen') else False

cm = ConfigManager(ignore_optional=True)
cm.addConfig("config", os.path.join(config_folder, 'config.yml'))
cm.addConfig("Skywind", os.path.join(config_folder, 'Skywind.yml'), optional=True)
cm.addConfig("Skyblivion", os.path.join(config_folder, 'Skyblivion.yml'), optional=True)

try:
    DEBUG = '-debug' in sys.argv or cm['config'].debug
except Exception as e:
    logging.error(e)
    DEBUG = True
if DEBUG:
    debug = DebugManager('TransTES', __version__)

dm = DepManager()

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

from installer import Encrypted
from core import GameInfoPanel, ModInfoPanel
from ui import SideBar, Browser, SBAction
# from dm import DM
from hub import Hub


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

        games_panel.resize(500, 100)

        is_skywind = "Skywind" in cm.configs
        is_skyblivion = "Skyblivion" in cm.configs

        self.Skyrim = GameInfoPanel('Skyrim', force_browse=True)

        if is_skywind:
            self.Morrowind = GameInfoPanel('Morrowind')
            games_panel.layout().addWidget(self.Morrowind)
            self.Skywind = ModInfoPanel('Skywind', self.Skyrim, self.Morrowind)
            self.Skywind.get_updates.connect(self.haveUpdates)

        if is_skyblivion:
            self.Oblivion = GameInfoPanel('Oblivion')
            games_panel.layout().addWidget(self.Oblivion)
            self.Skyblivion = ModInfoPanel('Skyblivion', self.Skyrim, self.Oblivion)
            self.Skyblivion.get_updates.connect(self.haveUpdates)

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

        # self.dm = DM(os.path.abspath(u'Data Files'))
        # self.dm.onShow = lambda: self.setMaximumWidth(games_panel.width())

        self.hub = Hub()
        hub = self.createSBAction(QIcon(icons_folder + 'app.png'), 'Hub', self.hub, toolbar=True, widgetWidth=500)

        self.readme = Browser()
        # self.readme.onShow = lambda: self.setMaximumWidth(games_panel.width())
        self.createSBAction(QIcon(icons_folder + 'readme.png'), 'Readme', self.readme, toolbar=True,
                                     widgetWidth=700, titleWidget=self.readme.toolbar)
        # self.createSBAction(QIcon(icons_folder + 'dm.png'),
        #                     'Downloads', self.dm, toolbar=True,
        #                     titleWidget=self.dm.toolbar)

        if DEBUG:
            self.initDebug(is_skyblivion, is_skywind)
        else:
            hub.showWidget()

        logging.info('Done ui building')

    def haveUpdates(self, args):
        have_updates, mod = args
        if have_updates:
            print('Can update %s' % mod.name)
        else:
            print('%s is latest version' % mod.name)

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

    def initDebug(self, is_skyblivion, is_skywind):
        report = QTextBrowser()
        report.resize(800, 600)
        bug_thread = cm['config']['installer_thread']
        prefix = u"""Please copy this report text and post it into this thread:
%s<br><br>""" % bug_thread
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
            extra['SKYWIND_CONFIG'] = cm['config']['skywind_url']
        if is_skyblivion:
            extra['OBLIVION_PATH'] = self.Oblivion.path
            extra['OBLIVION_IV'] = self.Oblivion.is_valid()
            extra['OBLIVION_EV'] = self.Oblivion.exe_valid
            extra['OBLIVION_FV'] = self.Oblivion.folder_valid
            extra['SKYBLIVION_DISTRIBPATH'] = self.Skyblivion.distrib_path
            extra['SKYBLIVION_INSTALLPATH'] = self.Skyblivion.install_path
            extra['SKYBLIVION_CONFIG'] = cm['config']['skyblivion_url']
        report.onShow = lambda: report.setHtml(debug.getReport(prefix=prefix, extra=extra))
        self.createSBAction(QIcon(icons_folder + 'bug.png'),
                            'Bug Report', report, toolbar=True)


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
                hash_sum = hashlib.sha256(f.read()).hexdigest()
            msgBox = QTextBrowser()
            msgBox.setText(u'Hash sum calculated\nhash: %s' % hash_sum)
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
                hash_sum = hashlib.sha256(f.read()).hexdigest()

            msgBox = QTextBrowser()
            msgBox.setText(u'File encrypted. Hash sums:\nhash: %s\noriginal_hash: %s' % (hash_sum, original_hash))
            msgBox.resize(500, 100)
            msgBox.show()
            qtapp.exec_()

            sys.exit(0)
    main()