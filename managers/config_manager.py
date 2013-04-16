#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import tempfile
import requests
from utils.config import Config
import logging


class ConfigManager(object):
    #TODO: add remote update config feature

    optional = False
    configs = {}
    invalid = []

    def __init__(self, ignore_optional=False):
        self.ignore_optional = ignore_optional

    def addConfigs(self, configs):
        raise NotImplemented

    def addRemoteConfig(self, name, url, optional=False):
        cfg = requests.get(url).text
        f = tempfile.NamedTemporaryFile(delete=False)
        with f:
            f.write(cfg)
        self.addConfig(name, f.name, optional)

    def addConfig(self, name, file_path, optional=False):
        try:
            self.configs[name] = Config(open(file_path))
        except Exception as e:
            logging.debug('Cant add config: %s (%s)' % (name, e))
            self.invalid.append((file_path, optional))
            raise e

    def reloadConfig(self, name):
        self.addConfig(name, self[name].filename)

    def saveConfig(self, name):
        self[name].save(open(self[name].filename, 'w'))

    @property
    def critical(self):
        return filter(lambda x: not x[1], self.invalid)

    def check(self):
        if self.invalid:
            if self.ignore_optional:
                if self.critical:
                    return False
                else:
                    return True
            else:
                return False
        else:
            return True

    def regenerate(self):
        """
            Only for DepManager
        """
        return False

    @property
    def info(self):
        if self.ignore_optional:
            return '\n'.join(["%s is missed or corrupted" % config[0] for config in self.critical])
        else:
            return '\n'.join(["%s is missed or corrupted" % config[0] for config in self.invalid])

    def __getitem__(self, item):
        return self.configs[item]