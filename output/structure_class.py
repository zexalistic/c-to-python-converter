from ctypes import *


class YOUR_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


class _MY_STRUCT(Structure):
    _fields_ = [("a", c_int * 128),
                ("b", c_long),
                ("c", POINTER(c_int))]


class MY_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


class DEV2(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, POINTER(_MY_STRUCT)))]


class DEV(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, POINTER(_MY_STRUCT)))]


