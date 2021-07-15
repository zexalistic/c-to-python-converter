## Automatically converting C code to python using ctypes lib

#### Input
+ **sample/** : folder which contains your C code
+ **config.json** : settings of this tool


#### <span id="output"> Output </span>
+ **enum_class.py** : Conversion result of C Enumeration type
+ **structure_class.py** : Conversion result of C Structure and Union type
+ **c_arrays.py** : Conversion result of C large arrays. (Optional, turned off in default)  
+ **wrapper.py** : Conversion result of C functions
+ **testcase.py**: Auto-generated testcases

#### How to use
See [Detailed User Guide](#DUG)


#### Limitation
1. Do not support other preprocessor commands except for "#define"
   
2. Do not support nested citation or definition. 
   
   e.g. a is a structure whose member is another structure; b is an alias of c which is an alias of d.
   
3. Regard all 'void' as 'int' at present version.
   
4. Parenthesis may affect the parsing result, e.g. ((x)) may have a different parsing result with x

 
#### TO-DO List in next version
1. No parameter
2.#ifdef #notdefine
3. Add additional debugging information   
4. C function parser. {} within {}

#### Brief introduction of ctypes
ctypes is a standard library of python to connect C with python. You need to first generate a dll/so file 
from C project and use ctypes.CDLL to call those C functions. Since the data structure in C and python are 
different, you need a wrapper as an interface to make the API more "pythonic". That's why I develop this 
wrapper auto-generator.

#### For more Information
About what can be parsed, see the comments in Sample\sample.h.
It supports the conversion of structure, union, enumerate, typedef... which already meets the need of common project.
It removes the C commands and processes the C blackslash at the end of each line.
It substitutes all macros(except for function header) before parsing.

Python Ctypes document:
https://docs.python.org/3/library/ctypes.html

This blog introduces how to use python ctypes:
https://www.cnblogs.com/night-ride-depart/p/4907613.html

## <span id="DUG">Detailed User Guide </span>
#### How to use the tool step by step
+ Replace **sample/** with your own project
+ Your project folder should contains:
    * DLL file generated from your C project
    * Dependent header files containing your customized data structure
    * Files containing functions you want to convert
+ [Add function prefix](#add_pre)       
+ [Edit config.json](#edit_config) 
+ Run autogen.py
+ Check error messages.
  
  <font size=2>*You may forget to add some necessary dependent header files so that the parser is unable to 
  recognize your customized data structure. Add them in config.json and run autogen.py again.*</font>
  
+ Check your result in [output files](#output).

#### <span id="edit_config">How to edit config.json </span>
+ Add DLL path. 
  
    Use your own file name. If you do not need [testcases,py](#output), skip this step.
    > "dll_path": "your_prj_folder\\dll_yours.dll",

+ Add dependent header file list. 
  
    These files contain all your customized data structure. [structure_class.py](#output) and
  [enum_class.py](#output) are  generated from these files. Customized types such as "typedef my_int int;" 
  are also parsed from these files. 
  
  If there is any unrecognized type due to lack of dependent files, the parser will skip those types and
  not parse them. Thus, you may either replace those types manually in the [output files](#output) (not recommned)
   or update the file list and run again.
     > "dependent_header_file_list": ["your_prj_folder\\\a.h", ""your_prj_folder\\\lib\\\\*.h""],

+ Add file list containing the functions your want to convert.

  We **STRONGLY** recommend you to use header files which contain the definition of functions, because they are cleaner.

  > "h_files_to_wrap": ["your_prj_folder\\\a.h", "your_prj_folder\\\b.h"],
  
  > "c_files_to_wrap": ["your_prj_folder\\\d.c", "your_prj_folder\\\e.c"],


+ <span id="add_pre">Add function prefix.</span>
  
  We use this as a sign to indicate which function to convert.

  Since you need something like "__declspec(dllexport)" to generate DLLs. 
  It is common to use a macro to replace "__declspec(dllexport)"; you can use this macro as function prefix. 
  
  You can also define an empty macro as the function prefix.
  
  > "func_header": "YOUR_FUNC_PREFIX",
  
+ Add exception dictionary.(Optional)
  
  For some complex structures, such as a device handler of a hardware device, you may just want to leave an interface of 
  void pointer and define that structure in other place. In this case, you should edit the exception dictionary here.
  
  >"exception_dict": {"Device_Handle_t": "c_void_p"},
  

+ Advanced Function (Optional)
  
   See source code or config.json by yourself.




