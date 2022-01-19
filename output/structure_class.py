from ctypes import *


class DEV(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, c_int))]


class DEV2(Structure):
    _fields_ = [("func_p", CFUNCTYPE(c_int, c_int, c_int))]


class MY_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


class YOUR_UNION(Union):
    _fields_ = [("a", c_int),
                ("b", c_char),
                ("c", c_double)]


