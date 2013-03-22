from ctypes import *


def GetModuleHandle(filename=None):
    h = windll.kernel32.GetModuleHandleW(filename)
    if not h:
        raise WinError()
    return h


def FindResource(typersc, idrsc, c_restype=c_char, filename=None):
    if type(idrsc) is int:
        idrsc = u'#%d' % idrsc
    if type(typersc) is int:
        typersc = u'#%d' % typersc
    hmod = GetModuleHandle(filename)
    hrsc = windll.kernel32.FindResourceW(hmod, typersc, idrsc)
    if not hrsc:
        raise WinError()
    hglobal = windll.kernel32.LoadResource(hmod, hrsc)
    if not hglobal:
        raise WinError()
    windll.kernel32.LockResource.restype = POINTER(c_restype)
    return windll.kernel32.LockResource(hglobal)[0]


class ResourceFile(Structure):
    _fields_ = [('name', c_char * 255), ('content', c_char * 1000000)]

    def get_buffer(self):
        return cast(pointer(self), POINTER(c_char * sizeof(self)))[0].raw
