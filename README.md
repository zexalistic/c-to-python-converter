## Converting C API to python lib

### File structure
+ **prj** : folder which contains the code of your project by default
+ <span id="output">**output**</span>:
    + **enum_class.py** : Conversion result of C Enumeration type
    + **structure_class.py** : Conversion result of C Structure and Union type
    + **python_API.py** : Conversion result of C functions
    + **c_arrays.py** : Conversion result of C large arrays. (Optional, turned off by default)
    + **testcase.py**: Auto-generated testcases (Optional, turned off by default)
+ **main.py** 
+ **config.json** : Advanced settings
+ <span id="debug_log">**debug.log**</span> : Recording debugging information


### How to use
1. Copy your source code into **prj** folder
2. Run main.py
3. Check the result in [output](#output) and [debug_log](#debug_log). 

### What this tool can do
+ Parsing C comment
+ Parsing typedef clause and getting our customized variable types
+ Parsing Array, Enum, Structure, Union
+ Parsing function pointer
+ Sorting the converted APIs and classes according to the order of calling, so that the file is executable
+ Getting the header files' dependency
+ Parsing macros and replace them (* macro function is not ready)
+ Parsing preprocessing clause, such as #ifdef, #if etc.
+ Searching the header files in project folder automatically


### Limitation 
+ **void** is not available in python. They are all regarded as **int**.
   
+ Redundant parenthesis may affect the parsing result, e.g. ((x)) may have a different parsing result with x


### Future work

+ POINTER(void) substitued as c_void_p

+ Add debugging info about which file it belongs to.

+ Add the comment of function before the API

+ \#define as a simple function, such as \#define MAX(a, b) ( (a) > (b) (a) : (b) )
   
+ C function parser. {} within {}

+ Recover file structure of the C project


### Brief introduction of ctypes
ctypes is a standard library of python to connect C with python. You need to first generate a dll/so file 
from C project and use *ctypes.CDLL* to call those C functions. 

__declspec(dllexport) is an internal C prefix which implies this function will be export to dll.

Since the data structure in C and python are different, you need a wrapper as an interface to make the API more "pythonic". That's why I develop this 
wrapper auto-generator.

### For more Information

Python Ctypes document:
https://docs.python.org/3/library/ctypes.html

This blog introduces how to use python ctypes:
https://www.cnblogs.com/night-ride-depart/p/4907613.html


### <span id="edit_config">Manual of config.json </span>

+ Add your header files
  
  These files contain all your customized data structure and APIs. [structure_class.py](#output) and
  [enum_class.py](#output) are  generated from these files. Customized types such as "typedef my_int int;" 
  are also parsed from these files. 
  
  If there is any unrecognized type due to lack of dependent files, the parser will skip those types and
  not parse them. Thus, you may either replace those types manually in the [output files](#output) (not recommned)
   or update the file list and run again.
     > "header_files": ["your_prj_folder\\\a.h", ""your_prj_folder\\\lib\\\\*.h""],
  
  
+ Add exception dictionary.
  
  For some complex structures, such as a device handler of a hardware device, you may just want to leave an interface of 
  void pointer and define that structure in other place. In this case, you should edit the exception dictionary here.
  
  >"exception_dict": {"Device_Handle_t": "c_void_p"},
  

+ Advanced Settings
  
   Edit [config.json](#edit_config) 




