#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import os

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.3'

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from config import Config


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


class PathPanel(QWidget):
    updated = pyqtSignal()

    def __init__(self, default='', button_title='...'):
        QWidget.__init__(self)

        self.path_input = QLineEdit(default)
        self.browse_button = QPushButton(button_title)

        self.browse_button.clicked.connect(self.browse)

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.path_input)
        self.layout().addWidget(self.browse_button)

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, u'Choose folder', '')
        if path:
            self.setPath(path)

    def setPath(self, path):
        if os.path.isdir(path):
            self.path_input.setText(path)
        else:
            QMessageBox.warning(self.Skywind, u'Error', u'Incorrect path')
        self.updated.emit()

    @pyqtProperty(str)
    def getPath(self):
        return self.path_input.text()


class Installer(QObject):
    setProgress = pyqtSignal(int)

    def __init__(self, skywind):

        self.Skywind = skywind

        QObject.__init__(self)

        self.wizard = QWizard()
        self.wizard.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.NoBackButtonOnLastPage)

        self.pip = self.PreInstallPage(self)
        self.cp = self.CheckPage(self)
        self.ip = self.InstallPage()

        self.wizard.addPage(self.pip)
        self.wizard.addPage(self.cp)
        self.wizard.addPage(self.ip)

    def install(self):
        self.wizard.setModal(True)
        self.wizard.show()


    class PreInstallPage(QWizardPage):
        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.layout().addWidget(QLabel('<h2>Options</h2>'), 0, 0)

            self.path = PathPanel(default=self.parent.Skywind.Skyrim.path)
            self.layout().addWidget(QLabel('Installation path:'), 1, 0)
            self.layout().addWidget(self.path, 1, 1)

            self.distrib_path = PathPanel(default=os.path.abspath('.'))
            self.layout().addWidget(QLabel('Distributive path:'), 2, 0)
            self.layout().addWidget(self.distrib_path, 2, 1)

            self.registerField('path', self.path, 'getPath', self.path.path_input.textChanged)
            self.registerField('distrib_path', self.distrib_path, 'getPath', self.distrib_path.path_input.textChanged)

            self.path.updated.connect(self.changed)
            self.distrib_path.updated.connect(self.changed)

        def changed(self):
            self.completeChanged.emit()

        def isComplete(self):
            return os.path.isdir(self.path.getPath) and os.path.isdir(self.distrib_path.getPath)


    class CheckPage(QWizardPage):
        setProgress = pyqtSignal(int)
        addComponentItem = pyqtSignal(str, bool, bool)
        editComponentItem = pyqtSignal(str, str)

        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.layout().addWidget(QLabel('<h2>Components</h2>'), 0, 0)

            self.distrib_label = QLabel()
            self.layout().addWidget(self.distrib_label, 1, 0)

            self.components_list = QListWidget()
            self.progress = QProgressBar()
            self.layout().addWidget(self.progress, 2, 0, 1, 2)
            self.layout().addWidget(self.components_list, 3, 0, 1, 2)

            addcomponent_button = QPushButton(u'Add component')
            addcomponent_button.setEnabled(False)
            self.layout().addWidget(addcomponent_button, 4, 0)

            self.is_done = False

            self.addComponentItem.connect(self.addListItem)
            self.setProgress.connect(self.progress.setValue)
            
            self.components_list.itemChanged.connect(self.completeChanged.emit)
            self.components_list.itemClicked.connect(self.completeChanged.emit)

            self.registerField('components', self.components_list)

        def initializePage(self):
            self.distrib_path = self.field('distrib_path').toString()
            print(self.distrib_path)
            self.distrib_label.setText('Search components in %s...' % self.distrib_path)

            self.components_list.clear()

            self.progress.setMaximum(0)

            self.startSearchComponents()

        def startSearchComponents(self):
            self.schema = Config(open('currentVersion.yml'))

            self.w = Worker(lambda: self.searchComponent(self.distrib_path))
            self.w.done.connect(self.endSearchComponents)
            self.w.error.connect(self.printError)

            self.w.start()

        def endSearchComponents(self):
            self.distrib_label.setText('Found components in %s' % self.distrib_path)

            self.is_done = True
            self.completeChanged.emit()

        def isComplete(self):
            return self.is_done and len(self.getSelectedItems())

        def getSelectedItems(self):
            list_widget = self.components_list
            items = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    items.append(str(item.text()))
    
            return items


        def addListItem(self, title, valid=True, checked=True):
            item = QListWidgetItem(title)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if valid:
                pass
            else:
                item.setForeground(QColor('gray'))

            if checked:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

            self.components_list.addItem(item)


        def searchComponent(self, distrib_path):

            distrib_path = str(distrib_path)

            self.setProgress.emit(0)

            def sizeof_fmt(num):
                for x in ['bytes', 'KB', 'MB', 'GB']:
                    if num < 1024.0 and num > -1024.0:
                        return "%3.1f%s" % (num, x)
                    num /= 1024.0

                return "%3.1f%s" % (num, 'TB')

            self.progress.setMaximum(len(self.schema.keys()))

            for i, distr_file in enumerate(self.schema.keys()):
                self.setProgress.emit(i)
                filepath = os.path.abspath(os.path.join(distrib_path, distr_file))
                exist = os.path.isfile(filepath)
                if not exist:
                    distr_file = 'Missed: %s' % distr_file
                else:
                    distr_file = '%s [%s]' % (distr_file, sizeof_fmt(os.path.getsize(filepath)))
                self.addComponentItem.emit(distr_file, exist, True if exist else False)
                # print(filepath)

            self.setProgress.emit(len(self.schema.keys()))

        def printError(self, e):
            print(e)


    class InstallPage(QWizardPage):
        def __init__(self):
            QWizardPage.__init__(self)
            self.setLayout(QVBoxLayout())
            self.layout().addWidget(QLabel('Install'))


    def makeProgress(self, title):
        s = QPushButton(u'Stop')
        s.setEnabled(False)

        d = QProgressDialog(title, u"Stop", 0, 0)
        d.setCancelButton(s)
        d.setModal(True)
        d.closeEvent = lambda event: event.ignore()

        self.setProgress.connect(d.setValue)

        return d

    def startInstall(self):
        # try:
        self.schema = Config(open('currentVersion.yml'))

        distrib_path = self.getDistribPath()

        self.w = Worker(lambda: self.checkFiles(distrib_path))
        self.w.done.connect(self.endCheck)
        self.w.error.connect(self.printError)

        self.p = self.makeProgress(u"Check distributive files")

        self.w.start()
        self.p.show()

        # except:
        #     QMessageBox.warning(self.Skywind, u'Error', u'File currentVersion.yml missed or corrupted.')


    def checkFiles(self, distrib_path):

        bad_files = []

        def sizeof_fmt(num):
            for x in ['bytes', 'KB', 'MB', 'GB']:
                if num < 1024.0 and num > -1024.0:
                    return "%3.1f%s" % (num, x)
                num /= 1024.0
            return "%3.1f%s" % (num, 'TB')

        self.p.setMaximum(len(self.schema.keys()))
        for i, distr_file in enumerate(self.schema.keys()):
            self.setProgress.emit(i)
            filepath = os.path.abspath(os.path.join(distrib_path, distr_file))
            print(filepath)
            if not os.path.isfile(filepath):
                print('%s missed' % distr_file)
                bad_files.append(distr_file)
            else:
                if self.schema[distr_file]['hash']:
                    hash = hashlib.sha256(open(filepath, 'rb').read()).hexdigest()
                    if hash != self.schema[distr_file]['hash']:
                        print(hash)
                        print('%s seems corrupted' % distr_file)
                        bad_files.append(distr_file)
                    else:
                        print('%s seems valid. Size: %s' % (distr_file, sizeof_fmt(os.path.getsize(filepath))))

        return bad_files

    def getDistribPath(self):
        distrib_path = QFileDialog.getExistingDirectory(self.Skywind, u'Distributive files folder', '')
        if distrib_path:
            self.distrib_path = str(distrib_path)

        return self.distrib_path


    def endCheck(self, bad_files, confirm=False):
        self.p.hide()
        if bad_files:
            QMessageBox.warning(self.Skywind, u'Error', u'Some missed or corrupted:\n%s' % ',\n'.join(bad_files))
        else:
            # QMessageBox.information(self, u'Success', u'All files are valid')

            if not confirm:
                msgBox = QMessageBox()
                msgBox.setText(u"All files are valid")
                msgBox.setInformativeText(u"Continue installation?")
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Discard)
                ret = msgBox.exec_()
                if ret == QMessageBox.Yes:
                    confirm = True

            if confirm:
                path = self.Skyrim.path
                msgBox = QMessageBox()
                msgBox.setText(u"Choose installation path...")
                msgBox.setInformativeText(u'Files will be extracted to "%s". Do you want to change?' % path)
                msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.Discard)
                ret = msgBox.exec_()
                if ret == QMessageBox.Yes:
                    path = QFileDialog.getExistingDirectory(self, u'Installation folder', '')
                    if path:
                        path = str(path)

                self.w = Worker(lambda: self.extractFiles(path, self.distrib_path))
                self.w.done.connect(self.endExtract)
                self.w.error.connect(self.printError)

                self.p = self.makeProgress(u"Extracting files...")

                self.w.start()
                self.p.show()


    def extractFiles(self, path, distrib_path):
        print('Start extraction. Files: %s to %s' % (len(self.schema.keys()), path))
        self.p.setMaximum(len(self.schema.keys()))
        for i, distr_file in enumerate(self.schema.keys()):
            self.setProgress.emit(i)
            filepath = os.path.abspath(os.path.join(distrib_path, distr_file))
            rf = rarfile.RarFile(filepath)
            dest_path = os.path.join(path, self.schema[distr_file]['dest'])
            print('Start extracting %s to %s' % (distr_file, dest_path))
            rf.extractall(dest_path)


    def endExtract(self, bad_files, confirm=False):
        self.p.hide()
        QMessageBox.information(self, u'Success', u'All files installed')

    def startUninstall(self):
        try:
            self.schema = Config(open('currentVersion.yml'))

            distrib_path = self.getDistribPath()

            self.w = Worker(lambda: self.uninstallFiles(self.Skyrim.path, distrib_path))
            self.w.done.connect(self.endUninstall)
            self.w.error.connect(self.printError)

            self.p = self.makeProgress(u"Delete files")

            self.w.start()
            self.p.show()

        except:
            QMessageBox.warning(self, u'Error', u'File currentVersion.yml missed or corrupted.')

    def uninstallFiles(self, path, distrib_path):
        self.p.setMaximum(len(self.schema.keys()))
        for i, distr_file in enumerate(self.schema.keys()):
            self.setProgress.emit(i)
            print('Remove content of %s' % distr_file)
            try:
                filepath = os.path.abspath(os.path.join(distrib_path, distr_file))
                rf = rarfile.RarFile(filepath)
                dest_path = os.path.join(path, self.schema[distr_file]['dest'])
                for f in rf.infolist():
                    filepath = os.path.join(dest_path, f.filename)
                    try:
                        os.remove(filepath)
                    except:
                        pass
            except:
                pass

    def endUninstall(self):
        self.p.hide()
        QMessageBox.information(self, u'Success', u'All files removed')