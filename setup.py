from distutils.core import setup
import py2exe
# from resources import ResourceFile

# UNRAR = open('unrar.exe', 'rb').read()
# MSVCP90 = open('C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll', 'rb').read()

setup(
    windows=[
        {
            "script": "TransTES.py",
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
            'PyQt4.QtNetwork', 'requests', 'lxml._elementpath', 'distutils', 'pycurl'
        ],
        'packages': ['checker', 'config', 'installer', 'dm', 'secret', 'pycurl.pyd'],
        'excludes': ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email', 'pywin.debugger',
                     'pywin.debugger.dbgcon', 'pywin.dialogs', 'tcl',
                     'Tkconstants', 'Tkinter'],
        "compressed": 1,
        "optimize": 2,
        'bundle_files': 1}
    },
    data_files=[
        ('.', []),
        ('config', [
            'config/Skywind.yml'
        ]),
        ('config/icons', ['config/icons/app.png', 'config/icons/Morrowind.png', 'config/icons/Skyrim.png', 'config/icons/Skywind.png']),
        ('config/contrib', ['config/contrib/vcredist_x86_2008.exe', 'config/contrib/vcredist_x86_2005.exe',
                                'config/contrib/unrar.exe', 'C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll'])
    ],
    zipfile=None, requires=['requests'],
)
