#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import logging

__author__ = 'Alexey "Averrin" Nabrodov'
__version__ = '0.0.3'

try:
    import winreg
except ImportError:
    import _winreg as winreg
import platform
import hashlib
from win32com.client import Dispatch
import logging

arch = platform.machine()

REG_KEYS = {'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE, 'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER,
            'HKLM': winreg.HKEY_LOCAL_MACHINE, 'HKCU': winreg.HKEY_CURRENT_USER, }

STEAM_ID = {'Morrowind': 22320, 'Skyrim': 72850, 'Oblivion': 22330}

if arch == 'AMD64':
    wow = 'Wow6432Node\\'
else:
    wow = ''

app_path = 'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\morrowind.exe'
path = {
    'Morrowind': 'HKEY_LOCAL_MACHINE\\SOFTWARE\\%sBethesda Softworks\\Morrowind',
    'Skyrim': 'HKEY_LOCAL_MACHINE\\SOFTWARE\\%sBethesda Softworks\\Skyrim',
    'Oblivion': 'HKEY_LOCAL_MACHINE\\SOFTWARE\\%sBethesda Softworks\\Oblivion'}
uninstall_steam = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\%%sMicrosoft\\Windows\\CurrentVersion\\Uninstall\\Steam App %s' % STEAM_ID
steam_path = 'HKEY_CURRENT_USER\\Software\\Valve\\Steam'
steam_postfix = '\\Apps\\%s'
data_folder = {'Morrowind': u'Data Files', 'Skyrim': u'Data', 'Oblivion': u'Data'}

versions = {
    '38268efe176de02193ed8b5babb20d6231f1324113c65b7fc5308e51d4fde5d3': {
        'version': '1.2.0.722',
        'desc': 'Russian 1C. No addons'
    },
    '26cc5aa36ebf07e38cea398c21759e3100f57f6336738dd00387ab220fad7663': {
        'version': '1.3.0.1029',
        'desc': 'Russian 1C. With Tribunal'
    },
    '14e5eb34b249358a48eb0d8c8be8504e66e32bed945fd0298bf9128757e9932c': {
        'version': '1.4.0.1313',
        'desc': 'Russian 1C. With Tribunal. Patched'
    },
    '496faca0b8e683431cbe0f0b5462cfc32c45e8af24c0ba5fff3d392cbc869cae': {
        'version': '1.6.0.1820',
        'desc': 'Steam GOTY. MGSO installed'
    },
    'eac72e1b3524ee0012d080d3c2e2e00e401464e41ee54f9afd6aaaadf2c221f5': {
        'version': '1.6.0.1820',
        'desc': 'Steam GOTY'
    },
    'ecb347304134f63cabf1ab38f0728dcff5fbfb11e7ac2b87a03c8639936ab094': {
        'version': '1.6.0.1820',
        'desc': 'Russian 1C. With Bloodmoon (+Tribunal)'
    },
}

blacklist = {'a0dfd7343dc40d8c61da6178912ff1988086f9d32695fe44dc3522662d90e2ce': {'version': '1.6.0.1820',
                                                                                  'desc': 'http://xtes.ru/index.php?name=downloads&op=full&file=7'},
             '2899d97d6430d68d08bb28cde663c82962c273e0991541f067074b8d399945f7': {'version': '1.6.0.1820',
                                                                                  'desc': 'http://nodvd.net/912-the-elder-scrolls-iii-morrowind-v16-ru-nodvd.html'}}

for p in path:
    path[p] = path[p] % wow
# uninstall = uninstall_steam % wow

def check_steam(game):
    logging.info('Checking steam for %s' % game)
    try:
        installed = int(get_reg_value(get_reg_key(steam_path + steam_postfix % STEAM_ID[game]), 'Installed'))
        if installed:
            return True
        else:
            return False
    except:
        return False


def get_reg_key(key):
    if key.split('\\')[0] in REG_KEYS:
        parent = REG_KEYS[key.split('\\')[0]]
        key = '\\'.join(key.split('\\')[1:])
    else:
        raise Exception('Wrong key format')

    k = winreg.OpenKey(parent, key)
    logging.info("Looking for %s" % key)
    return k


def enum_reg_values(key):
    print(key)

    key = get_reg_key(key)

    try:
        i = 0
        while 1:
            name, value, reg_type = winreg.EnumValue(key, i)
            print('\t', repr(name), get_reg_value(key, name))
            i += 1
    except WindowsError:
        pass


def get_reg_value(key, subkey):
    logging.info('Reading reg key %s\\%s' % (key, subkey))
    result = winreg.QueryValueEx(key, subkey)[0]
    logging.debug('\t %s' % result)
    return result


def exe_info(path):
    logging.info('Get exe info for %s' % path)
    m = hashlib.sha256(open(path, 'rb').read())

    ver_parser = Dispatch('Scripting.FileSystemObject')
    version = ver_parser.GetFileVersion(path)
    hash = m.hexdigest()

    if hash in blacklist:
        reason = 'Morrowind.exe was cracked'
        return False, reason
    else:
        info = (hash, version, versions[hash]['desc'] if hash in versions else 'Unknown exe')
        logging.debug('\t %s' % str(info))
        return info, None


def get_path(game, is_steam=False):
    if is_steam:
        steam_dir = get_reg_value(get_reg_key(steam_path), 'SteamPath')
        logging.info('Steam folder: "%s"' % steam_dir)
        try:
            return os.path.normpath(os.path.join(steam_dir, 'SteamApps\\common\\%s' % game))
        except WindowsError:
            return 'Cant find %s installation' % game
    else:
        try:
            return os.path.normpath(get_reg_value(get_reg_key(path[game]), 'Installed Path'))
        except WindowsError:
            return 'Cant find %s installation' % game


def check_valid_folder(game, game_dir):
    reason = None

    data_dir = os.path.join(game_dir, data_folder[game])
    if os.path.isdir(data_dir):
        if game == 'Morrowind':
            required = ['Morrowind.bsa', 'Morrowind.esm']
            ok = True
            for f in required:
                if not os.path.isfile(os.path.join(data_dir, f)):
                    ok = False
                    reason = 'No required Morrowind files'
                    break
            if ok:
                required_addons = ['Bloodmoon.bsa', 'Bloodmoon.esm', 'Tribunal.bsa', 'Tribunal.esm']
                for f in required_addons:
                    if not os.path.isfile(os.path.join(data_dir, f)):
                        ok = False
                        reason = 'No required addons files'
                        break
            if ok:
                return True, reason
            else:
                return False, reason

        else:
            return True, reason
    else:
        reason = 'No data folder'

    return False, reason


def check_mod(mod, skyrim_path):
    data_dir = os.path.join(skyrim_path, data_folder['Skyrim'])
    if os.path.isfile(os.path.join(skyrim_path, data_dir, u'%s.esm' % mod)):
        # f = open(os.path.join(skyrim_path, data_dir, '%s.esm' % mod), 'rb')
        # f.seek(195)
        # version = f.read(3)
        # f.close()
        return '', True
    else:
        return 'No %s.esm found' % mod, False


def check_valid_exe(game, game_dir):
    logging.info('Checking installation of %s in %s' % (game, game_dir))
    if os.path.isdir(game_dir):
        if game == 'Morrowind':
            morrowind_exe = os.path.join(game_dir, u'Morrowind.exe')
            morrowind_original_exe = os.path.join(game_dir, u'Morrowind.Original.exe')

            if os.path.isfile(morrowind_original_exe):
                morrowind_exe = morrowind_original_exe

            if os.path.isfile(morrowind_exe):
                return exe_info(morrowind_exe)
            else:
                reason = 'No Morrowind.exe found'
                logging.debug('\t' + reason)
                return False, reason
        elif game == 'Skyrim':
            exe = os.path.join(game_dir, u'TESV.exe')
            if os.path.isfile(exe):
                return exe_info(exe)
            else:
                reason = 'Cant find TESV.exe'
                logging.debug('\t' + reason)
                return False, reason
        elif game == 'Oblivion':
            exe = os.path.join(game_dir, u'Oblivion.exe')
            if os.path.isfile(exe):
                return exe_info(exe)
            else:
                reason = 'Cant find Oblivion.exe'
                logging.debug('\t' + reason)
                return False, reason
    else:
        reason = 'Cant find %s installation.' % game
        logging.debug('\t' + reason)
        return False, reason


def main():
    print(check_steam('Morrowind'))
    print(check_steam('Skyrim'))


def _main():
    logging.info('Start')
    is_steam = check_steam('Morrowind')
    if is_steam:
        logging.info('Steam version detected')
        print('Steam version detected')
        morrowind_version = 'Steam'
    else:
        morrowind_version = 'Retail'

    try:
        morrowind_dir = get_path('Morrowind', morrowind_version)
        is_valid = check_valid_exe(morrowind_dir)
        if is_valid:
            logging.info('Morrowind version: %s [%s]' % is_valid[1:])
            print('Morrowind version: %s [%s]' % is_valid[1:])
        else:
            logging.info('Unknown Morrowind.exe file')
            print('Unknown Morrowind.exe file')
    except:
        logging.info('No Morrowind detected')
        print('No Morrowind detected')


if __name__ == '__main__':
    main()