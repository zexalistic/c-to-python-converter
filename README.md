## Automatically converting C code to python using ctypes lib

#### How to use
+ Edit config.json
+ Run autogen.py
+ Python APIs are in wrapper.py

#### Output
+ wrapper.py : the python wrapper of C functions written in ctypes style
+ Testcase_all.py: simple auto-generated testcases templates.

#### Brief introduction of ctypes
ctypes is a standard library of python to connect C with python. You need to first generate a dll/so file 
from C project and use ctypes.CDLL to call those C functions. Since the data structure in C and python are 
different, you need a wrapper as an interface to make the API more "pythonic". That's why I develop this 
wrapper auto-generator.

#### Limitation
1. Do not support other preprocessor commands except for "#define"
2. Do not support nested citation or definition. e.g. a is a structure whose member is another structure; b is an alias of c which is an alias of d.
3. Parameter of function can not be void. I regard it as 'int' at present version.
4. Parenthesis may affect the parsing result, e.g. ((a)) may have a different parsing result with a

 
#### TO-DO List in next version
1. Add void type and other c types
2. Write better testcases

#### For more Information
About what can be parsed, see the comments in Sample\sample.h.
It supports the conversion of structure, union, enumerate, typedef... which already meets the need of common project.
It removes the C commands and processes the C blackslash at the end of each line.
It substitutes all macros(except for function header) before parsing.

Python Ctypes document:
https://docs.python.org/3/library/ctypes.html

This blog introduces how to use python ctypes:
https://www.cnblogs.com/night-ride-depart/p/4907613.html

## Detailed User Guide 
#### How to edit config.json
You want to wrap the function *hello_world* in **Samples\main.c**. That function is defined in **Samples\main.h** and the related file is in **Samples\sample.h**. You complied your C files and put the result in **Samples\samples.dll**. Thus, you need to write below in config.json:
> "dll_path": "Samples\\\samples.dll",
"h_files_to_wrap": ["Samples\\\main.h"],

If some functions are defined in Samples\main.c, you need to add:
> "c_files_to_wrap": ["Samples\\\main.c"],

This is optional, so it is commented by default. Functions only defined in header files are preferred.

You opened **main.h** and found there are customized variable types *MY_BOOL* and *MY_INT*. They are defined in **Samples\sample.h**. Thus, you need to write below in config.json:
> "h_files_to_parse": ["Samples\\\sample.h"],

A prefix is usually necessary when you want to export the function to dll files. Thus, we use this as a sign to distinguish the C functions you want to wrap. 
You need to write the prefix in config.json. In **main.h**, the prefix is *FUNC_PREFIX*:
> "func_header": "FUNC_PREFIX",

The device handler in hardware is complex and usually wrapped separatedly, so I leave a special entry for these types. The parser will bypass these types and not recognize them as a common structure pointer. You need to add these types in config.json:
> "exception_dict": {"MY_STRUCT_PTR": "c_void_p"},

In a real project of the author, the dictionary is:
>"exception_dict": {"MCESD_DEV_PTR": "c_void_p", "MZD_PVOID": "c_void_p", "MZD_DEV_PTR":  "c_void_p", "Device_Handle_t": "c_void_p"},

Other parameters in config.json are optional to change. You can see the comments in config.json.

#### Notice
Function prefix is necessary in the current version... Though this is a critical limitation...

Anyway, you need that function prefix to generate the dll files.

#### How to run
Open an IDE and run autogen.py. Watch the logs to check if there are any errors. If not, everything is done.
