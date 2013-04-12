#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import shutil
import logging


class DepManager(object):
    deps = []
    invalid = []

    def addDeps(self, deps):
        for dep in deps:
            self.addDep(dep)

    def addDep(self, dep):
        self.deps.append(dep)

    @property
    def ok(self):
        self.invalid = []
        for dep in self.deps:
            if not dep.check():
                if not dep.regenerate():
                    self.invalid.append(dep)
        if self.invalid:
            return False
        else:
            return True

    @property
    def critical(self):
        return filter(lambda x: not x.optional, self.invalid)

    class Dependency(object):
        optional = False

        def check(self):
            return True

        def regenerate(self):
            return True

        @property
        def info(self):
            return 'Dummy Dependency'


class External(DepManager.Dependency):
    def __init__(self, name, dest=None, contrib_folder='config/contrib', optional=False):
        self.optional = optional
        self.name = name
        self.dest = os.path.abspath(dest)
        self.contrib_folder = os.path.abspath(contrib_folder)
        DepManager.Dependency.__init__(self)

    def check(self):
        return os.path.exists(self.dest)

    def regenerate(self):
        logging.debug('Try to regenerate: %s' % self.name)
        if self.dest is not None:
            try:
                try:
                    shutil.copy(os.path.join(self.contrib_folder, self.name), self.dest)
                except OSError as e:
                    print(e)
                    shutil.copy(os.path.join(self.contrib_folder, self.name), os.path.join('.', self.name))
                logging.debug('Success regenerate: %s' % self.name)
                return True
            except Exception as e:
                print(e)
                logging.debug('Fail regenerate: %s, %s' % (self.name, e))
                return False
        else:
            return False

    @property
    def info(self):
        return '%s is %s' % (self.dest, 'exists' if self.check() else 'not exists')


class Internal(DepManager.Dependency):
    def __init__(self, path, is_folder=False, optional=False):
        self.optional = optional
        self.path = os.path.abspath(path)
        self.is_folder = is_folder

    def check(self):
        return os.path.exists(self.path)

    @property
    def info(self):
        return '%s is %s' % (self.path, 'exists' if self.check() else 'not exists')

    def regenerate(self):
        if self.is_folder:
            try:
                os.mkdir(self.path)
                logging.debug('Success regenerate: %s' % self.path)
                return self.check()
            except Exception as e:
                logging.debug('Fail regenerate: %s, %s' % (self.path, e))
                return False
        else:
            return False


def main():
    dm = DepManager()
    dm.addDeps([
        Internal('config', is_folder=True),
        Internal('fake.dll', optional=True),
        Internal('config/icons', is_folder=True),
        Internal('config/contrib', is_folder=True),
        External('unrar.exe', os.path.join(os.environ['SYSTEMROOT'], 'unrar.exe')),
        External('7z.exe', os.path.join(os.environ['SYSTEMROOT'], '7z.exe')),
        External('7z.dll', os.path.join(os.environ['SYSTEMROOT'], '7z.dll')),
        External('fake.dll', os.path.join(os.environ['SYSTEMROOT'], 'fake.dll')),
    ])
    if not dm.ok:
        print('Total:')
        for d in dm.invalid:
            print(d.info)
        print('Critical:')
        for d in dm.critical:
            print(d.info)


if __name__ == '__main__':
    main()