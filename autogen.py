# automatically generate Cpython wrapper file according to header files
# Created by Yihao Liu on 2021/3/5

import glob
import os
import re
import logging
import time
import traceback
import json
import shutil
import copy


def rm_c_comments(lines):
    """
    remove C comments in the file to parse
    """
    m = re.compile(r'//.*')
    lines = re.sub(m, '', lines)
    m = re.compile(r'/\*.*?\*/', re.S)
    lines = re.sub(m, '', lines)

    return lines


class CommonParser:
    """
    Parent class for all parser
    """
    def __init__(self):
        self.h_files = list()                           # list of header files
        self.c_files = list()                           # list of C files to parse

        self.struct_pointer_dict = dict()               # key = name of struct pointer, value = name of struct
        self.macro_dict = dict()                        # key = name of macro, value = value of macro
        self.struct_class_name_list = list()            # name list of structure class
        self.enum_class_name_list = list()
        self.exception_list = list()                    # list of keys in exception dict
        self.struct_class_list = list()                 # list of structure


        # Read from json
        with open('config.json', 'r') as fp:
            self.env = json.load(fp)
        self.basic_type_dict = self.env.get('basic_type_dict', dict())
        self.exception_dict = self.env.get('exception_dict', dict())
        self.func_pointer_dict = self.env.get('func_pointer_dict', dict())

    class _Param:
        """
        A class recording the information of the parameter of a C function
        """
        def __init__(self, param_info=(None, None, None)):      # param_info sample: IN MZD_U8 Var_name
            self.arg_pointer_flag = False
            arg_info = list()
            for info in param_info:
                if info and ('*' in info or '[' in info):
                    self.arg_pointer_flag = True
                    info = re.sub(r'[\[\]*]', '', info)
                arg_info.append(info)

            self.arg_inout = arg_info[0]                 # IN/ OUT
            self.arg_type = arg_info[1].strip()
            self.arg_name = arg_info[2]

    def convert_to_ctypes(self, arg_type, arg_ptr_flag):
        """
        Convert customized variable type to ctype according to the type dict
        """
        if self.exception_dict.get(arg_type, 0):
            arg_type = self.exception_dict[arg_type]
        elif self.basic_type_dict.get(arg_type, 0):
            arg_type = self.basic_type_dict[arg_type]
        elif arg_type in self.enum_class_name_list:
            pass
        elif arg_type in self.struct_class_name_list:
            pass
        elif self.struct_pointer_dict.get(arg_type, 0):
            arg_type = self.struct_pointer_dict[arg_type]
            arg_ptr_flag = True
        elif self.func_pointer_dict.get(arg_type, 0):
            arg_type = f'CFUNCTYPE({self.func_pointer_dict[arg_type]})'
            arg_ptr_flag = True
        else:
            logging.warning(f'Unrecognized type! Type name: {arg_type}')
        return arg_type, arg_ptr_flag


class StructUnionParser(CommonParser):
    """
    Parse the header files in the folder. Get the structure and Unions
    """
    def __init__(self):
        super().__init__()

    class _Struct:
        """
        A class recording the name, member and type of a structure/union
        """
        def __init__(self):
            self.struct_name = None                         # string
            self.struct_members = list()                    # list of string
            self.struct_types = list()                      # list of string/ctypes
            self.pointer_flags = list()                     # list of bool
            self.member_idc = list()                        # list of integer
            self.isUnion = False                            # structure = False, Union = True

        def __getitem__(self, item):
            return self.struct_members[item], self.struct_types[item], self.struct_types[item], self.member_idc[item]

    def generate_struct_union_class_list(self):
        # parse header files
        for h_file in self.h_files:
            with open(h_file, 'r') as fp:
                lines = fp.read()
                lines = rm_c_comments(lines)
                structs = re.findall(r'typedef struct ([\s\w]+)\{([^{}]+)\}([\s\w,*]+);\s', lines)             # match: typedef struct _a{}a, *ap;
                struct_flags = [False] * len(structs)
                unions = re.findall(r'typedef union ([\s\w]+)\{([^{}]+)\}([\s\w,*]+);\s', lines)             # match: typedef struct _a{}a, *ap;
                union_flags = [True] * len(unions)
                contents = structs + unions
                flags = struct_flags + union_flags
                for content, flag in zip(contents, flags):
                    struct = self._Struct()
                    struct.isUnion = flag
                    struct_name = re.sub(r'\s', '', content[2])
                    if re.search(r',\s*\*', struct_name):
                        struct_name, struct_pointer_name = re.search(r'(\w+),\s*\*(\w+)', struct_name).groups()
                        self.struct_pointer_dict[struct_pointer_name] = struct_name
                    struct.struct_name = struct_name
                    struct_infos = content[1].split(';')
                    for struct_info in struct_infos:
                        struct_info = struct_info.strip()                                                  # This is necessary
                        tmp = re.findall(r'([\[\]*\w\s]+)\s+([^;}]+)', struct_info)                        # parse the members of structure
                        if tmp:        # filter the empty list
                            member_type = tmp[0][0]
                            member_name = tmp[0][1]
                            member_type = member_type.strip()
                            member_name = member_name.strip()
                            # find the pointer, this part only support 1st order pointer
                            if member_type.endswith('*'):
                                struct.struct_types.append(member_type[:-1])
                                struct.struct_members.append(member_name)
                                struct.pointer_flags.append(True)
                            elif member_name.endswith('[]'):
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name[:-2])
                                struct.pointer_flags.append(True)
                            elif member_name.startswith('*'):
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name[1:])
                                struct.pointer_flags.append(True)
                            else:
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name)
                                struct.pointer_flags.append(False)
                    self.struct_class_list.append(struct)
                    self.struct_class_name_list.append(struct.struct_name)

                structs = re.findall(r'struct\s*([\w]+)\s*\{([^}]+)?\}\s*;', lines)  # match: struct _a{};
                struct_flags = [False] * len(structs)
                unions = re.findall(r'union\s*([\w]+)\s*\{([^}]+)?\}\s*;', lines)  # match: struct _a{};
                union_flags = [True] * len(unions)
                contents = structs + unions
                flags = struct_flags + union_flags
                for content, flag in zip(contents, flags):
                    struct = self._Struct()
                    struct.isUnion = flag
                    struct_name = re.sub(r'\s', '', content[0])
                    struct.struct_name = struct_name
                    struct_infos = content[1].split(';')
                    for struct_info in struct_infos:
                        struct_info = struct_info.strip()  # This is necessary
                        tmp = re.findall(r'([\[\]*\w\s]+)\s+([^;}]+)', struct_info)  # parse the members of structure
                        if tmp:  # filter the empty list
                            member_type = tmp[0][0]
                            member_name = tmp[0][1]
                            member_type = member_type.strip()
                            member_name = member_name.strip()
                            # find the pointer, this part only support 1st order pointer
                            if member_type.endswith('*'):
                                struct.struct_types.append(member_type[:-1])
                                struct.struct_members.append(member_name)
                                struct.pointer_flags.append(True)
                            elif member_name.endswith('[]'):
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name[:-2])
                                struct.pointer_flags.append(True)
                            elif member_name.startswith('*'):
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name[1:])
                                struct.pointer_flags.append(True)
                            else:
                                struct.struct_types.append(member_type)
                                struct.struct_members.append(member_name)
                                struct.pointer_flags.append(False)
                    self.struct_class_list.append(struct)
                    self.struct_class_name_list.append(struct.struct_name)

                    # find if there is any "typedef struct _struct_var struct_var;" or "typedef _struct_var* struct_var_ptr"; if so, add them to list
                    struct_ptr = re.findall(r'typedef {}\s*\*\s*(\w+);'.format(struct.struct_name), lines)
                    if struct_ptr:
                        self.struct_pointer_dict[struct_ptr[0]] = struct.struct_name
                    alias = re.findall(r'typedef struct {} (\w+);'.format(struct.struct_name), lines)
                    if alias:
                        struct_alias = copy.deepcopy(struct)
                        struct_alias.struct_name = alias[0]
                        self.struct_class_list.append(struct_alias)
                        self.struct_class_name_list.append(alias[0])

                        # find if there's any structure pointer
                        struct_ptr = re.findall(r'typedef {}\s*\*\s*(\w+);'.format(alias[0]), lines)
                        if struct_ptr:
                            self.struct_pointer_dict[struct_ptr[0]] = alias[0]

    def convert_structure_class_to_ctype(self):
        """
        Convert customized type to ctypes here; convert C array to legal python ctypes here.

        Since the member type of some structure is another class member, the order of definition of class has to be arranged so that structure_class.py
        can be imported as a python module.
        Therefore, I create an algorithm to set an index indicating the order in struct_class_list.

        Algorithm: Let B should be defined after A and C, the original order is ABC. To begin with, I set the order index as 1,2,3. Then, when I check B, I set
        the order index B as index(A) + index(C) + index(B). Then, index(B) will always be larger than A and C. Finally, by sorting order index with structure_class,
        I can get the correct order.
        """
        order_idx = [f'{i}' for i in range(len(self.struct_class_list))]
        updated_struct_list = list()

        # convert struct_type to ctype
        for i, struct in enumerate(self.struct_class_list):
            updated_struct_members = list()
            updated_struct_types = list()
            for member, struct_type, pointer_flag in zip(struct.struct_members, struct.struct_types, struct.pointer_flags):
                idx = 0
                # check if member is array
                if '][' in member:    # high order array
                    expressions = re.findall(r'\[([\w\s*/+\-()]+)?\]', member)
                    idx = 1
                    member = re.search(r'(\w+)\[.*\]', member).group(1)
                    for expr in expressions:
                        items = re.findall(r'\w+', expr)
                        for item in items:
                            if self.macro_dict.get(item, 0):
                                # may have bug here.. Do not consider the condition that macro_1 is part of macro_2
                                expr = re.sub(item, self.macro_dict[item], expr)
                        try:
                            idx = idx * int(eval(expr))
                        except Exception:
                            traceback.print_exc()
                            logging.error(f'Unrecognized macro: {expr}.. {struct.struct_name}')

                elif '[' in member:  # 1 order array
                    if re.search(r'\w+\[([\s*/\-+\d()]+)\]', member):  # support +-/*
                        member, idx = re.search(r'(\w+)\[([\s*/\-+\d()]+)\]', member).groups()
                    elif re.search(r'\w+\[([\s*/\-+\d\w]+)\]', member):  # There is a macro within array index
                        member, idx = re.search(r'(\w+)\[([\s*/\-+\d()\w]+)\]', member).groups()
                        items = re.findall(r'\w+', idx)
                        for item in items:
                            if self.macro_dict.get(item, 0):
                                # may have bug here.. Do not consider the condition that macro_1 is part of macro_2
                                idx = re.sub(item, self.macro_dict[item], idx)
                    try:
                        idx = int(eval(idx))
                    except Exception:
                        traceback.print_exc()
                        logging.error(f'Unrecognized macro: {idx}... {struct.struct_name}')

                if struct.struct_name not in self.exception_list:
                    struct_type, pointer_flag = self.convert_to_ctypes(struct_type, pointer_flag)

                if struct_type in self.struct_class_name_list:
                    tmp = self.struct_class_name_list.index(struct_type)
                    order_idx[i] += f' + eval(order_idx[{tmp}])'
                if struct_type in self.enum_class_name_list:
                    struct_type = 'c_int'

                struct.member_idc.append(idx)
                updated_struct_members.append(member)
                updated_struct_types.append(struct_type)
            struct.struct_types = updated_struct_types
            struct.struct_members = updated_struct_members
            updated_struct_list.append(struct)

        # Sort the structure class
        order_idc = list()
        for idx in order_idx:
            idx = eval(idx)
            order_idc.append(idx)
        tmp = list(zip(order_idc, updated_struct_list))
        result = sorted(tmp, key=lambda x: x[0])
        self.struct_class_list = [item[1] for item in result]

    def write_structure_class_into_py(self):
        """
        generate struct_class.py. Since device structure is complicated... I just write the device structure by myself
        """
        with open('structure_class.py', 'w') as fp:
            fp.write('from ctypes import *\n\n\n')
            for struct in self.struct_class_list:
                if struct.isUnion:
                    fp.write(f'class {struct.struct_name}(Union):\n    _fields_ = [')
                    info_list = []
                    for member, struct_type, pointer_flag, idx in zip(struct.struct_members, struct.struct_types, struct.pointer_flags, struct.member_idc):
                        # check void
                        if pointer_flag:
                            struct_type = f'POINTER({struct_type})'
                        if idx:
                            info = '("' + f'{member}' + '", ' + f'{struct_type} * {idx}' + ')'
                        else:
                            info = '("' + f'{member}' + '", ' + f'{struct_type}' + ')'
                        info_list.append(info)
                    info_list = ',\n                '.join(info_list)
                    fp.write(f'{info_list}]\n\n\n')
                else:
                    fp.write(f'class {struct.struct_name}(Structure):\n    _fields_ = [')
                    info_list = []
                    for member, struct_type, pointer_flag, idx in zip(struct.struct_members, struct.struct_types, struct.pointer_flags, struct.member_idc):
                        # check void
                        if pointer_flag:
                            struct_type = f'POINTER({struct_type})'
                        if idx:
                            info = '("' + f'{member}' + '", ' + f'{struct_type} * {idx}' + ')'
                        else:
                            info = '("' + f'{member}' + '", ' + f'{struct_type}' + ')'
                        info_list.append(info)
                    info_list = ',\n                '.join(info_list)
                    fp.write(f'{info_list}]\n\n\n')


class EnumParser(CommonParser):
    """
    Parse the header files in the folder. Catch the enum types and sort them into enum_class.py
    """
    def __init__(self):
        super().__init__()
        self.enum_class_list = list()

    class _Enum:
        """
        A class recording the name, members, values of a enumerate type
        """
        def __init__(self):
            self.enum_name = None
            self.enum_members = list()
            self.enum_values = list()

        def __getitem__(self, item):
            return self.enum_members[item], self.enum_values[item]

    def generate_enum_class_list(self):
        """
        generate enum_class.py
        """
        for h_file in self.h_files:
            with open(h_file) as fp:
                contents = fp.read()
                contents = rm_c_comments(contents)
                contents = re.findall(r'typedef enum[^;]+;', contents)  # find all enumerate types
                for content in contents:
                    enum = self._Enum()
                    tmp = re.split(r'[{}]', content)  # split the typedef enum{ *** } name;
                    enum_infos = re.sub(r'\s', '', tmp[1])
                    enum.enum_name = re.sub(r'[\s;]', '', tmp[2])
                    enum_infos = enum_infos.split(',')
                    enum_infos = list(filter(None, enum_infos))
                    for default_value, enum_info in enumerate(enum_infos):
                        if '=' in enum_info:
                            enum_member = enum_info.split('=')[0]
                            enum_value = enum_info.split('=')[1]
                            if enum_value.startswith('0x'):
                                enum_value = int(enum_value, 16)
                        else:
                            enum_member = enum_info
                            enum_value = default_value
                        enum.enum_members.append(enum_member)
                        enum.enum_values.append(enum_value)

                    self.enum_class_list.append(enum)
                    self.enum_class_name_list.append(enum.enum_name)

    def write_enum_class_into_py(self):
        with open('enum_class.py', 'w') as f:
            f.write('from enum import Enum, unique, IntEnum\n\n')
            for enum in self.enum_class_list:
                f.write(f'@unique\nclass {enum.enum_name}(IntEnum):\n')
                for member, value in enum:
                    f.write(f'    {member} = {value}\n')
                f.write('\n\n')


class FunctionParser(CommonParser):
    """
    Automatically parse the header files
    """
    def __init__(self):
        super().__init__()
        self.func_list = list()
        self.dll_name = 'APILib'                     # Name of CDLL
        self.wrapper = self.env.get('name_of_wrapper', 'FunctionLib.py')  # Name of Output wrapper
        self.dll_path = self.env.get('dll_path', 'samples.dll')
        self.testcase = self.env.get('name_of_testcase', 'Testcases_all.py')  # Output testcase
        self.func_header = self.env.get('func_header', False)
        self.func_param_decorator = self.env.get('func_param_decorator', False)
        self.is_multiple_file = self.env.get('is_multiple_file', False)

    class _Func:
        """
        A class recording the function name, type of return value and arguments
        """
        def __init__(self):
            self.func_name = None
            self.ret_type = None
            self.header_file = None
            self.parameters = list()

        def get_arg_names(self):
            ret = list()
            for param in self.parameters:
                if param.arg_pointer_flag:
                    ret.append(param.arg_name + '_p')
                else:
                    ret.append(param.arg_name)
            return ', '.join(ret)

    def generate_func_list_from_h_files(self):
        """
        parse all the header files in the target folder;
        get all the functions to be wrapped.
        save those function information(name, argument type, return type) in func_list
        """
        for h_file in self.h_files:
            with open(h_file) as fp:
                contents = fp.read()
                contents = rm_c_comments(contents)
                # This pattern matching rule may have bugs in other cases
                if self.func_header:
                    contents = re.findall(r'{} ([*\w]+)\s+([\w]+)([^;]+);'.format(self.func_header), contents)       # find all functions
                else:
                    contents = re.findall(r'([*\w]+)\s+([\w]+)([^;]+);', contents)  # find all functions
                # For each function
                for content in contents:
                    func = self._Func()
                    ret_type = content[0]
                    func.ret_type, ret_ptr_flag = self.convert_to_ctypes(ret_type, False)           # Ignore the case that return value is a pointer
                    if func.ret_type in self.enum_class_name_list:
                        func.ret_type = 'c_int'
                    func.func_name = content[1]
                    param_infos = re.sub(r'[\n()]', '', content[2])                          # remove () and \n in parameters
                    param_infos = param_infos.split(',')
                    for param_info in param_infos:
                        if self.func_param_decorator:
                            param_info = re.search(r'({})\s+([*\w\s]+)\s+([\[\]*\w]+)'.format(self.func_param_decorator), param_info).groups()
                        else:
                            param_info = re.search(r'([*\w\s]+)\s+([\[\]*\w]+)', param_info).groups()
                            param_info = (None, *param_info)
                        param = self._Param(param_info=param_info)
                        param.arg_type, param.arg_pointer_flag = self.convert_to_ctypes(param.arg_type, param.arg_pointer_flag)
                        func.parameters.append(param)
                    func.header_file = os.path.basename(h_file)[:-2]
                    self.func_list.append(func)

    def generate_func_list_from_c_files(self):
        for c_file in self.c_files:
            with open(c_file) as fp:
                contents = fp.read()
                contents = rm_c_comments(contents)
                # This pattern matching rule may have bugs in other cases
                contents = re.findall(r'([*\w]+) ([\w]+)\s*\(([^;)]+)\)?\s*\{', contents)  # find all functions
                for content in contents:
                    if content[0] == 'else':           # remove else if clause
                        continue
                    func = self._Func()
                    ret_type = content[0]
                    func.ret_type, ret_ptr_flag = self.convert_to_ctypes(ret_type, False)           # Ignore the case that return value is a pointer
                    if func.ret_type in self.enum_class_name_list:
                        func.ret_type = 'c_int'
                    func.func_name = content[1]
                    param_infos = re.sub(r'[\n()]', '', content[2])                          # remove () and \n in parameters
                    param_infos = param_infos.split(',')
                    for param_info in param_infos:
                        param_info = re.search(r'({})\s+([*\w\s]+)\s+([\[\]*\w]+)'.format(self.func_param_decorator), param_info).groups()
                        param = self._Param(param_info=param_info)
                        param.arg_type, param.arg_pointer_flag = self.convert_to_ctypes(param.arg_type, param.arg_pointer_flag)
                        func.parameters.append(param)
                    func.header_file = os.path.basename(c_file)[:-2]
                    self.func_list.append(func)

    def write_funcs_to_wrapper(self):
        wrapper_name = self.wrapper
        if self.is_multiple_file:
            try:
                os.mkdir('FunctionLib')
            except FileExistsError:
                logging.warning('Already exist FunctionLib// ... Now cleaning and rewrite the folder')
                shutil.rmtree('FunctionLib')
                os.mkdir('FunctionLib')
        else:
            with open(self.wrapper, 'w') as fp:
                fp.write('from structure_class import *\n\n')
                fp.write(f'{self.dll_name} = CDLL("{self.dll_path}")\n\n')

        for func in self.func_list:
            if self.is_multiple_file:
                self.wrapper = os.path.join('FunctionLib', func.header_file + '_' + wrapper_name)
                if not os.path.exists(self.wrapper):
                    with open(self.wrapper, 'w') as fp:
                        fp.write('from structure_class import *\n\n')
                        fp.write(f'{self.dll_name} = CDLL("{self.dll_path}")\n\n')

            with open(self.wrapper, 'a') as fp:
                arg_names = func.get_arg_names()
                fp.write(f'def {func.func_name}({arg_names}):\n')

                # Comment of this function
                fp.write('    """\n')
                arg_types = list()
                for param in func.parameters:
                    arg_type = param.arg_type
                    arg_name = param.arg_name
                    if arg_type in self.enum_class_name_list:                   # convert customized varibale type to C type
                        if param.arg_pointer_flag:
                            arg_types.append('POINTER(c_int)')
                            fp.write(f'    :param {arg_name}_p: A pointer of the enumerate class {arg_type}\n')
                        else:
                            arg_types.append('c_int')
                            fp.write(f'    :param {arg_name}: member from enumerate class {arg_type}\n')
                    elif arg_type in self.struct_class_name_list:
                        if param.arg_pointer_flag:
                            arg_types.append(f'POINTER({arg_type})')
                            fp.write(f'    :param {arg_name}_p: A pointer of the structure class {arg_type}\n')
                        else:
                            arg_types.append(arg_type)
                            fp.write(f'    :param {arg_name}: implementation of the structure class {arg_type}\n')
                    elif 'CFUNCTYPE' in arg_type:
                        arg_types.append(arg_type)
                        fp.write(f'    :param {arg_name}: a function pointer\n')
                    else:
                        if param.arg_pointer_flag and arg_type != 'c_void_p':
                            arg_types.append(f'POINTER({arg_type})')
                            fp.write(f'    :param {arg_name}_p: A pointer of {arg_type}\n')
                        else:
                            arg_types.append(arg_type)
                            fp.write(f'    :param {arg_name}: argument type {arg_type}\n')
                fp.write('    """\n')

                fp.write(f'    func = {self.dll_name}["{func.func_name}"]\n')
                arg_types = ', '.join(arg_types)
                fp.write(f'    func.argtypes = [{arg_types}]\n')
                fp.write(f'    func.restype = {func.ret_type}\n')
                fp.write(f'    ret = func({arg_names})\n')
                fp.write(f'    return ret\n\n\n')

    def write_testcase_header(self):
        with open(self.testcase, 'w') as fp:
            fp.write('import os\nimport logging\nimport time\nimport traceback\n')
            fp.write('from enum_class import *\n')
            fp.write('from structure_class import *\n')
            fp.write(f'from {self.wrapper[:-3]} import *\n')
            fp.write('\n')
            fp.write('if __name__ == "__main__":\n')

    def write_testcase(self):
        """
        Automatically generate testcases. Since the initial value is usually set at practice. This part is just a draft.
        """
        #shutil.copyfile('testcase_template.py', self.testcase)
        self.write_testcase_header()

        basic_type_list = ['c_int8', 'c_int16', 'c_int32', 'c_int64', 'c_uint8', 'c_uint16', 'c_uint32', 'c_uint64', 'c_uint', 'c_int', 'c_float', 'c_double', 'c_char']
        with open(self.testcase, 'a') as fp:
            for func in self.func_list:
                arg_names = list()
                logging_infos = list()
                init_param_infos = list()
                for param in func.parameters:
                    arg_type = param.arg_type
                    arg_name = param.arg_name
                    # common param
                    if arg_type == 'c_void_p':
                        pass
                    elif arg_type in basic_type_list:
                        init_param_infos.append(f'    {arg_name} = 1\n')  # maybe we could iterate/ lane ranges from 0, 1, 2, 3
                        if param.arg_pointer_flag:
                            init_param_infos.append(f'    {arg_name}_p = {arg_type}({arg_name})\n')
                            logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}_p.value' + '}")\n')
                            arg_name = arg_name + '_p'
                        else:
                            logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}' + '}")\n')
                    elif arg_type in self.enum_class_name_list:
                        member_names = eval(arg_type).__dict__['_member_names_']
                        init_param_infos.append(f'    {arg_name} = {arg_type}.{member_names[0]}.value\n')  # maybe we could iterate
                        if param.arg_pointer_flag:
                            init_param_infos.append(f'    {arg_name}_p = {arg_type}({arg_name})\n')
                            logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}_p.value' + '}")\n')
                            arg_name = arg_name + '_p'
                        else:
                            logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}' + '}")\n')
                    elif arg_type in self.struct_class_name_list:
                        attr_inits = []
                        for struct_tmp in self.struct_class_list:
                            if arg_type == struct_tmp.struct_name:
                                struct = struct_tmp
                        for struct_member, struct_type, pointer_flag, member_idx in zip(struct.struct_members, struct.struct_types, struct.pointer_flags, struct.member_idc):
                            # Whether the parameter is an array
                            if member_idx:
                                init_param_infos.append(f'    {struct_member} = ({struct_type} * {member_idx})()\n')
                                init_param_infos.append(f'    {struct_member}_init = [0] * {member_idx}\n')
                                init_param_infos.append(f'    for idx, value in enumerate({struct_member}_init):\n        {struct_member}[idx] = value\n')
                                attr_inits.append(f'{struct_member}')
                            else:
                                attr_inits.append('0')                          # Just give it an initial value... Usually it is used for OUT
                                logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_type}.{struct_member}' + '}")\n')

                        attr_init = ', '.join(attr_inits)
                        init_param_infos.append(f'    {arg_name} = {arg_type}({attr_init})\n')
                        if param.arg_pointer_flag:
                            init_param_infos.append(f'    {arg_name}_p = byref({arg_name})\n')
                            arg_name = arg_name + '_p'
                    elif 'CFUNCTYPE' in arg_type:
                        # function pointer, which means this is a device initiation function. I should manually write it
                        logging_infos = list()
                        break
                    else:
                        logging.warning(f'Unrecognized arg_type {arg_type}; func_name {func.func_name}; arg_name {arg_name}')
                    arg_names.append(arg_name)

                if logging_infos:
                    params = ', '.join(arg_names)
                    fp.write(f'    logging.info("Function name : {func.func_name}")\n')
                    for init_param_info in init_param_infos:
                        fp.write(f'{init_param_info}')
                    fp.write(f'    try:\n        {func.func_name}({params})\n    except Exception:\n        traceback.print_exc()\n')

                    for logging_info in logging_infos:
                        fp.write(f'{logging_info}')
                    fp.write('    logging.info("\\n")\n')
                    fp.write('\n')


class TypeUnionParser(StructUnionParser, EnumParser, FunctionParser):
    """
    Parse the header files in the include path and store the customized variable types in python format.
    Store the parsing result in enum_class.py (typedef enumerate) and structure_class.py (typedef structure)
    Store the macros in a dictionary
    """
    def __init__(self):
        StructUnionParser.__init__(self)
        EnumParser.__init__(self)
        FunctionParser.__init__(self)

    def __call__(self):
        """
        Main function when you use this parser
        """
        h_files_to_parse = self.env.get('h_files_to_parse', ['*.h'])
        for file_path in h_files_to_parse:
            self.h_files.extend(glob.glob(file_path))

        self.parse()
        self.write_to_file()

        h_files_to_wrap = self.env.get('h_files_to_wrap', ['*.h'])
        for file_path in h_files_to_wrap:
            self.h_files.extend(glob.glob(file_path))
        c_files_to_wrap = self.env.get('c_files_to_wrap', ['*.c'])
        for file_path in c_files_to_wrap:
            self.c_files.extend(glob.glob(file_path))
        self.generate_func_list_from_h_files()
        self.generate_func_list_from_c_files()
        self.write_funcs_to_wrapper()

    def parse(self):
        """
        Parse the header files
        """
        self.generate_enum_class_list()
        self.generate_macro_dict()
        self.generate_func_ptr_dict()
        self.generate_struct_union_class_list()
        self.convert_structure_class_to_ctype()

    def write_to_file(self):
        """
        Write the parsing result to file
        """
        self.write_enum_class_into_py()
        self.write_structure_class_into_py()

    def generate_macro_dict(self):
        for h_file in self.h_files:
            with open(h_file, 'r') as fp:
                contents = fp.read()
                contents = rm_c_comments(contents)
                m = re.compile(r'#define\s(\w+)\s+(0x[0-9a-fA-F]+|\d+)')
                contents = re.findall(m, contents)
                for content in contents:
                    if content[1].startswith('0x'):
                        self.macro_dict[content[0]] = int(content[1], 16)
                    else:
                        self.macro_dict[content[0]] = content[1]

        for enum in self.enum_class_list:
            for member, value in zip(enum.enum_members, enum.enum_values):
                self.macro_dict[member] = str(value)

    def generate_func_ptr_dict(self):
        # parse header files
        for h_file in self.h_files:
            with open(h_file, 'r') as fp:
                contents = fp.read()
                contents = rm_c_comments(contents)
                m = re.compile(r'typedef\s*([\w*]+)\s+\(\*([\w]+)\)([^;]+);')
                contents = re.findall(m, contents)
                for content in contents:            # For each function pointer
                    value = list()
                    ret_type = content[0]
                    if '*' in ret_type:
                        ret_type, ret_pointer_flag = self.convert_to_ctypes(ret_type, True)
                    else:
                        ret_type, ret_pointer_flag = self.convert_to_ctypes(ret_type, False)
                    if ret_type in self.enum_class_name_list:
                        ret_type = 'c_int'
                    if ret_pointer_flag:
                        value.append(f'POINTER({ret_type})')
                    else:
                        value.append(f'{ret_type}')

                    key = content[1]
                    args = re.findall(r'([\w*]+)\s+([*\w[\[\]]+)?', content[2])
                    for arg in args:                # For each parameter
                        param_info = tuple([None]) + arg
                        param = self._Param(param_info=param_info)
                        param.arg_type, param.arg_pointer_flag = self.convert_to_ctypes(param.arg_type, param.arg_pointer_flag)
                        if param.arg_type in self.enum_class_name_list:
                            param.arg_type = 'c_int'
                        if param.arg_pointer_flag:
                            value.append(f'POINTER({param.arg_type})')
                        else:
                            value.append(f'{param.arg_type}')
                    value = ', '.join(value)
                    self.func_pointer_dict[key] = value


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s! File: %(filename)s Line %(lineno)d; Msg: %(message)s', datefmt='%d-%M-%Y %H:%M:%S')

    parser = TypeUnionParser()
    parser()

    from enum_class import *
    from structure_class import *
    parser.write_testcase()
