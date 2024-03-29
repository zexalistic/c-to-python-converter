"""
    @usage: Conversion result of API
"""
import os
from output.structure_class import *

APILib = CDLL(os.path.join(os.getcwd(), "Sample.dll"))


def hello_world(something):
    """
    :param something: member from enumerate class MY_BOOL
    """
    func = APILib["hello_world"]
    func.argtypes = [c_int]
    func.restype = c_int
    ret = func(something)
    return ret


def hello_world_3():
    """
    """
    func = APILib["hello_world_3"]
    func.argtypes = []
    func.restype = c_int
    ret = func()
    return ret


