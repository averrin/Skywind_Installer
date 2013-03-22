#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import hashlib
import sys
import os
from PyQt4.QtCore import Qt, QObject, pyqtSignal, pyqtProperty, QThread
from PyQt4.QtGui import QColor, QListWidgetItem, QMessageBox, QLabel, QGridLayout, QWizardPage, QWizard, QLineEdit, QPushButton, QWidget, QListWidget, QProgressBar, QFileDialog, QHBoxLayout, QTextBrowser
import time

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.3'

from config import Config
import rarfile
import yaml


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
            QMessageBox.warning(self, u'Error', u'Incorrect path')
        self.updated.emit()

    @pyqtProperty(str)
    def getPath(self):
        return str(self.path_input.text())


class Installer(QObject):
    setProgress = pyqtSignal(int)

    def __init__(self, options, firer):

        QObject.__init__(self)
        if not hasattr(options, 'install_path') or not hasattr(options, 'distrib_path'):
            QMessageBox.warning(firer, u'Error', u'Incorrect options')
            firer.setEnabled(False)
            return

        self.options = options
        self.firer = firer

        self.wizard = QWizard()
        self.wizard.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.NoBackButtonOnLastPage)
        self.wizard.resize(800, 600)

        self.unwizard = QWizard()
        self.unwizard.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.NoBackButtonOnLastPage)
        self.unwizard.resize(800, 600)

        self.pip = self.PreInstallPage(self)
        self.cp = self.CheckPage(self)
        self.ip = self.InstallPage(self)

        self.puip = self.PreUnInstallPage(self)
        self.uip = self.UnInstallPage(self)

        self.wizard.addPage(self.pip)
        self.wizard.addPage(self.cp)
        self.wizard.addPage(self.ip)

        self.unwizard.addPage(self.puip)
        self.unwizard.addPage(self.uip)

    def install(self):
        self.wizard.setModal(True)
        self.wizard.show()

    def uninstall(self):
        self.unwizard.setModal(True)
        self.unwizard.show()

    class PreInstallPage(QWizardPage):
        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent
            
            self.setLayout(QGridLayout())
            self.setTitle('Options')
            self.setSubTitle('Please select destination folder and folder which contains distributive files.')

            self.path = PathPanel(default=self.parent.options.install_path)
            self.layout().addWidget(QLabel('Installation path:'), 1, 0)
            self.layout().addWidget(self.path, 1, 1)

            self.distrib_path = PathPanel(default=self.parent.options.distrib_path)
            self.layout().addWidget(QLabel('Distributive path:'), 2, 0)
            self.layout().addWidget(self.distrib_path, 2, 1)

            self.registerField('path', self.path, 'getPath', self.path.path_input.textChanged)
            self.registerField('distrib_path', self.distrib_path, 'getPath', self.distrib_path.path_input.textChanged)

            self.path.updated.connect(self.changed)
            self.distrib_path.updated.connect(self.changed)

        def initializePage(self):
            self.path.setPath(self.parent.options.install_path)
            self.distrib_path.setPath(self.parent.options.distrib_path)

        def changed(self):
            self.completeChanged.emit()

        def isComplete(self):
            return os.path.isdir(self.path.getPath) and os.path.isdir(self.distrib_path.getPath)


    class CheckPage(QWizardPage):
        setProgress = pyqtSignal(int)
        addComponentItem = pyqtSignal(str, str, bool, bool)
        editComponentItem = pyqtSignal(str, str)

        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.setTitle('Components')
            self.setSubTitle('Please select components which will be extracted to your destination folder.')

            self.status_label = QLabel()
            self.layout().addWidget(self.status_label, 1, 0)

            self.components_list = QListWidget()
            self.progress = QProgressBar()
            self.layout().addWidget(self.progress, 2, 0, 1, 4)
            self.layout().addWidget(self.components_list, 3, 0, 1, 4)

            addcomponent_button = QPushButton(u'Add component')
            addcomponent_button.setEnabled(False)
            self.layout().addWidget(addcomponent_button, 4, 0)

            self.is_done = False

            self.addComponentItem.connect(self.addListItem)
            self.setProgress.connect(self.progress.setValue)

            self.components_list.itemChanged.connect(self.completeChanged.emit)
            self.components_list.itemClicked.connect(self.completeChanged.emit)

            self.registerField('components', self, 'getComponents', self.components_list.itemClicked)

        def initializePage(self):
            self.distrib_path = self.field('distrib_path').toString()
            self.status_label.setText('Search components in %s...' % self.distrib_path)
            self.components_list.clear()
            self.progress.setMaximum(0)
            self.startSearchComponents()

        def startSearchComponents(self):
            self.schema = Config(open('currentVersion.yml'))

            self.w = Worker(lambda: self.searchComponent(self.distrib_path))
            self.w.done.connect(self.endSearchComponents)
            self.w.error.connect(self.parent.printError)

            self.w.start()

        def endSearchComponents(self):
            self.status_label.setText('Found components in %s' % self.distrib_path)

            self.is_done = True
            self.completeChanged.emit()

        def isComplete(self):
            self.wizard().components = self.getComponents
            return self.is_done and len(self.wizard().components)


        @pyqtProperty(list)
        def getComponents(self):
            return self.getSelectedItems()

        def getSelectedItems(self):
            list_widget = self.components_list
            items = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    items.append(item)

            return items


        def addListItem(self, component, title, valid=True, checked=True):
            item = QListWidgetItem(title)
            item.component = component
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
                    if 1024.0 > num > -1024.0:
                        return "%3.1f%s" % (num, x)
                    num /= 1024.0

                return "%3.1f%s" % (num, 'TB')

            self.progress.setMaximum(len(self.schema.files.keys()))

            for i, file_name in enumerate(self.schema.files.keys()):
                self.setProgress.emit(i)
                file_path = os.path.abspath(os.path.join(distrib_path, file_name))
                exist = os.path.isfile(file_path)
                match = True
                if not exist:
                    file_label = 'Missed: %s' % file_name
                else:
                    file_label = '%s [%s]' % (file_name, sizeof_fmt(os.path.getsize(file_path)))
                    if self.schema.files[file_name]['hash']:
                        hash_sum = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()
                        if hash_sum != self.schema.files[file_name]['hash']:
                            match = False
                            file_label = '%s Hash sum mismatched!' % file_label
                self.addComponentItem.emit(file_name, file_label, exist, match if exist else False)

            self.setProgress.emit(len(self.schema.files.keys()))

    class InstallPage(QWizardPage):
        setProgress = pyqtSignal(int)
        message = pyqtSignal(str)

        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.setTitle('Installation')
            self.setSubTitle('All selected components will be extracted.')

            self.layout().addWidget(QLabel(u'Installation progress'), 0, 0)
            self.progress = QProgressBar()
            self.progress.setMaximum(0)
            self.layout().addWidget(self.progress, 1, 0, 1, 2)

            self.log = QTextBrowser()
            self.layout().addWidget(self.log, 2, 0, 1, 2)

            self.setProgress.connect(self.progress.setValue)
            self.message.connect(self.log.append)
            self.is_done = False

        def initializePage(self):
            self.components = self.wizard().components
            self.startInstallation()

        def startInstallation(self):
            self.distrib_path = str(self.field('distrib_path').toString())
            self.path = str(self.field('path').toString())

            self.schema = Config(open('currentVersion.yml'))

            self.w = Worker(lambda: self.install(self.distrib_path, self.path))
            self.w.done.connect(self.endInstall)
            self.w.error.connect(self.parent.printError)

            self.w.start()

        def install(self, src, destination):
            self.message.emit(u'Started...')
            self.progress.setMaximum(len(self.components))
            for i, item in enumerate(self.components):
                self.setProgress.emit(i)
                file_path = os.path.abspath(os.path.join(src, str(item.component)))
                rf = rarfile.RarFile(file_path)
                self.message.emit('Extracting: %s' % item.component)
                dest_path = os.path.join(destination, self.schema.files[str(item.component)]['dest'])
                self.message.emit('to %s' % dest_path)
                rf.extractall(dest_path)

            self.generateUninstallList(destination, src, map(lambda x: str(x.component), self.components))

        def generateUninstallList(self, install_path, distrib_path, components):
            self.message.emit(u'Generating uninstall list...')

            with open('uninstall.list', 'w') as f:
                l = ''
                for i, distr_file in enumerate(components):
                    filepath = os.path.abspath(
                        os.path.join(distrib_path, distr_file)
                    )
                    rf = rarfile.RarFile(filepath)
                    file_list = {distr_file: []}
                    for fl in rf.infolist():
                        file_list[distr_file].append(
                            os.path.normpath(
                                os.path.join(install_path, self.schema.files[distr_file]['dest'], fl.filename)
                            )
                        )
                    l += yaml.dump(file_list, default_flow_style=False, indent=4, allow_unicode=True,
                                   encoding="utf-8") + '\n'
                f.write(l)
                f.close()

        def endInstall(self):
            self.log.append(u'Finished')
            self.setProgress.emit(len(self.components))
            self.is_done = True
            self.completeChanged.emit()

        def isComplete(self):
            if self.is_done:
                self.wizard().finished.emit(1)
            return self.is_done

    class PreUnInstallPage(QWizardPage):
        setProgress = pyqtSignal(int)
        addComponentItem = pyqtSignal(str, str, bool, bool)
        editComponentItem = pyqtSignal(str, str)

        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.setTitle('Components')
            self.setSubTitle('This page cant handle manually installed components')

            self.components_list = QListWidget()
            self.progress = QProgressBar()
            self.layout().addWidget(self.progress, 2, 0, 1, 4)
            self.layout().addWidget(self.components_list, 3, 0, 1, 4)

            self.setProgress.connect(self.progress.setValue)

            self.is_done = False

            self.addComponentItem.connect(self.addListItem)
            self.setProgress.connect(self.progress.setValue)

            self.components_list.itemChanged.connect(self.completeChanged.emit)
            self.components_list.itemClicked.connect(self.completeChanged.emit)

        def initializePage(self):
            schema = Config(open('uninstall.list'))
            for component in schema.keys():
                self.addListItem(component, component)

            self.is_done = True

        def isComplete(self):
            self.wizard().components = self.getComponents
            return self.is_done and len(self.wizard().components)


        @pyqtProperty(list)
        def getComponents(self):
            return self.getSelectedItems()

        def getSelectedItems(self):
            list_widget = self.components_list
            items = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    items.append(item)

            return items


        def addListItem(self, component, title, valid=True, checked=True):
            item = QListWidgetItem(title)
            item.component = component
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


    class UnInstallPage(QWizardPage):
        setProgress = pyqtSignal(int)
        message = pyqtSignal(str)

        def __init__(self, parent):
            QWizardPage.__init__(self)
            self.parent = parent

            self.setLayout(QGridLayout())
            self.setTitle('Uninstallation')
            self.setSubTitle('All selected components will be removed.')

            self.layout().addWidget(QLabel(u'Uninstallation progress'), 0, 0)
            self.progress = QProgressBar()
            self.progress.setMaximum(0)
            self.layout().addWidget(self.progress, 1, 0, 1, 2)

            self.log = QTextBrowser()
            self.layout().addWidget(self.log, 2, 0, 1, 2)

            self.setProgress.connect(self.progress.setValue)
            self.message.connect(self.log.append)
            self.is_done = False

        def initializePage(self):
            self.components = self.wizard().components
            self.startUninstallation()

        def startUninstallation(self):
            # self.distrib_path = str(self.parent.options.Skyrim.path)
            self.path = str(self.parent.options.install_path)

            self.schema = Config(open('currentVersion.yml'))

            self.w = Worker(lambda: self.uninstall(self.path, map(lambda x: str(x.component), self.components)))
            self.w.done.connect(self.endUninstall)
            self.w.error.connect(self.parent.printError)

            self.w.start()

        def uninstall(self, path, components):
            self.message.emit('Start uninstalling...')
            schema = Config(open('uninstall.list'))

            self.progress.setMaximum(len(components))

            i = 0
            for component in schema.keys():
                if component in components:
                    i += 1
                    self.setProgress.emit(i)
                    for fl in schema[component]:
                        if os.path.isfile(fl):
                            os.remove(fl)
                        elif os.path.isdir(fl):
                            if not os.listdir(fl):
                                os.removedirs(fl)

        def endUninstall(self):
            self.log.append(u'Finished')
            self.is_done = True
            self.completeChanged.emit()

        def isComplete(self):
            if self.is_done:
                self.wizard().finished.emit(1)
            return self.is_done

    def printError(self, e):
        print(e)



