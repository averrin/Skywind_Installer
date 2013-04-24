#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from PyQt4.QtGui import QWidget, QVBoxLayout, QApplication, QLabel, QHBoxLayout, QPixmap
from PyQt4.QtCore import pyqtSignal, Qt
import sys
from utils.async import background_job


__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.0'


class HubItem(QWidget):
    pos = -1
    dont_show = False

    def init(self):
        pass

    def remove(self):
        return True


class AsyncItem(HubItem):
    ready = pyqtSignal(object)
    error = pyqtSignal(Exception)
    message = pyqtSignal(object)

    def init(self):
        self.ready.connect(self.onReady)
        self._job()

    @background_job('ready', error_callback='error')
    def _job(self, *args):
        return self.job()

    def job(self):
        return

    def onReady(self, ret):
        pass


class Hub(QWidget):
    itemReady = pyqtSignal(object)
    itemError = pyqtSignal(Exception)
    itemRemoved = pyqtSignal()
    items = []

    def __init__(self):
        QWidget.__init__(self)
        self.setLayout(QVBoxLayout())

        self.itemReady.connect(self.addItemWidget)
        self.itemError.connect(print)
        self.itemRemoved.connect(self.layout().removeWidget)

        self.layout().setAlignment(Qt.AlignTop)

    def addItemWidget(self, item):
        if not item.dont_show:
            if item.pos == -1:
                self.layout().addWidget(item)
                item.pos = self.layout().count()
            else:
                self.layout().insertWidget(item.pos, item)

    @background_job('itemReady', error_callback='itemError')
    def addItem(self, item):
        self.items.append(item)
        item.hub = self
        item.init()
        return item

    @background_job('itemReady', error_callback='itemError')
    def removeItem(self, item):
        return item.remove()


def main():
    qt_app = QApplication(sys.argv)
    hub = Hub()
    item = AsyncItem()

    hub.show()
    hub.addItem(item)

    qt_app.exec_()


if __name__ == '__main__':
    main()
