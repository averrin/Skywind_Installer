#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import tempfile
import requests
from config import Config
import logging


class ConfigManager(object):          #TODO: add remote update config feature
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

    def addConfig(self, name, filepath, optional=False):
        try:
            self.configs[name] = Config(open(filepath))
        except Exception as e:
            logging.debug('Cant add config: %s (%s)' % (name, e))
            self.invalid.append((filepath, optional))

    @property
    def critical(self):
        return filter(lambda x: not x[1], self.invalid)

    def check(self):
        if self.invalid:
            return False or self.ignore_optional
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