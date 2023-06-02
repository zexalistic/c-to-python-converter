"""
    @usage: automatically generate Cpython wrappers from header files
    @date: 2021-03-05
    @author: Yihao Liu
    @email: lyihao@marvell.com
    @python: 3.7
    @latest modification: 2023-06-02
    @version: 2.1.13
    @update: update gui
"""
import glob
import os
import re
import logging
import traceback
import json
from collections import deque


def rm_miscellenous(lines: str) -> str:
    """
    remove C comments in the file to parse
    """
    m = re.compile(r'//.*')
    lines = re.sub(m, '', lines)
    m = re.compile(r'/\*.*?\*/', re.S)
    lines = re.sub(m, '', lines)

    """
    remove backslash at the end of each line
    """
    lines = re.sub(r'\\\n', '', lines)

    """
    remove additional new lines to make debugging info clear
    """
    lines = re.sub(r'\n{3,}', '\n\n', lines)

    """
    remove ornamental keywords such as auto, volatile, static etc.
    """
    redundant_keyword_list = ['const', 'signed', 'auto', 'volatile', 'static', 'inline']

    for key in redundant_keyword_list:
        lines = re.sub(r'\b{}\b'.format(key), '', lines)

    """
    remove space before bracket, which will save the work to match arrays
    """
    lines = re.sub(r'\s+\[', '[', lines)

    return lines


def unique_list(file_list: list) -> list:
    """
    Although using set to eliminate repeated files is convenient, the result of set is disordered.
    Thus, we manually compare and remove repeated files.
    """
    tmp_file_list = []
    for file in file_list:
        if file not in tmp_file_list:
            tmp_file_list.append(file)
    return tmp_file_list


class CommonParser:
    """
    Base class for all parser
    """
    def __init__(self):
        self.h_files = list()                           # list of header files
        self.c_files = list()                           # list of C files to parse

        self.struct_class_name_list = list()            # name list of structure class
        self.enum_class_name_list = list()
        self.enum_class_list = list()
        self.exception_list = list()                    # list of keys in exception dict
        self.struct_class_list = list()                 # list of structure
        self.array_list = list()                        # list of large C arrays
        self.func_name_list = list()                    # names of functions in wrapper
        self.struct_union_type_dict = dict()
        self.basic_type_dict = dict()

        # Read from json
        with open('config.json', 'r') as fp:
            self.env = json.load(fp)
        self.exception_dict = self.env.get('exception_dict', dict())
        self.func_pointer_dict = self.env.get('func_pointer_dict', dict())   # key: str, item: list of parameters
        self.macro_dict = self.env.get('predefined_macro_dict', dict())
        self.dll_path = self.env.get('dll_path', 'Sample.dll')

    class _Param:
        """
        A class recording the information of the parameter of a C function
        """
        def __init__(self, param_info=(None, None)):      # param_info sample: MZD_U8 Var_name
            self.arg_pointer_flag = False
            arg_info = list()
            for info in param_info:
                if info and ('*' in info or '[' in info):
                    self.arg_pointer_flag = True
                    info = re.sub(r'[\[\]*]', '', info)
                arg_info.append(info)

            self.arg_type = arg_info[0].strip()
            self.arg_name = arg_info[1]

    class _Type:
        """
        Class used in TypeDefParser
        """

        def __init__(self, name: str, base_type: str, is_ptr: bool):
            self.name = name
            self.base_type = base_type
            self.is_ptr = is_ptr

    class _DebugInfo:
        def __init__(self):
            self.filename = ''
            self.line_number = 0

    def convert_to_ctypes(self, arg_type: str, arg_ptr_flag: bool, debug_info=None):
        """
        Convert customized variable type to ctypes according to the type dict
        """
        if self.exception_dict.__contains__(arg_type):
            arg_type = self.exception_dict[arg_type]
            arg_ptr_flag = False
        elif self.basic_type_dict.__contains__(arg_type):
            arg_ptr_flag = self.basic_type_dict[arg_type].is_ptr or arg_ptr_flag
            arg_type = self.basic_type_dict[arg_type].base_type
        elif arg_type in self.enum_class_name_list:
            pass
        elif arg_type in self.struct_class_name_list:
            pass
        elif self.struct_union_type_dict.__contains__(arg_type):
            arg_ptr_flag = self.struct_union_type_dict[arg_type].is_ptr or arg_ptr_flag
            arg_type = self.struct_union_type_dict[arg_type].base_type
        elif self.func_pointer_dict.__contains__(arg_type):
            arg_type = f"CFUNCTYPE({', '.join(self.func_pointer_dict[arg_type])})"
            arg_ptr_flag = True
        else:
            logging.warning(f'Unrecognized type! Type name: {arg_type}.')
            if debug_info:
                logging.warning(f'File: {debug_info.filename}, Line: {debug_info.line_number}')

        return arg_type, arg_ptr_flag


class PreProcessor(CommonParser):
    """
    Preprocess header files
    """
    def __init__(self):
        super().__init__()
        self.intermediate_h_files = list()  # list of intermediate h files
        self.macro_func_dict = dict()   # key = name of macro func, value = macro func class

        # C operator dictionary in #if clause
        self.c_operator_dict = {'&&': ' and ', '||': ' or ', 'defined': ''}

        self.fully_visited_list = list()
        self.visited_list = list()
        self.node_list = self._NodeList()
        self.detected_loop = False
        self.squeezed_flag = False

    class _MacroFunc:
        """
        Class containing information of a macro function
        """
        def __init__(self):
            self.name = None            # name of macro
            self.param_list = list()
            self.value = None           # string representing the value of macro

    class _Node:
        """
        Class used in topological sorting
        """
        def __init__(self, item):
            self.in_nodes = list()
            self.out_nodes = list()
            self.item = item        # name of header file, string or list

    class _NodeList:
        """
        The topography of node
        """
        def __init__(self):
            self.nodes = list()
            self.node_items = list()

        def __getitem__(self, idx):
            return self.nodes[idx]

        def __iter__(self):
            self.current_index = 0
            return self

        def __next__(self):
            if self.current_index == len(self.nodes):
                raise StopIteration
            else:
                result = self.nodes[self.current_index]
                self.current_index += 1
                return result

        def get_node_by_name(self, name: str):
            for node in self.nodes:
                if node.item == name:
                    return node
            return None

    def pre_process(self):
        self.h_files = self.sort_h_files()
        for h_file in self.h_files:
            with open(h_file, 'r') as fp:
                lines = fp.read()
                lines = rm_miscellenous(lines)
                self.intermediate_h_files.append(lines)

    def topo_sort(self):
        sorted_list = list()
        while self.node_list.nodes:
            zero_in_node = None
            for node in self.node_list:
                if not node.in_nodes:
                    zero_in_node = node
                    break
            if zero_in_node:
                self.node_list.nodes.remove(zero_in_node)
                if isinstance(zero_in_node.item, str):
                    sorted_list.append(zero_in_node.item)
                else:   # is list
                    sorted_list.extend(zero_in_node.item)
                for node in self.node_list.nodes:
                    if zero_in_node in node.in_nodes:
                        node.in_nodes.remove(zero_in_node)
            else:
                logging.error("topography has loop!!!")
                break

        return sorted_list

    def fill_in_node_list(self, include_list: list):
        if include_list:
            prev_node = None
            for include_item in include_list:
                if include_item not in self.node_list.node_items:
                    node = self._Node(include_item)
                    self.node_list.nodes.append(node)
                    self.node_list.node_items.append(include_item)
                else:
                    node = self.node_list.get_node_by_name(include_item)

                if prev_node and prev_node is not node and node not in prev_node.out_nodes:
                    prev_node.out_nodes.append(node)
                prev_node = node

    def generate_node_graph(self, file_list: list, is_h_file: bool):
        quick_table = [os.path.basename(h_file) for h_file in self.h_files]

        for file in file_list:
            with open(file, 'r') as fp:
                lines = fp.read()
                lines = rm_miscellenous(lines)
                include_list = re.findall(r'#include\s+["<](\w+.h)[">]\s*', lines)
                include_list = [self.h_files[quick_table.index(os.path.basename(i))] for i in include_list if os.path.basename(i) in quick_table]
                if is_h_file:
                    include_list.append(file)
                self.fill_in_node_list(include_list)

    def sort_h_files(self) -> list:
        """
        Before we sort the header files in DFS, we need to pre-sort the header files according to their including
        order in C files. A corresponding header file is sometimes not explicitly called in header files, whereas
        they are called in a C file before including that header file. In that case, we need to parse the C files
        and get the order of "#include" and guide our sorting of header files.
        Since C files are not part of our input, we only parse the C files in target folder and same folder level of target h files.
        Then we need to consider the #include order in header files.
        Finally, we will do the topographical sorting and get the correct order of calling header files.

        """
        # Step1: generate node graph
        self.generate_node_graph(self.h_files, is_h_file=True)
        self.generate_node_graph(self.c_files, is_h_file=False)

        for node in self.node_list.nodes:
            for out_node in node.out_nodes:
                out_node.in_nodes.append(node)

        # Step2: remove loop, and then squeeze them into one node
        while self.node_list.nodes:
            node = self.node_list.nodes[0]
            self.dfs_node(node)
            if self.detected_loop:     # There is a loop
                self.node_list.nodes = self.visited_list + self.node_list.nodes
                self.visited_list = list()
                self.detected_loop = False
                self.squeezed_flag = False

        self.node_list.nodes = self.fully_visited_list

        # Step3: topo sort
        return self.topo_sort()

    @staticmethod
    def update_node_list(squeezed_node: _Node, loop_node_list: list, in_out_node_list: list) -> list:
        new_in_out_node_list = [in_node for in_node in in_out_node_list if in_node not in loop_node_list]
        if len(in_out_node_list) != len(new_in_out_node_list):
            new_in_out_node_list.append(squeezed_node)

        return new_in_out_node_list

    def squeeze_into_one_node(self, loop_node_list: list):
        in_nodes = list()
        out_nodes = list()
        items = list()
        for node in loop_node_list:
            in_nodes = in_nodes + [in_node for in_node in node.in_nodes if in_node not in loop_node_list]
            out_nodes = out_nodes + [out_node for out_node in node.out_nodes if out_node not in loop_node_list]
            if isinstance(node.item, str):
                items.append(node.item)
            else:       # is a list
                items.extend(node.item)
            self.visited_list.remove(node)

        squeezed_node = self._Node(items)
        squeezed_node.in_nodes = unique_list(in_nodes)
        squeezed_node.out_nodes = unique_list(out_nodes)

        # replace node in loop node list with the squeezed node
        for node in self.node_list.nodes:
            node.in_nodes = self.update_node_list(squeezed_node, loop_node_list, node.in_nodes)
            node.out_nodes = self.update_node_list(squeezed_node, loop_node_list, node.out_nodes)
        for node in self.visited_list:
            node.in_nodes = self.update_node_list(squeezed_node, loop_node_list, node.in_nodes)  # This line is critical
            node.out_nodes = self.update_node_list(squeezed_node, loop_node_list, node.out_nodes)
        for node in self.fully_visited_list:
            node.in_nodes = self.update_node_list(squeezed_node, loop_node_list, node.in_nodes)

        self.node_list.nodes.append(squeezed_node)

    def dfs_node(self, node: _Node):
        if self.squeezed_flag:
            return None

        if not self.detected_loop:
            self.visited_list.append(node)
            self.node_list.nodes.remove(node)

        for out_node in node.out_nodes:
            if out_node in self.visited_list and not self.detected_loop:
                self.detected_loop = True
                return [out_node, node]                 # only returning [out_node] causes bug
            elif out_node in self.node_list.nodes and not self.squeezed_flag:   # in untouched list
                ret = self.dfs_node(out_node)
                if not ret:
                    continue
                if ret[0] == node:
                    self.squeeze_into_one_node(ret)
                    self.squeezed_flag = True
                    return None
                else:
                    return ret + [node]
            else:   # node in fully visited list or in a traceback process
                continue

        if not self.detected_loop:
            self.fully_visited_list.append(node)
            self.visited_list.remove(node)

        return None

    def parse_macro(self, lines: str):
        """
        Parse the #define clause within lines and append the macros to the macro dictionary
        """
        macro_list = re.findall(r'#define\s+(\w+)\b(.*)\n', lines)
        for item in macro_list:
            val = item[1].strip()

            if val == '' or val == '__declspec(dllexport)':
                self.macro_dict[item[0]] = val
            else:
                try:
                    value = eval(val)
                    if isinstance(value, int) or isinstance(value, float):
                        self.macro_dict[item[0]] = value
                    else:
                        logging.error(f"Error in parsing macro {item[0]}\n")
                        continue
                except Exception:
                    for m, v in self.macro_dict.items():
                        val = re.sub(r'\b{}\b'.format(m), '{}'.format(v), val)
                    val = re.sub(r'\b(\d+)[uUlL]+\b', r'\1', val)
                    val = re.sub(r'\b(0x[\dA-F]+)[uUlL]+\b', r'\1', val)
                    try:
                        value = eval(val)
                        if isinstance(value, int) or isinstance(value, float):
                            self.macro_dict[item[0]] = value
                        else:
                            # logging.warning(f"Unable to parse macro, {item[0]}\n")
                            pass
                    except Exception:
                        if val.startswith('('):
                            # macro function
                            pass
                        else:
                            traceback.print_exc()
                            # logging.warning(f'Unable to parse macro; {item[0]}')
                            pass
                            continue

    def check_macro(self):
        for i, lines in enumerate(self.intermediate_h_files):
            lines = '\n' + self.intermediate_h_files[i] + '\n'        # append a pseudo new line here to make sure there must be some code before #ifdef and after #endif
            # comment: len(blocks) = len(criterion)+1;
            blocks = re.split(r'#if\s+defined\s+\w+\b\s*\n|#if.*\s*\n|#elif.*\s*\n|#ifndef\s+\w+\b\s*\n|#if\s+\w+\b\s*\n|#ifdef\s+\w+\b\s*\n|#endif|#else\s*\n|#elif\s+\w+\b\s*\n', lines)
            criterion = re.findall(r'#if\s+defined\s+\w+\b\s*\n|#if.*\s*\n|#elif.*\s*\n|#ifndef\s+\w+\b\s*\n|#if\s+\w+\b\s*\n|#ifdef\s+\w+\b\s*\n|#endif|#else\s*\n|#elif\s+\w+\b\s*\n', lines)
            criterion = [tmpCter.strip() for tmpCter in criterion]
            tmpPattern = re.compile(r'(\d+)[uUlL]+')
            criterion = [tmpPattern.subn(r'\1', tmpCter)[0] for tmpCter in criterion]
            criterion = list(filter(None, criterion))

            # Process the first code block here. It should always be valid.
            code_block = blocks.pop(0)
            self.parse_macro(code_block)
            new_lines = code_block          # save result
            flag_stack = deque()  # use a stack to remember whether the former criterion is valid
            flag_stack.append(True)
            is_ignore_else = True  # whether we should ignore the #else clause or not

            while criterion:
                criteria = criterion.pop(0)
                code_block = blocks.pop(0)
                # check ifndef, ifdef, if, if defined
                if criteria.startswith('#ifndef'):
                    macro = re.search(r'#ifndef\s+(\w+)', criteria).group(1)
                    flag = (not self.macro_dict.__contains__(macro)) and flag_stack[-1]   # the validation before and after criteria both affect
                    flag_stack.append(flag)
                    is_ignore_else = not self.macro_dict.__contains__(macro)

                elif criteria.startswith('#ifdef'):
                    macro = re.search(r'#ifdef\s+(\w+)', criteria).group(1)
                    flag = self.macro_dict.__contains__(macro) and flag_stack[-1]   # the validation before and after criteria both affect
                    flag_stack.append(flag)
                    is_ignore_else = self.macro_dict.__contains__(macro)

                elif criteria.startswith('#endif'):
                    flag_stack.pop()             # deque pop from right
                    is_ignore_else = True
                    try:
                        flag = flag_stack[-1]
                    except IndexError:
                        traceback.print_exc()
                        logging.error(f'Error in preprocessing file {self.h_files[i]}.')
                elif criteria.startswith('#if') or criteria.startswith('#elif'):
                    if criteria.startswith('#if'):
                        expr = re.search(r'#if\s+(.+)', criteria).group(1)
                    else:
                        if is_ignore_else:
                            continue
                        expr = re.search(r'#elif\s+(.+)', criteria).group(1)
                        flag_stack.pop()
                    for key, val in self.c_operator_dict.items():       # replace c operator with python operator
                        expr = expr.replace(key, val)
                    for macro, val in self.macro_dict.items():          # replace macro with it original value
                        expr = re.sub(r'\b{}\b'.format(macro), '{}'.format(val), expr)

                    try:
                        if eval(expr):
                            flag = flag_stack[-1]
                            is_ignore_else = True
                        else:
                            flag = False
                            is_ignore_else = False
                        flag_stack.append(flag)
                    except Exception:
                        flag = False                                     # not defined macro
                        is_ignore_else = False
                        flag_stack.append(flag)

                elif criteria.startswith('#else'):
                    if is_ignore_else:
                        continue
                    else:
                        flag_stack.pop()
                        is_ignore_else = True
                        flag = flag_stack[-1]
                        flag_stack.append(flag)
                else:
                    logging.error(f"Unable to parse preprocessing clause : {criteria}")

                if flag:
                    self.parse_macro(code_block)
                    new_lines += code_block

            self.intermediate_h_files[i] = new_lines

    def replace_macro(self, lines: str) -> str:
        """
        replace macros in C code with its definition and return the clear C code
        """
        lines = re.sub(r'#define\s+.*\n', '', lines)
        for macro, val in self.macro_dict.items():
            lines = re.sub(r'\b{}\b'.format(macro), '{}'.format(val), lines)

        return lines


class TypeDefParser(PreProcessor):
    """
    Parse basic C types such as int, double etc. , and customized types such as U32 (equal to uint32_t)
    """
    def __init__(self):
        super().__init__()

        self.c_type_map_tree = dict()               # Depth = 3, level 1 is root, level 2 is basic C types, level 3 is lists of customized C types
        self.base_struct_union_types_list = list()

        # Basic C types, preload here
        self.basic_c_type_keys = ['int', 'int8_t', 'int16_t', 'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
                     'long long', 'long', 'wchar_t', 'unsigned long long', 'unsigned long', 'short', 'unsigned short', 'long double',
                     'unsigned int', 'float', 'double', 'char', 'unsigned char', '_Bool', 'size_t', 'ssize_t']
        self.basic_ctypes_lib_vars = ['c_int', 'c_int8', 'c_int16', 'c_int32', 'c_int64', 'c_uint8', 'c_uint16', 'c_uint32', 'c_uint64',
                           'c_longlong', 'c_long', 'c_wchar', 'c_ulonglong', 'c_ulong', 'c_short', 'c_ushort', 'c_longdouble',
                           'c_uint', 'c_float', 'c_double', 'c_char', 'c_ubyte', 'c_bool', 'c_size_t', 'c_ssize_t']
        self.init_basic_type_dict()

    def init_basic_type_dict(self):
        for key, key_ctype in zip(self.basic_c_type_keys, self.basic_ctypes_lib_vars):
            ttype = self._Type(name=key, base_type=key_ctype, is_ptr=False)
            self.basic_type_dict.setdefault(key, ttype)
        ttype = self._Type(name='void', base_type='c_int', is_ptr=False)
        self.basic_type_dict.setdefault('void', ttype)
        ttype = self._Type(name='bool', base_type='c_bool', is_ptr=False)
        self.basic_type_dict.setdefault('bool', ttype)
        ttype = self._Type(name='unsigned', base_type='c_uint', is_ptr=False)
        self.basic_type_dict.setdefault('unsigned', ttype)

    def generate_typedef_mapping_dict(self):
        """
        Generate basic type dict from header files
        """
        for lines in self.intermediate_h_files:
            contents = re.findall(r'typedef\s+([\w\s*]+)\s+(\w+);', lines)
            for content in contents:
                original_type = content[0]
                customized_type = content[1]
                ttype = self._Type(name=customized_type, base_type=original_type, is_ptr=False)
                if '*' in original_type:
                    original_type = original_type.strip('*')
                    ttype.is_ptr = True

                if 'struct' in original_type or 'union' in original_type:
                    original_type = re.sub(r'\bstruct\b', '', original_type)
                    original_type = re.sub(r'\bunion\b', '', original_type)
                    ttype.base_type = original_type.strip()
                original_type = original_type.strip()
                if original_type in self.basic_type_dict.keys():        # parse basic c types
                    ttype.base_type = self.basic_type_dict[original_type].base_type
                    ttype.is_ptr = ttype.is_ptr or self.basic_type_dict[original_type].is_ptr
                    self.basic_type_dict[customized_type] = ttype
                else:                                                   # parse struct/union typedef
                    if original_type in self.struct_union_type_dict.keys():
                        ttype.base_type = self.struct_union_type_dict[original_type].base_type
                        ttype.is_ptr = ttype.is_ptr or self.struct_union_type_dict[original_type].is_ptr
                    self.struct_union_type_dict[customized_type] = ttype


class StructUnionParser(PreProcessor):
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
            self.struct_types = list()                      # variable type of elements in structure
            self.pointer_flags = list()                     # list of bool
            self.member_idc = list()                        # list of integer
            self.isUnion = False                            # structure = False, Union = True

        def __getitem__(self, item):
            return self.struct_members[item], self.struct_types[item], self.struct_types[item], self.member_idc[item]

    def parse_struct_member_info(self, struct: _Struct, struct_infos: list):
        for struct_info in struct_infos:
            struct_info = struct_info.strip()  # This is necessary
            tmp = re.findall(r'([\[\]*\w\s]+)\s+([^;}]+)', struct_info)  # parse the members of structure
            if tmp:  # filter the empty list
                member_type = tmp[0][0].strip()
                member_name = tmp[0][1].strip()
                # find the pointer, this part only support 1st order pointer
                if member_type.endswith('*'):
                    struct.struct_types.append(member_type[:-1].strip())
                    struct.struct_members.append(member_name)
                    struct.pointer_flags.append(True)
                elif member_name.endswith('[]'):
                    struct.struct_types.append(member_type)
                    struct.struct_members.append(member_name[:-2].strip())
                    struct.pointer_flags.append(True)
                elif member_name.startswith('*'):
                    struct.struct_types.append(member_type)
                    struct.struct_members.append(member_name[1:].strip())
                    struct.pointer_flags.append(True)
                else:
                    struct.struct_types.append(member_type)
                    struct.struct_members.append(member_name)
                    struct.pointer_flags.append(False)
        self.struct_class_list.append(struct)
        self.struct_class_name_list.append(struct.struct_name)

    def generate_struct_union_class_list(self):
        """
        Parse header files and save structure/union into a list of class, which records their information
        """
        for lines in self.intermediate_h_files:
            structs = re.findall(r'typedef struct[\s\w]*{([^{}]+)}([\s\w,*]+);\s', lines)             # match: typedef struct _a{}a, *ap;
            struct_flags = [False] * len(structs)
            unions = re.findall(r'typedef union[\s\w]*{([^{}]+)}([\s\w,*]+);\s', lines)             # match: typedef union _a{}a, *ap;
            union_flags = [True] * len(unions)
            contents = structs + unions
            flags = struct_flags + union_flags
            for content, flag in zip(contents, flags):
                struct = self._Struct()
                struct.isUnion = flag
                struct_name = re.sub(r'\s', '', content[1])
                if re.search(r',\s*\*', struct_name):
                    struct_name, struct_pointer_name = re.search(r'(\w+),\s*\*(\w+)', struct_name).groups()
                    ttype = self._Type(name=struct_pointer_name, base_type=struct_name, is_ptr=True)
                    self.struct_union_type_dict[struct_pointer_name] = ttype            # store struct pointer
                struct.struct_name = struct_name
                if self.exception_dict.__contains__(struct_name):
                    continue
                else:
                    struct_infos = content[0].split(';')
                    self.parse_struct_member_info(struct, struct_infos)

            structs = re.findall(r'struct\s*([\w]+)\s*{([^}]+)?}\s*;', lines)  # match: struct _a{};
            struct_flags = [False] * len(structs)
            unions = re.findall(r'union\s*([\w]+)\s*{([^}]+)?}\s*;', lines)  # match: struct _a{};
            union_flags = [True] * len(unions)
            contents = structs + unions
            flags = struct_flags + union_flags
            for content, flag in zip(contents, flags):
                struct = self._Struct()
                struct.isUnion = flag
                struct_name = re.sub(r'\s', '', content[0])
                struct.struct_name = struct_name
                if self.exception_dict.__contains__(struct_name):
                    continue
                else:
                    struct_infos = content[1].split(';')
                    self.parse_struct_member_info(struct, struct_infos)

    def sort_structs(self):
        sorted_queue = deque()

        for item in self.struct_class_list:
            sorted_queue = self.sort_structs_dfs(item, sorted_queue)

        sorted_queue = list(sorted_queue)
        unique_queue = list(set(sorted_queue))
        unique_queue.sort(key=sorted_queue.index)
        self.struct_class_list = unique_queue
        self.struct_class_name_list = [struct.struct_name for struct in self.struct_class_list]

    def sort_structs_dfs(self, item: _Struct, sorted_queue: deque):
        sorted_queue.appendleft(item)
        for struct_type in item.struct_types:
            struct_type = re.sub(r'^POINTER\(', '', struct_type)  # Remove POINTER decoration
            struct_type = re.sub(r'\)$', '', struct_type)  # Remove POINTER decoration
            if struct_type in self.struct_class_name_list:
                idx = self.struct_class_name_list.index(struct_type)
                dependent_struct = self.struct_class_list[idx]
                sorted_queue.appendleft(dependent_struct)
                sorted_queue = self.sort_structs_dfs(dependent_struct, sorted_queue)
            elif self.func_pointer_dict.__contains__(struct_type):
                for param in self.func_pointer_dict[struct_type]:
                    param = re.sub(r'^POINTER\(', '', param)  # Remove POINTER decoration
                    param = re.sub(r'\)$', '', param)  # Remove POINTER decoration
                    if param in self.struct_class_name_list:
                        idx = self.struct_class_name_list.index(param)
                        dependent_struct = self.struct_class_list[idx]
                        sorted_queue.appendleft(dependent_struct)
                        sorted_queue = self.sort_structs_dfs(dependent_struct, sorted_queue)

        return sorted_queue

    def convert_structure_class_to_ctypes(self):
        """
        Convert customized type to ctypes here; convert C array to legal python ctypes here.

        Since the member type of some structure is another class member, the order of definition of class has to be arranged so that structure_class.py
        can be imported as a python module.
        """
        updated_struct_list = list()

        # convert struct_type to ctype
        for i, struct in enumerate(self.struct_class_list):
            updated_struct_members = list()
            updated_struct_types = list()
            for member, struct_type, pointer_flag in zip(struct.struct_members, struct.struct_types, struct.pointer_flags):
                idx = 0
                # check if member is array
                if '][' in member:    # high order array
                    expressions = re.findall(r'\[([\w\s*/+\-()]+)?]', member)
                    idx = 1
                    member = re.search(r'(\w+)\[.*]', member).group(1)
                    for expr in expressions:
                        try:
                            idx = idx * int(eval(expr))
                        except Exception:
                            traceback.print_exc()
                            logging.error(f'Unrecognized macro: {expr}.. {struct.struct_name}')

                elif '[' in member:  # 1 order array
                    if re.search(r'\w+\[([\s*/\-+\d()]+)]', member):  # support +-/*
                        member, idx = re.search(r'(\w+)\[([\s*/\-+\d()]+)]', member).groups()
                    elif re.search(r'\w+\[([\s*/\-+\d\w]+)]', member):  # There is a macro within array index
                        member, idx = re.search(r'(\w+)\[([\s*/\-+\d()\w]+)]', member).groups()
                    try:
                        idx = int(eval(idx))
                    except Exception:
                        traceback.print_exc()
                        logging.error(f'Unrecognized macro: {idx}... {struct.struct_name}')

                else:
                    # This is not an array
                    pass

                struct_type, pointer_flag = self.convert_to_ctypes(struct_type, pointer_flag)

                if struct_type in self.enum_class_name_list:
                    struct_type = 'c_long'

                struct.member_idc.append(idx)
                updated_struct_members.append(member)
                updated_struct_types.append(struct_type)
            struct.struct_types = updated_struct_types
            struct.struct_members = updated_struct_members
            updated_struct_list.append(struct)

        # Sort the structure class
        self.sort_structs()

    def write_structure_class_into_py(self):
        """
        generate struct_class.py
        """
        with open(os.path.join('output', 'structure_class.py'), 'w') as fp:
            fp.write('"""\n')
            fp.write('    @usage: Conversion result of Structure and Union type\n')
            fp.write('"""\n')
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


class EnumParser(PreProcessor):
    """
    Parse the header files in the folder. Catch the enum types and sort them into enum_class.py
    """
    def __init__(self):
        super().__init__()

    class _Enum:
        """
        A class recording the name, members, values of a enumerate type
        """
        def __init__(self):
            self.enum_name = None
            self.enum_members = list()              # list of string
            self.enum_values = list()               # list of integer

        def __getitem__(self, item):
            return self.enum_members[item], self.enum_values[item]

    def parse_enum(self, enum_name: str, enum_infos: str):
        enum = self._Enum()
        enum.enum_name = enum_name

        enum_infos = enum_infos.split(',')
        enum_infos = list(filter(None, enum_infos))
        default_value = 0
        for enum_info in enum_infos:
            if '=' in enum_info:
                enum_member = enum_info.split('=')[0]
                enum_value = enum_info.split('=')[1]

                try:
                    value = eval(enum_value)
                    if isinstance(value, int) or isinstance(value, float):
                        enum_value = value
                        default_value = enum_value
                    else:
                        logging.warning(f"Unable to parse enum {enum_member}\n")
                        return None
                except Exception:
                    for m, v in self.macro_dict.items():
                        enum_value = re.sub(r'\b{}\b'.format(m), '{}'.format(v), enum_value)
                    enum_value = re.sub(r'\b(\d+)[uUlL]+\b', r'\1', enum_value)
                    enum_value = re.sub(r'\b(0x[\dA-F]+)[uUlL]+\b', r'\1', enum_value)
                    try:
                        value = eval(enum_value)
                        if isinstance(value, int) or isinstance(value, float):
                            enum_value = value
                            default_value = enum_value
                        else:
                            logging.warning(f"Unable to parse enum {enum_member}\n")
                            return None
                    except Exception:
                        traceback.print_exc()
                        logging.error(f"Error in parsing enum {enum_member}\n")
                        continue
            else:
                enum_member = enum_info
                enum_value = default_value

            default_value += 1
            enum.enum_members.append(enum_member)
            enum.enum_values.append(enum_value)
            self.macro_dict[enum_member] = str(enum_value)          # extend the macro dictionary

        self.enum_class_list.append(enum)
        self.enum_class_name_list.append(enum.enum_name)

    def generate_enum_class_list(self):
        """
        Parse header files and get enumerate types. Store their information in enum_class
        """
        for lines in self.intermediate_h_files:
            contents = re.findall(r'typedef enum[^;]+;', lines)  # find all enumerate types
            for content in contents:
                tmp = re.split(r'[{}]', content)  # split the typedef enum{ *** } name;
                enum_infos = re.sub(r'\s', '', tmp[1])
                enum_name = re.sub(r'[\s;]', '', tmp[2])
                self.parse_enum(enum_name, enum_infos)

            contents = re.findall(r'enum\s+(\w+)\s*{([^{}]+)};', lines)  # parse another way to define a enum type
            for content in contents:
                enum_name = content[0]
                enum_infos = re.sub(r'\s', '', content[1])
                self.parse_enum(enum_name, enum_infos)

    def write_enum_class_into_py(self):
        """
        generate struct_class.py
        """
        with open(os.path.join('output', 'enum_class.py'), 'w') as f:
            f.write('"""\n')
            f.write('    @usage: Conversion result of Enumeration type\n')
            f.write('"""\n')
            f.write('from enum import Enum, unique, IntEnum\n\n\n')
            for enum in self.enum_class_list:
                # f.write(f'class {enum.enum_name}(IntEnum):\n')
                f.write(f'@unique\nclass {enum.enum_name}(IntEnum):\n')
                for member, val in enum:
                    f.write(f'    {member} = {val}\n')
                f.write('\n\n')


class FunctionParser(PreProcessor):
    """
    Automatically parse the header files
    """
    def __init__(self):
        super().__init__()
        self.func_list = list()
        self.dll_name = 'APILib'                                            # Alias of the return value of CDLL
        self.wrapper = "python_API.py"                                      # Name of Output wrapper
        self.testcase = "testcases.py"                                      # Output testcase

    class _Func:
        """
        A class recording the function name, type of return value and arguments
        """
        def __init__(self):
            self.func_name = None
            self.ret_type = None
            self.header_file = None
            self.parameters = list()

        def get_arg_names(self) -> str:
            """
            Parameter list to string of arguments in function
            """
            ret = list()
            for param in self.parameters:
                if param.arg_pointer_flag:
                    ret.append(param.arg_name + '_p')
                else:
                    ret.append(param.arg_name)
            return ', '.join(ret)

    def parse_func_parameters(self, content: str) -> list:
        param_list = list()
        param_infos = re.sub(r'\n', '', content)            # remove\n in parameters
        if not param_infos or param_infos.strip() == 'void':
            return param_list
        else:
            param_infos = param_infos.split(',')
            for i, param_info in enumerate(param_infos):
                # Parameter has two forms: (1) int func(void, int); (2) int func(void a, int b);
                # The if clause below checks these two forms and makes them a united format.
                param_info_clean = re.sub(r'[\[*\]]', '', param_info.strip())
                if self.exception_dict.__contains__(param_info_clean) \
                    or self.basic_type_dict.__contains__(param_info_clean) \
                    or param_info_clean in self.enum_class_name_list \
                    or param_info_clean in self.struct_class_name_list \
                    or self.struct_union_type_dict.__contains__(param_info_clean) \
                    or self.func_pointer_dict.__contains__(param_info_clean):
                    param_info = (param_info, f'arg{i}')
                else:
                    param_info = re.search(r'([*\w\s]+)\s+([\[\]*\w]+)', param_info).groups()
                param = self._Param(param_info=param_info)
                param.arg_type, param.arg_pointer_flag = self.convert_to_ctypes(param.arg_type, param.arg_pointer_flag)
                param_list.append(param)

        return param_list

    def generate_func_list_from_h_files(self):
        """
        parse all the header files in h_file list
        get all the functions to be wrapped.
        save those function information(name, argument type, return type) in func_list
        """
        for lines, h_file in zip(self.intermediate_h_files, self.h_files):
            # This pattern matching rule may have bugs in other cases
            # Another way is to use [^;] to replace .*?
            lines = re.findall(r'__declspec\(dllexport\)\s+([*\w]+)\s+(\w+)\s*\((.*?)\)\s*;', lines, re.S)  # find all exported functions
            # For each function
            for content in lines:
                if content[1] not in self.func_name_list:
                    self.func_name_list.append(content[1])
                else:
                    continue
                func = self._Func()
                ret_type = content[0]
                func.func_name = content[1]
                func.ret_type, ret_ptr_flag = self.convert_to_ctypes(ret_type, False)           # Ignore the case that return value is a pointer
                if func.ret_type in self.enum_class_name_list:
                    func.ret_type = 'c_int'

                # parse parameters
                param_infos = re.sub(r'\n', '', content[2])                          # remove () and \n in parameters
                if not param_infos or param_infos.strip() == 'void':
                    func.parameters = list()
                else:
                    param_infos = param_infos.split(',')
                    for param_info in param_infos:
                        param_info = re.search(r'([*\w\s]+)\s+([\[\]*\w]+)', param_info).groups()
                        param = self._Param(param_info=param_info)
                        param.arg_type, param.arg_pointer_flag = self.convert_to_ctypes(param.arg_type, param.arg_pointer_flag)
                        func.parameters.append(param)

                func.header_file = os.path.basename(h_file)[:-2]
                self.func_list.append(func)

    def write_funcs_to_wrapper(self):
        """
        Generate main.py
        """
        wrapper_name = os.path.join('output', self.wrapper)
        with open(wrapper_name, 'w') as fp:
            fp.write('"""\n')
            fp.write('    @usage: Conversion result of API\n')
            fp.write('"""\n')
            fp.write('import os\nfrom output.structure_class import *\n\n')
            fp.write(f'{self.dll_name} = CDLL(os.path.join(os.getcwd(), "{self.dll_path}"))\n\n\n')

        for func in self.func_list:
            with open(wrapper_name, 'a') as fp:
                arg_names = func.get_arg_names()
                fp.write(f'def {func.func_name}({arg_names}):\n')

                # Comment of this function
                fp.write('    """\n')
                arg_types = list()
                for param in func.parameters:
                    arg_type = param.arg_type
                    arg_name = param.arg_name
                    if arg_type in self.enum_class_name_list:              # convert customized variable type to C type
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
                    elif self.exception_dict.__contains__(arg_type):
                        arg_types.append(self.exception_dict[arg_type])
                        fp.write(f'    :param {arg_name}: argument type {self.exception_dict[arg_type]}\n')
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
            fp.write('"""\n')
            fp.write('    @usage: testcase template\n')
            fp.write('"""\n')
            fp.write('import os\nimport logging\nimport time\nimport traceback\n')
            fp.write('from output.enum_class import *\n')
            fp.write('from output.structure_class import *\n')
            fp.write(f'from output.{self.wrapper[:-3]} import *\n')
            fp.write('\n')
            fp.write('if __name__ == "__main__":\n')

    def write_testcase(self):
        """
        Automatically generate testcases. Since the initial value is usually set at practice. This part is just a draft.
        """
        self.write_testcase_header()

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
                    # elif arg_type in self.key_ctypes:
                    #     init_param_infos.append(f'    {arg_name} = 1\n')  # maybe we could iterate/ lane ranges from 0, 1, 2, 3
                    #     if param.arg_pointer_flag:
                    #         init_param_infos.append(f'    {arg_name}_p = {arg_type}({arg_name})\n')
                    #         logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}_p.value' + '}")\n')
                    #         arg_name = arg_name + '_p'
                    #     else:
                    #         logging_infos.append(f'    logging.debug(f"{arg_name}' + ' = {' + f'{arg_name}' + '}")\n')
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


class ArrayParser(PreProcessor):
    """
    Parse large arrays and write them in python style. This can help coder to call those large arrays in python without additional efforts.
    """
    def __init__(self):
        super().__init__()

    class _Array:
        """
        A class recording the information of the contents of a large C array
        """
        def __init__(self):
            self.arr_name = None                # string
            self.arr_idc = list()                # list of array indices
            self.arr_val = list()               # list of the whole array matrix

    def generate_array_list(self):
        """
        Write large array in C to py
        """
        for lines in self.intermediate_h_files:
            lines = re.findall(r'\w+\s+(\w+)\s*(\[.*])\s*=([^;]+);', lines)
            for content in lines:
                arr = self._Array()
                arr.arr_name = content[0]
                # parsing the array indices
                idcs = re.findall(r'\[([\d\s*/+\-()]+)?]', content[1])
                for idc in idcs:
                    try:
                        arr.arr_idc.append(str(eval(idc)))
                    except Exception:
                        traceback.print_exc()
                        logging.error(f'Unrecognized expression in C array: {content[0]}{content[1]}')
                arr.arr_val = re.sub('{', '[', content[2].strip())
                arr.arr_val = re.sub('}', ']', arr.arr_val)
                self.array_list.append(arr)

    def write_arr_into_py(self):
        if self.array_list:
            with open(os.path.join('output', 'c_arrays.py'), 'w') as fp:
                fp.write('"""\n')
                fp.write('    @usage: Conversion result of Arrays\n')
                fp.write('"""\n')
                fp.write('from structure_class import *\n\n')
                for arr in self.array_list:
                    arr_idc = '*'.join(arr.arr_idc)
                    fp.write(f'# Array size: {arr_idc}\n')
                    fp.write(f'{arr.arr_name} = {arr.arr_val}\n\n')


class Parser(TypeDefParser, StructUnionParser, EnumParser, FunctionParser, ArrayParser):
    """
    Major class of the final parser
    Parse the header files in the include path and store the customized variable types in python format.
    """
    def __init__(self):
        logging.basicConfig(filename='debug.log',
                            format='%(asctime)s %(levelname)s! File: %(filename)s Line %(lineno)d; Msg: %(message)s',
                            datefmt='%d-%M-%Y %H:%M:%S')
        FunctionParser.__init__(self)
        TypeDefParser.__init__(self)

    def __call__(self, skip_output=False):
        """
        Main function when you use this parser
        """
        h_files_to_parse = self.env.get('header_files', list())
        dir_paths = list()
        for file_path in h_files_to_parse:
            file_paths = glob.glob(file_path)
            file_paths = [os.path.relpath(p, os.getcwd()) for p in file_paths]
            self.h_files.extend(file_paths)
            if os.path.dirname(file_path) not in dir_paths:
                dir_paths.append(os.path.dirname(file_path))

        for dir_path in dir_paths:
            for f in os.listdir(dir_path):
                if f.endswith('.c'):
                    self.c_files.append(os.path.join(dir_path, f))

        project_folders = self.env.get('project_folders', list())
        for project_folder in project_folders:
            for root, dirs, files in os.walk(project_folder):
                for file in files:
                    if file.endswith('.h'):
                        file_path = os.path.join(root, file)
                        self.h_files.append(os.path.relpath(file_path, os.getcwd()))
                    elif file.endswith('.c'):
                        file_path = os.path.join(root, file)
                        self.c_files.append(os.path.relpath(file_path, os.getcwd()))

        self.h_files = unique_list(self.h_files)
        self.c_files = unique_list(self.c_files)

        self.pre_process()

        self.parse()

        if not skip_output:
            self.write_to_file()

        self.generate_func_list_from_h_files()
        self.write_funcs_to_wrapper()

    def parse(self):
        """
        Parse the header files
        """
        self.check_macro()
        self.generate_typedef_mapping_dict()
        self.generate_enum_class_list()
        for i, lines in enumerate(self.intermediate_h_files):
            lines = self.replace_macro(lines)
            self.intermediate_h_files[i] = lines
        self.generate_func_ptr_dict()
        self.generate_struct_union_class_list()
        self.convert_structure_class_to_ctypes()
        self.generate_array_list()

    def write_to_file(self):
        """
        Write the parsing result to file
        """
        if not os.path.exists('output'):
            os.mkdir('output')
        self.write_enum_class_into_py()
        self.write_structure_class_into_py()
        self.write_arr_into_py()

    def generate_func_ptr_dict(self):
        # parse header files
        for lines in self.intermediate_h_files:
            lines = re.findall(r'typedef\s+(\w+)\s*\(\*([\w]+)\)\s*\((.*?)\)\s*;', lines, re.S)
            for content in lines:            # For each function pointer
                val = list()
                ret_type = content[0]
                if '*' in ret_type:
                    ret_type, ret_pointer_flag = self.convert_to_ctypes(ret_type, True)
                else:
                    ret_type, ret_pointer_flag = self.convert_to_ctypes(ret_type, False)
                if ret_type in self.enum_class_name_list:
                    ret_type = 'c_int'
                if ret_pointer_flag:
                    val.append(f'POINTER({ret_type})')
                else:
                    val.append(f'{ret_type}')

                key = content[1]
                param_list = self.parse_func_parameters(content[2])
                for param in param_list:
                    if param.arg_type in self.enum_class_name_list:
                        param.arg_type = 'c_int'
                    if param.arg_pointer_flag:
                        val.append(f'POINTER({param.arg_type})')
                    else:
                        val.append(f'{param.arg_type}')
                self.func_pointer_dict.setdefault(key, val)


if __name__ == '__main__':
    # logging.basicConfig(format='%(levelname)s! File: %(filename)s Line %(lineno)d; Msg: %(message)s', datefmt='%d-%M-%Y %H:%M:%S')

    parser = Parser()
    parser()

    from output.enum_class import *
    from output.structure_class import *
    parser.write_testcase()
