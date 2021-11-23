from ctypes import *


class DEV(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, MY_STRUCT_PTR))]


class DEV2(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, MY_STRUCT_PTR))]


class MY_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


class _MY_STRUCT(Structure):
    _fields_ = [("a", c_int * 128),
                ("b", c_long),
                ("c", POINTER(c_int))]


class MY_STRUCT(Structure):
    _fields_ = [("a", c_int * 128),
                ("b", c_long),
                ("c", POINTER(c_int))]


class YOUR_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


