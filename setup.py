from distutils.core import setup
import py2exe
from resources import ResourceFile

UNRAR = open('unrar.exe', 'rb').read()
MSVCP90 = open('C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll', 'rb').read()

setup(
    windows=[
        {
            "script": "Skywind.py",
            # "icon_resources": [(0, "app.ico")],
            'other_resources': [
                # (u"UNRAR", 1, ResourceFile('unrar.exe', UNRAR).get_buffer()),
                # (u'MSVCP90', 2, ResourceFile('MSVCP90.dll', MSVCP90).get_buffer())
            ],
        }
    ],
    options={"py2exe": {
        "includes": ["sip", "logging", "subprocess", 'json', 'yaml', 'rarfile', '_winreg', 'win32com', 'Crypto'],
        'packages': ['checker', 'config', 'installer', 'resources', 'secret'],
        "compressed": 1,
        "optimize": 2,
        'bundle_files': 1}
    },
    data_files=[
        ('.', ['unrar.exe', 'C:\\Dropbox\\developers\\interpreters\\Python2\\DLLs\\MSVCP90.dll']),
        ('.', ['currentVersion.yml']),
        ('icons', ['icons/app.png', 'icons/Morrowind.png', 'icons/Skyrim.png', 'icons/Skywind.png']),
        ('contrib', ['contrib/vcredist_x86_2008.exe', 'contrib/vcredist_x86_2005.exe'])
    ],
    zipfile=None, requires=['Crypto', 'requests'],
)
