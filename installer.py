#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import hashlib
from subprocess import Popen, PIPE
import sys
import os
from PyQt4.QtCore import Qt, QObject, pyqtSignal, pyqtProperty, QThread
from PyQt4.QtGui import QColor, QListWidgetItem, QMessageBox, QLabel, QGridLayout, QWizardPage, QWizard, QLineEdit, QPushButton, QWidget, QListWidget, QProgressBar, QFileDialog, QHBoxLayout, QTextBrowser
import shutil
from distutils.dir_util import copy_tree

import random, struct
import zipfile
from Crypto.Cipher import AES
import py7zlib
from utils.config import Config

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.3'

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

    def __init__(self, default='', button_title='...', select_dir=True):
        QWidget.__init__(self)

        self.select_dir = select_dir

        self.path_input = QLineEdit(default)
        self.browse_button = QPushButton(button_title)

        self.browse_button.clicked.connect(self.browse)

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.path_input)
        self.layout().addWidget(self.browse_button)

    def browse(self):
        if self.select_dir:
            path = QFileDialog.getExistingDirectory(self, u'Choose folder', '')
        else:
            path = QFileDialog.getSaveFileName(self, u'Save as', '')
        if path:
            self.setPath(path)

    def setPath(self, path):
        path = unicode(path)
        if (self.select_dir and os.path.isdir(path)) or not self.select_dir:
            self.path_input.setText(path)
        else:
            QMessageBox.warning(self, u'Error', u'Incorrect path')
        self.updated.emit()

    @pyqtProperty(str)
    def getPath(self):
        return unicode(self.path_input.text())


class Installer(QObject):
    setProgress = pyqtSignal(int)

    def __init__(self, options, schema, firer):

        QObject.__init__(self)
        if not hasattr(options, 'install_path') or not hasattr(options, 'distrib_path'):
            QMessageBox.warning(firer, u'Error', u'Incorrect options')
            firer.setEnabled(False)
            return

        self.schema = schema

        self.options = options
        self.firer = firer

        self.wizard = QWizard()
        self.wizard.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.NoBackButtonOnLastPage)
        self.wizard.resize(800, 600)
        self.wizard.schema = schema

        self.unwizard = QWizard()
        self.unwizard.setOptions(QWizard.NoBackButtonOnStartPage | QWizard.NoBackButtonOnLastPage)
        self.unwizard.resize(800, 600)
        self.unwizard.schema = schema

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
            self.setSubTitle('Please select destination folder and folder which contains downloaded files.')

            self.path = PathPanel(default=self.parent.options.install_path)
            self.layout().addWidget(QLabel('Installation path:'), 1, 0)
            self.layout().addWidget(self.path, 1, 1)

            self.distrib_path = PathPanel(default=self.parent.options.distrib_path)
            self.layout().addWidget(QLabel('Downloaded files:'), 2, 0)
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
        addComponentItem = pyqtSignal(object, str, bool, bool)
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
            self.components = []
            self.distrib_path = unicode(self.field('distrib_path').toString())
            self.status_label.setText('Search components in %s...' % self.distrib_path)
            self.components_list.clear()
            self.progress.setMaximum(0)
            self.startSearchComponents()

        def startSearchComponents(self):
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
            return self.is_done and len(self.getComponents)


        @pyqtProperty(list)
        def getComponents(self):
            components = []
            for item in self.getSelectedItems():
                if item.component.available:
                    components.append(item.component)
            return components

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

            self.setProgress.emit(0)

            self.progress.setMaximum(len(self.wizard().schema.components.keys()))

            for i, component_name in enumerate(self.wizard().schema.components.keys()):
                component = Component.create(component_name, distrib_path,
                                             self.wizard().schema.components[component_name])
                self.setProgress.emit(i)
                if component is not None:
                    self.addComponentItem.emit(
                        component,
                        component.title,
                        component.available,
                        component.default_install
                    )
                    self.components.append(component)

            self.setProgress.emit(len(self.wizard().schema.components.keys()))

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
            self.distrib_path = unicode(self.field('distrib_path').toString())
            self.path = unicode(self.field('path').toString())

            self.w = Worker(lambda: self.install(self.distrib_path, self.path))
            self.w.done.connect(self.endInstall)
            self.w.error.connect(self.parent.printError)

            self.w.start()

        def install(self, src, destination):
            self.message.emit(u'Started...')
            self.progress.setMaximum(len(self.components))
            for i, component in enumerate(self.components):
                self.setProgress.emit(i)
                component.install(destination, message=self.message.emit)

            self.generateUninstallList(destination, src, self.components)

        def generateUninstallList(self, install_path, distrib_path, components):
            self.message.emit(u'Generating uninstall list...')

            with open('config/uninstall.yml', 'w') as f:
                l = ''
                for i, component in enumerate(components):
                    file_list = {component.name: component.uninstall_info}
                    l += yaml.dump(file_list, default_flow_style=False, indent=4, allow_unicode=True,
                                   encoding="utf-8")
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
        addComponentItem = pyqtSignal(object, str, bool, bool)
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

        def initializePage(self):         #TODO: make separate uninstallers
            self.components = []
            self.components_list.clear()
            if os.path.isfile('config/uninstall.yml'):
                schema = Config(open('config/uninstall.yml'))
            else:
                schema = {}
            for component_name in schema.keys():
                component = Component.create(component_name, None, schema[component_name])
                if component is not None:
                    self.addComponentItem.emit(
                        component,
                        component.title,
                        True,
                        component.default_uninstall
                    )
                    self.components.append(component)

            self.is_done = True

        def isComplete(self):
            self.wizard().components = self.getComponents
            return self.is_done and len(self.wizard().components)


        @pyqtProperty(list)
        def getComponents(self):
            components = []
            for item in self.getSelectedItems():
                if item.component.available:
                    components.append(item.component)
            return components

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
            self.path = unicode(self.parent.options.install_path)

            self.w = Worker(lambda: self.uninstall(self.path, self.components))
            self.w.done.connect(self.endUninstall)
            self.w.error.connect(self.parent.printError)

            self.w.start()

        def uninstall(self, path, components):
            self.message.emit('Start uninstalling...')
            schema = Config(open('config/uninstall.yml'))

            self.progress.setMaximum(len(components))

            component_names = [x.name for x in components]

            i = 0
            for component in components:
                if component.name in component_names:
                    i += 1
                    self.setProgress.emit(i)
                    component.uninstall(schema[component.name], message=self.message.emit)

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


class Component(object):
    def __init__(self, name, src_folder, kwargs):
        self.name = name
        self.src_folder = src_folder
        self.__dict__.update(kwargs)

    @classmethod
    def create(cls, name, src_folder, kwargs):
        component_types = {
            'archive': Archive,
            'encrypted': Encrypted,
            'folder': Folder,
            'file': SingleFile
        }
        if 'type' in kwargs:
            component_class = component_types.get(kwargs['type'], None)
            return component_class(name, src_folder, kwargs)

    @property
    def title(self):
        return self.name

    @property
    def available(self):
        return True

    @property
    def default_install(self):
        return False

    @property
    def default_uninstall(self):
        return True

    @property
    def is_optional(self):
        if hasattr(self, 'optional'):
            return self.optional
        else:
            return False

    def install(self, destination, message=None):
        pass

    def uninstall(self, schema, message=None):
        pass

    @property
    def uninstall_info(self):
        return None


class Archive(Component):
    @property
    def available(self):
        if self.src_folder is not None:
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            return os.path.isfile(file_path)
        else:
            return True

    @property
    def title(self):
        def sizeof_fmt(num):
            for x in ['bytes', 'KB', 'MB', 'GB']:
                if 1024.0 > num > -1024.0:
                    return "%3.1f%s" % (num, x)
                num /= 1024.0
            return "%3.1f%s" % (num, 'TB')

        if self.src_folder is not None:
            if not self.available:
                return 'Missed: %(name)s' % self.__dict__
            elif not self.match:
                return '%(name)s [Check sum mismatched]' % self.__dict__
            else:
                file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
                return '%s [%s]' % (self.name, sizeof_fmt(os.path.getsize(file_path)))
        else:
            return self.name

    @property
    def default_install(self):
        return self.available and self.match and not self.is_optional

    @property
    def match(self):
        if not hasattr(self, 'matched'):
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            if hasattr(self, 'hash') and self.hash:
                with open(file_path, 'rb') as f:
                    hash_sum = hashlib.sha256(f.read()).hexdigest()
                    self.matched = hash_sum == self.hash
            else:
                self.matched = True
        return self.matched

    def install(self, destination, message=None):
        self.destination = destination
        if message is None:
            message = lambda x: None
        file_path = os.path.abspath(os.path.join(self.src_folder, unicode(self.name)))
        message('Extracting: %s' % self.name)
        dest_path = os.path.join(destination, self.dest)
        message('to %s' % dest_path)

        if self.name.endswith('.rar'):
            self.extract_rar(file_path, dest_path)
        elif self.name.endswith('.zip'):
            self.extract_zip(file_path, dest_path)
        elif self.name.endswith('.7z'):
            self.extract_7z(file_path, dest_path)
        else:
            message('Cant handle archive format')

    def extract_7z(self, file_path, dest_path):
        cmd = ['7z.exe', 'x', '-y', '-o' + dest_path, file_path]
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out = p.communicate()[0].strip().split('\r\n')
        if out[-2] == 'Error:':
            raise Exception('Error during extraction')

    def extract_rar(self, file_path, dest_path):
        rf = rarfile.RarFile(file_path)
        rf.extractall(dest_path)

    def extract_zip(self, file_path, dest_path):
        zf = zipfile.ZipFile(file_path)
        zf.extractall(dest_path)


    @property
    def uninstall_info(self):
        info = {'files': [], 'type': 'archive'}
        if hasattr(self, 'destination'):
            file_path = os.path.abspath(os.path.join(self.src_folder, unicode(self.name)))
            flist = []
            if self.name.endswith('.rar'):
                rf = rarfile.RarFile(file_path)
                flist = map(lambda x: x.filename, rf.infolist())
            elif self.name.endswith('.zip'):
                zf = zipfile.ZipFile(file_path)
                flist = zf.namelist()
            elif self.name.endswith('.7z'):
                cmd = ['7z.exe', 'l', file_path]
                p = Popen(cmd, stdout=PIPE, stderr=PIPE)
                flist = [ln.split('  ')[-1].strip() for ln in p.communicate()[0].split('\r\n')[16:-3]]
            for fl in flist:
                info['files'].append(
                    os.path.normpath(
                        os.path.join(self.destination, self.dest, fl)
                    )
                )
        return info

    def uninstall(self, schema, message=None):
        if message is None:
            message = lambda x: None
        for fl in schema['files']:
            if os.path.isfile(fl):
                os.remove(fl)
                message('Removed: %s' % fl)
            elif os.path.isdir(fl):
                if not os.listdir(fl):
                    os.removedirs(fl)
                message('Removed: %s' % fl)


class Encrypted(Component):
    def encrypt(self, key, in_filename, out_filename=None, chunksize=64 * 1024):
        key = hashlib.sha256(key).digest()
        if not out_filename:
            out_filename = in_filename + '.enc'

        iv = ''.join(chr(random.randint(0, 0xFF)) for i in range(16))
        encryptor = AES.new(key, AES.MODE_CBC, iv)
        filesize = os.path.getsize(in_filename)

        with open(in_filename, 'rb') as infile:
            with open(out_filename, 'wb') as outfile:
                outfile.write(struct.pack('<Q', filesize))
                outfile.write(iv)

                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    elif len(chunk) % 16 != 0:
                        chunk += ' ' * (16 - len(chunk) % 16)

                    outfile.write(encryptor.encrypt(chunk))

    def decrypt(self, key, in_filename, out_filename=None, chunksize=24 * 1024):
        key = hashlib.sha256(key).digest()
        if not out_filename:
            out_filename = os.path.splitext(in_filename)[0]

        with open(in_filename, 'rb') as infile:
            origsize = struct.unpack('<Q', infile.read(struct.calcsize('Q')))[0]
            iv = infile.read(16)
            decryptor = AES.new(key, AES.MODE_CBC, iv)

            with open(out_filename, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunksize)
                    if len(chunk) == 0:
                        break
                    outfile.write(decryptor.decrypt(chunk))

                outfile.truncate(origsize)

            if hasattr(self, 'original_hash') and self.original_hash:
                hash_sum = hashlib.sha256(open(out_filename, 'rb').read()).hexdigest()
                print(hash_sum)
                if hash_sum != self.original_hash:
                    raise Exception(u'Hash sum of result not matched with shipped')

    @property
    def match(self):
        if not hasattr(self, 'matched'):
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            if hasattr(self, 'hash') and self.hash:
                with open(file_path, 'rb') as f:
                    hash_sum = hashlib.sha256(f.read()).hexdigest()
                    print(hash_sum)
                    self.matched = hash_sum == self.hash
            else:
                self.matched = True
        return self.matched

    @property
    def available(self):
        if self.src_folder is not None:
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            return os.path.isfile(file_path)
        else:
            return True

    @property
    def title(self):
        def sizeof_fmt(num):
            for x in ['bytes', 'KB', 'MB', 'GB']:
                if 1024.0 > num > -1024.0:
                    return "%3.1f%s" % (num, x)
                num /= 1024.0
            return "%3.1f%s" % (num, 'TB')

        if self.src_folder is not None:
            if not self.available:
                return 'Missed: %(name)s' % self.__dict__
            elif not self.match:
                return '%(name)s [Check sum mismatched]' % self.__dict__
            else:
                file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
                return '%s [%s]' % (self.name, sizeof_fmt(os.path.getsize(file_path)))
        else:
            return self.name

    @property
    def default_install(self):
        return self.available and self.match and not self.is_optional

    def install(self, destination, message=None):
        self.destination = destination
        if message is None:
            message = lambda x: None
        from secret import key

        message('Decrypt: %s' % self.name)
        try:
            self.decrypt(key, os.path.join(self.src_folder, self.name), os.path.join(destination, self.dest))
            message('Done')
        except Exception, e:
            message(str(e))

    @property
    def uninstall_info(self):
        info = {'files': [], 'type': 'encrypted'}
        if hasattr(self, 'destination'):
            info['files'].append(
                os.path.normpath(os.path.abspath(os.path.join(self.destination, self.dest)))
            )
        return info

    def uninstall(self, schema, message=None):
        if message is None:
            message = lambda x: None
        for fl in schema['files']:
            if os.path.isfile(fl):
                os.remove(fl)
                message('Removed: %s' % fl)
            elif os.path.isdir(fl):
                if not os.listdir(fl):
                    os.removedirs(fl)
                message('Removed: %s' % fl)


class Folder(Component):
    @property
    def available(self):
        if self.src_folder is not None:
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            return os.path.isdir(file_path)
        else:
            return True

    @property
    def default_install(self):
        return self.available and not self.is_optional

    @property
    def title(self):
        if self.src_folder is not None:
            return 'Copy folder %s' % (
                self.name
            )
        else:
            return 'Remove folder %s' % self.name

    def install(self, destination, message=None):
        self.destination = destination
        if message is None:
            message = lambda x: None
        file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
        message('Copy: %s' % self.name)
        dest_path = os.path.join(destination, self.dest)
        message('to %s' % dest_path)
        try:
            try:
                copy_tree(file_path, dest_path)
            except OSError:
                shutil.copy(file_path, dest_path)
        except Exception, e:
            message('Error in copy process: %s' % e)

    @property
    def uninstall_info(self):
        info = {'files': [], 'type': 'folder'}
        if hasattr(self, 'destination'):
            info['files'].append(
                os.path.normpath(os.path.abspath(os.path.join(self.destination, self.dest)))
            )
        return info

    def uninstall(self, schema, message=None):
        if message is None:
            message = lambda x: None
        for fl in schema['files']:
            if os.path.isfile(fl):
                os.remove(fl)
            elif os.path.isdir(fl):
                os.removedirs(fl)
            message('Removed: %s' % fl)


class SingleFile(Component):
    @property
    def available(self):
        if self.src_folder is not None:
            file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
            return os.path.isfile(file_path)
        else:
            return True

    @property
    def default_install(self):
        return self.available and not self.is_optional

    @property
    def title(self):
        if self.src_folder is not None:
            return 'Copy file %s' % (
                self.name
            )
        else:
            return 'Remove file %s' % self.name

    def install(self, destination, message=None):
        self.destination = destination
        if message is None:
            message = lambda x: None
        file_path = os.path.abspath(os.path.join(self.src_folder, self.name))
        message('Copy: %s' % self.name)
        dest_path = os.path.join(destination, self.dest)
        message('to %s' % dest_path)
        try:
            shutil.copy(file_path, dest_path)
        except Exception, e:
            message('Error in copy process: %s' % e)

    @property
    def uninstall_info(self):
        info = {'files': [], 'type': 'file'}
        if hasattr(self, 'destination'):
            info['files'].append(
                os.path.normpath(os.path.abspath(os.path.join(self.destination, self.dest)))
            )
        return info

    def uninstall(self, schema, message=None):
        if message is None:
            message = lambda x: None
        for fl in schema['files']:
            if os.path.isfile(fl):
                os.remove(fl)
            elif os.path.isdir(fl):
                os.removedirs(fl)
            message('Removed: %s' % fl)


if __name__ == '__main__':
    e = Encrypted('skywind', '', {})
    from secret import key

    e.encrypt(key, 'C:\\Dropbox\\bin\\Skywind\\Skywind_open_059.esm', 'C:\\Dropbox\\bin\\Skywind\\Skywind.cmf')
    # e.decrypt(key, 'C:\\Dropbox\\bin\\Skywind\Skywind.esm.enc')


