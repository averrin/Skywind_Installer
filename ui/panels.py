#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from PyQt4.QtGui import QAction, QWidget, QVBoxLayout, QToolBar, QToolButton, QIcon, QDockWidget, QStackedWidget, QPushButton, QLabel
from PyQt4.QtWebKit import QWebView
import logging
from PyQt4.QtCore import QSize, Qt
from lxml import etree
import os
from requests import get
from utils.oauth import GistClient, GDClient


__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.0'


class Browser(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.setLayout(QVBoxLayout())

        self.view = QWebView()
        self.layout().addWidget(self.view)

        self.toolbar = QToolBar()

        self.config = False

        logging.info('Get readme')

        if os.path.isfile('config/Skywind.yml') and not cm['config']['skywind_disabled']:
            self.view.setHtml(self.getReadme('Skywind'))
            button = QToolButton()
            button.setIcon(QIcon(icons_folder + 'Skywind_icon.png'))
            button.clicked.connect(lambda: self.view.setHtml(self.getReadme('Skywind')))
            self.toolbar.addWidget(button)

        if os.path.isfile('config/Skyblivion.yml') and not cm['config']['skyblivion_disabled']:
            if not self.config:
                self.view.setHtml(self.getReadme('Skyblivion'))
            button = QToolButton()
            button.setIcon(QIcon(icons_folder + 'Skyblivion_icon.png'))
            button.clicked.connect(lambda: self.view.setHtml(self.getReadme('Skyblivion')))
            self.toolbar.addWidget(button)

        logging.info('Done with readme')

    def getReadme(self, game):
        self.config = cm[game]
        try:
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
        except Exception as e:
            logging.error(e)
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

        self.setIconSize(QSize(48, 48))
        self.setMovable(False)

        self.dock = QDockWidget()
        self.dock.setObjectName('sideBarDock')
        self.dock.stack = QStackedWidget()
        self.stack = self.dock.stack
        self.dock.setWidget(self.stack)
        self.parent.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        self.dock.hide()


class ToolPanel(QWidget):
    def __init__(self, Gists, Drive):
        QWidget.__init__(self)

        self.setLayout(QVBoxLayout())

        gh = QPushButton(u'Get GitHub key')
        gh.clicked.connect(lambda: Gists.auth())
        Gists.creds_read.connect(lambda: gh.setText(u'Github oauth: Done'))
        gd = QPushButton(u'Get Google Drive key')
        gd.clicked.connect(lambda: Drive.auth())
        Drive.creds_read.connect(lambda: gd.setText(u'Google Drive oauth: Done'))
        # ex = QPushButton(u'Close this window.')
        # ex.clicked.connect(self.close)
        self.layout().addWidget(gh)
        self.layout().addWidget(gd)
        # self.layout().addWidget(ex)

        self.layout().addWidget(QLabel('<hr>'))
        
        uninstaller = QPushButton(u'Uninstall components')
        self.layout().addWidget(uninstaller)

        # self.layout().setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.layout().setAlignment(Qt.AlignTop)


from Launcher import icons_folder, cm