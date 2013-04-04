import hashlib
import struct
from tempfile import NamedTemporaryFile
from Crypto.Cipher import AES

__author__ = 'a.nabrodov'

import os
temp_folder = 'config/temp/'
if not os.path.isdir(temp_folder):
    os.mkdir(temp_folder)


class ESMFile(file):
    def __init__(self, filename):
        self.filename = filename
        file.__init__(self, filename, 'rb')
        self.esm_info = {}
        offset = 0x00
        self.seek(offset)
        if self.read(4) != 'TES4':
            raise Exception('Not a esm file.')
            return
        offset += 4
        offset += 20  # skip unknown bites

        self.seek(offset)
        if self.read(4) != 'HEDR':
            raise Exception('File seems corrupted: cant read header')

        offset += 4
        offset += 14  # skip unknown bites

        ret = self.readString(offset)  # CNAM
        offset += len(ret)

        ret = self.readString(offset)  # developer
        self.esm_info['developer'] = ret[:-1].strip()
        offset += len(ret)

        ret = self.readString(offset)  # SNAM
        offset += len(ret)

        ret = self.readString(offset)  # description
        self.esm_info['description'] = ret[:-1].strip()
        offset += len(ret)

        ret = self.readString(offset)  # MAST
        offset += len(ret)

        ret = self.readString(offset)  # master
        self.esm_info['master'] = ret[:-1]
        offset += len(ret)

        self.offset = offset

        self.close()  # bad

        # print(self.esm_info)

    def readString(self, offset):
        string = ''
        b = self.read(1)
        while b != '\0':
            self.seek(offset)
            b = self.read(1)
            string += b
            offset += 1
        return string


class CryptedESMFile(ESMFile):
    def __init__(self, filename, key):
        self.key = hashlib.sha256(key).digest()

        with file(filename, 'rb') as orig:
            origsize = struct.unpack('<Q', orig.read(struct.calcsize('Q')))[0]
            iv = orig.read(16)
            self.decryptor = AES.new(self.key, AES.MODE_CBC, iv)

            first_chunk = orig.read(512)
            with NamedTemporaryFile('wb', delete=False) as header:
                header.write(self.decryptor.decrypt(first_chunk))
                fn = header.name

        ESMFile.__init__(self, fn)
        os.unlink(fn)


def main():
    ESMFile('SkyWind.esm')
    ESMFile('Skywind_open_056.esm')
    from secret import key

    CryptedESMFile('Skywind.cmf', key)


if __name__ == '__main__':
    main()