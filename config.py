#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import yaml
import json
import re
from collections import OrderedDict

class Mapping(OrderedDict):
    def __unicode__(self):
        return super().__unicode__()

    def __getattribute__(self, key):
        try:
            attr = super(OrderedDict, self).__getitem__(key)
        except KeyError:
            attr = super(OrderedDict, self).__getattribute__(key)
        return attr
#
#    def __getitem__(self, key):
#        attr = super().__getitem__(key)
#        r = Mapping._convert(attr)
#        if r != attr:
#            super().__setitem__(key, r)
#        return r
#
#    def __setattr__(self, key, value):
#        super(OrderedDict, self).__setitem__(key, value)

    @classmethod
    def _convert(cls, attr):
        tf = {'TRUE': True, 'FALSE': False}
        if isinstance(attr, str) and attr.upper() in tf:
            return tf[str(attr).upper()]
        elif isinstance(attr, dict):
            m = Mapping()
            m.update(attr)
            m._total_convert()
            attr = m
        elif attr in [b'True', b'False']:
            attr = eval(attr)
        elif isinstance(attr, bytes):
            attr = attr.decode('utf8')
            
        if isinstance(attr, str):
            try:
                if attr.startswith('[') and attr.endswith(']') and type(eval(attr)) == list:
                    attr = eval(attr)
            except SyntaxError:
                pass

        return attr

    def _total_convert(self):
        for attr in self:
            r = self[attr]
            self[attr] = Mapping._convert(r)


def mapping_representer(dumper, data):
    return dumper.represent_mapping('!mapping', data)

yaml.add_representer(Mapping, mapping_representer)

def mapping_constructor(loader, tag, node):
    value = loader.construct_mapping(node)
    m = Mapping(sorted(value.items()))
#    m.update(value)
    return m

yaml.add_multi_constructor('!mapping', mapping_constructor)

class Config(object):
    def __init__(self, cfg_file):
        cfg = cfg_file.read()
        cfg = yaml.load(cfg)
        self._dict = cfg

    def __getattr__(self, key):
        try:
            return self._dict.__getattribute__(key)
        except AttributeError:
            attr = self._dict[key]
            if isinstance(attr, dict):
                    m = Mapping()
                    m.update(attr)
                    m._total_convert()
                    attr = m
                    self._dict[key] = attr
            return attr

    def __getitem__(self, key):
        attr = self._dict[key]
        if isinstance(attr, dict):
            m = Mapping()
            m.update(attr)
            m._total_convert()
            attr = m
        return attr

    def save(self, cfg_file):
        for attr in self._dict:
            r = self._dict[attr]
            if isinstance(r, dict):
                m = Mapping()
                m.update(r)
                r = m
            if isinstance(r, Mapping):
                r._total_convert()
            self._dict[attr] = r
        dump = yaml.dump(self._dict, default_flow_style=False, indent=4, allow_unicode=True, encoding="utf-8")
        cfg_file.write(dump.decode('utf8'))


def main():
    cfg = Config(open('../Apps/Orlangur/config/main.cfg'))
#    print(cfg.options)
    cfg.save(open('../Apps/Orlangur/config/main.cfg', 'w'))

if __name__ == '__main__':
    main()
