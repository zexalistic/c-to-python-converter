from ctypes import *


class DEV(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, c_void_p))]


class _MY_STRUCT(Structure):
    _fields_ = [("a", c_int * 128),
                ("b", c_int),
                ("c", POINTER(c_int))]


class MY_STRUCT(Structure):
    _fields_ = [("a", c_int * 128),
                ("b", c_int),
                ("c", POINTER(c_int))]


