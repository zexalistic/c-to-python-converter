## Generate C to python wrapper automatically
This tool mainly focus on generating ctypes python wrapper on embedded C project.
The major idea of this tool is to parse header/C files and grasp the definition of functions and customized variable types, then rewrite them in Ctypes style.

#### How to use
+ Build dll files(Optional, if you want to run testcases)
+ Edit config.json
+ Run autogen.py

#### Output
+ wrapper.py : the python wrapper of C functions written in ctypes style
+ Testcase_all.py: simple auto-generated testcases templates. You had better check it before running.

#### How to use Ctypes Wrapper
You need to compile the C project and generate a dynamic lib(.dll in windows).
Cpython support loading dll files while running C and will call the C function according to its name.
This wrapper is an interface to wrap those C function into a python function.

#### Limitation
1. Do not support #ifdef #endif...
2. Do not support nested citation. e.g. the parameter of a function pointer is another function pointer
3. Do not support union at present...
4. Only support simplest macros like this: #define VAR_NAME 1
5. Parameter of function can not be void...
6. Only support typedef enum. not support direct definition of enum type.
7. Parenthesis may affect the parsing result, e.g. ((a)) may have a different parsing result with a
 

#### For more Information
About what can be parsed, see the comments in Sample\sample.h.

## Detailed User Guide 
#### How to edit config.json
You want to wrap the function *hello_world* in Samples\main.c. That function is defined in **Samples\main.h**. You complied your C files and put the result in **Samples\samples.dll**. Thus, you need to write below in config.json:
> "dll_path": "Samples\\\samples.dll",
"h_files_to_parse": ["Samples\\\main.h"],

If some functions are defined in Samples\main.c, you need to add:
> "c_files_to_wrap": ["Samples\\\main.c"],

This is optional, so it is commented by default. Functions only defined in header files are preferred.

You opened **main.h** and found there are customized variable types *MY_BOOL* and *MY_INT*. They are defined in **Samples\sample.h**. Thus, you need to write below in config.json:
> "h_files_to_wrap": ["Samples\\\sample.h"],

You found there is a prefix before function *hello_world* and there is no prefix before *hello_world_2*. This prefix is usually necessary as a sign to export the function to dll files. Thus, you need to add this prefix in config.json; leave it blank if there is no prefix.
> "func_header": "FUNC_PREFIX",

Some hardware engineers prefer to add an empty macro before function parameters to map a real pin. E.g. 
 FUNC_PREFIX MY_INT hello_world(IN MY_BOOL something);
 If any, you need to declare them in config.json. If not, just ignore. This is commented by default.
 > "func_param_decorator": "IN|OUT|INOUT",

Since *typedef int MY_INT;* is not parsed (This is a limitation of my parser), you need to manually add these definations in config.json. I have aleady written some common types, so you need to append it as in samples:
> 	"basic_type_dict": {"int8_t": "c_int8", "int16_t": "c_int16", "int32_t": "c_int32", "int64_t": "c_int64", "uint8_t": "c_uint8", "uint16_t": "c_uint16", "uint32_t": "c_uint32", "uint64_t": "c_uint64", "unsigned int": "c_uint", "int": "c_int", "float": "c_float", "double": "c_double", "char": "c_char", "const char": "c_char", "unsigned char": "c_ubyte", "MY_INT": "c_int"},  

The device handler in hardware is complex and usually wrapped separatedly, so I leave a special entry for these types. The parser will bypass these types and not recognize them as a common structure pointer. You need to add these types in config.json:
> "exception_dict": {"MY_STRUCT_PTR": "c_void_p"},

In a real project of the author, the dictionary is:
>"exception_dict": {"MCESD_DEV_PTR": "c_void_p", "MZD_PVOID": "c_void_p", "MZD_DEV_PTR":  "c_void_p", "Device_Handle_t": "c_void_p"},

Other parameters in config.json are optional to change. You can see the comments in config.json.

#### How to run
Open an IDE and run autogen.py. Watch the logs to check if there are any errors. If not, everything is done.