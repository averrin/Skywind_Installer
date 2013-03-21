from distutils.core import setup
import py2exe

setup(windows=[
    {"script": "Skywind.py"}],
      options={"py2exe": {
          "includes": ["sip", "logging", "subprocess", 'json', 'yaml', 'rarfile', '_winreg', 'win32com'],
          'packages': ['checker', 'config'],
          "compressed": 1,
          "optimize": 2,
          'bundle_files': 1
      }
      },
      data_files=[('.', ['C:\Dropbox\developers\interpreters\Python2\DLLs\MSVCP90.dll']),
                  ('.', ['unrar.exe', 'currentVersion.yml']),
                  ('icons', ['icons/app.png', 'icons/Morrowind.png', 'icons/Skyrim.png', 'icons/Skywind.png']),
                  ('contrib', ['contrib/vcredist_x86_2008.exe', 'contrib/vcredist_x86_2005.exe'])
                  ])
