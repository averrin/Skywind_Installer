from distutils.core import setup
import py2exe
import sys
sys.path.append('utils')
sys.path.append('ui')
# from resources import ResourceFile

# UNRAR = open('unrar.exe', 'rb').read()
# MSVCP90 = open('C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll', 'rb').read()

setup(
    windows=[
        {
            "script": "Launcher.py",
            # "icon_resources": [(0, "app.ico")],
            'other_resources': [
                # (u"UNRAR", 1, ResourceFile('unrar.exe', UNRAR).get_buffer()),
                # (u'MSVCP90', 2, ResourceFile('MSVCP90.dll', MSVCP90).get_buffer())
            ],
        }
    ],
    options={"py2exe": {
        "includes": [
            "sip", "logging", "subprocess", 'json', 'yaml',
            'rarfile', '_winreg', 'win32com', 'Crypto',
            'PyQt4.QtNetwork', 'requests', 'lxml._elementpath', 'distutils', 'pycurl', 'oauth2client',
        ],
        'packages': ['checker', 'config', 'installer', 'dm', 'secret', 'utils', 'ui'],
        'excludes': ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'pywin.debugger',
                     'pywin.debugger.dbgcon', 'pywin.dialogs', 'tcl',
                     'Tkconstants', 'Tkinter'],
        "compressed": 1,
        'dll_excludes': ["mswsock.dll", "powrprof.dll"],
        "optimize": 2,
        'bundle_files': 2
    }
    },
    data_files=[
        ('.', []),
        ('config', [
            'config/config.yml'
        ]),
        ('config/icons', [
            'config/icons/app.png',
            'config/icons/Morrowind.png',
            'config/icons/Oblivion.png',
            'config/icons/Skyrim.png',
            'config/icons/Skywind.png',
            'config/icons/Skyblivion.png',
            'config/icons/Skywind_icon.png',
            'config/icons/Skyblivion_icon.png',

            'config/icons/bug.png',
            'config/icons/readme.png',
            'config/icons/start.png',
            'config/icons/pause.png',

            'config/icons/add.png',
            'config/icons/remove.png',
        ]),
        ('config/contrib', [
            'config/contrib/vcredist_x86_2008.exe',
            'config/contrib/vcredist_x86_2005.exe',
            'config/contrib/unrar.exe',
            'config/contrib/7z.exe',
            'config/contrib/7z.dll',
            'C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll'
        ])
    ],
    # zipfile=None,
    requires=['requests', 'lxml', 'pycurl', 'oauth2client'],
)
