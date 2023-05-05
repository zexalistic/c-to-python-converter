"""
    @usage: automatically generate Cpython wrapper file according to header files
    @date: 2021-03-05
    @author: Yihao Liu
    @email: lyihao@marvell.com
    @python: 3.7
    @latest modification: 2023-05-03
    @version: 2.1.10
    @update: add vcxproj import
"""
import PySimpleGUI as sg
import json
from parse import Parser
import xml.dom.minidom


def import_json(config_json: str, config: dict):
    with open(config_json, 'r') as fp:
        env = json.load(fp)
    config["exception_dict"].update(env.get('exception_dict', dict()))
    config["header_files"].extend(env.get('header_files', list()))
    config["predefined_macro_dict"].update(env.get('predefined_macro_dict', dict()))
    config["project_folders"].extend(env.get('project_folders', list()))
    config["is_multiple_file"] = env.get('is_multiple_file', False)


def parse_xml(xml_name: str, yes_no: str):
    """
    @Param xml_name: name of xml file
    @Param yes_no: Yes for debug, No for release
    """
    DOMTree = xml.dom.minidom.parse(xml_name)
    collection = DOMTree.documentElement
    item_defs = collection.getElementsByTagName("ItemDefinitionGroup")
    condition_dict = {'Yes': 'Debug', 'No': 'Release'}

    for item_def in item_defs:
        if len(item_def.attributes):
            # let's assume there is only one condition tag in
            # <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
            # If there are more, we need to change the code here.
            # We check debug and release
            condition_tag = item_def.attributes.items()[0]
            if condition_dict[yes_no] in condition_tag[1]:
                pre_def = item_def.getElementsByTagName('PreprocessorDefinitions')[0]
                pre_def_str_list = pre_def.firstChild.nodeValue.split(';')
                pre_def_str_list.pop()  # The last one is %(PreprocessorDefinitions)
                for pre_def in pre_def_str_list:
                    if '=' in pre_def:
                        macro_key = pre_def.split('=')[0]
                        macro_value = pre_def.split('=')[1]
                    else:
                        macro_key = pre_def
                        macro_value = ''
                    config["predefined_macro_dict"].update({macro_key: macro_value})


def make_window(theme):
    sg.theme(theme)
    menu_def = [['&File', ['&Save settings as config.json', '&Import settings from vcxproj', '&Exit']],
                ['&Help', ['&About', '&user guide']]]
    right_click_menu_def = [[], ['Versions', 'Exit']]

    settings_layout = [
        [sg.Text("Files and folders to convert")],
        [sg.Listbox(values=config["header_files"] + config["project_folders"],
                    size=(20, 5),
                    key='-files and folders-',
                    expand_x=True,
                    enable_events=True)],
         [sg.Button("Add Folder"), sg.Button("Add File"), sg.Button("Delete"), sg.Button("Clear")],
         [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROGRESS BAR-'), sg.Button('Convert', button_color=('black', 'white'))]]

    advance1_layout = [
            [sg.Text("Pre-defined macros to set:")],
            [sg.Text("User defined macros"), sg.Text("  Value of macros")],
            [sg.Listbox(values=config["predefined_macro_dict"].keys(),
                        size=(18, 5),
                        key='-macro keys-',
                        expand_x=False,
                        enable_events=True),
             sg.Listbox(values=config["predefined_macro_dict"].values(),
                        size=(18, 5),
                        key='-macro values-',
                        expand_x=False,
                        enable_events=True),
             ],
             [sg.Button("Add Macro"), sg.Button("Delete Macro"), sg.Button("Clear Macros")]
        ]
    advance2_layout = [
            [sg.Text("Enviroment variables to set:")],
            [sg.Text("Skipped Variable"), sg.Text("     Value of variable")],
            [sg.Listbox(values=config["exception_dict"].keys(),
                        size=(18, 5),
                        key='-skipped keys-',
                        expand_x=False,
                        enable_events=True),
             sg.Listbox(values=config["exception_dict"].values(),
                        size=(18, 5),
                        key='-skipped values-',
                        expand_x=False,
                        enable_events=True),
             ],
            [sg.Button("Add Var"), sg.Button("Delete Var"), sg.Button("Clear Vars")]
         ]

    layout = [[sg.MenubarCustom(menu_def, key='-MENU-', font='Courier 10', tearoff=True)]]
    layout += [[sg.TabGroup([[sg.Tab('Basic', settings_layout),
                              sg.Tab('Macro', advance1_layout),
                              sg.Tab('Var', advance2_layout),
                              ]], key='-TAB GROUP-', expand_x=True, expand_y=True)
                ]]
    layout[-1].append(sg.Sizegrip())
    window = sg.Window('C to python wrapper', layout, right_click_menu=right_click_menu_def,
                       right_click_menu_tearoff=True, grab_anywhere=True, resizable=True, margins=(0, 0),
                       use_custom_titlebar=True, finalize=True, keep_on_top=True)
    window.set_min_size(window.size)
    return window


txt_about = \
    'This project converts C APIs to python classes, which enables programmers to use and test the C APIs in python.\n\
The basic idea is to parse variable types, functions, and their corresponding parameters from header files, \
and rewrite them as python *ctypes* classes. \
When the number of class is tremendous, we need this tool to do it automatically.\n\
ctypes is a standard python library which is used to call C codes. \
The C code is firstly compiled as a dynamic library(*.dll), and then is imported as a python class. \
Users are able to call the C functions from that class. \
For details, please refer to below websites.\n\
Python Ctypes document:\n\
https://docs.python.org/3/library/ctypes.html\n\
This blog introduces how to use python ctypes:\n\
https://www.cnblogs.com/night-ride-depart/p/4907613.html\n'

txt_user_guide = "1. Add files or folders to convert\n" \
                 "2. Click Convert Button\n" \
                 "3. Check the log and results in the output folder\n"

if __name__ == '__main__':
    config = dict()
    with open('config.json', 'r') as fp:    # load previous configuration
        config = json.load(fp)

    window = make_window(sg.theme("TealMono"))
    # The four lines below are for bug removing
    window['-macro keys-'].update(config["predefined_macro_dict"].keys())
    window['-macro values-'].update(config["predefined_macro_dict"].values())
    window['-skipped keys-'].update(config["exception_dict"].keys())
    window['-skipped values-'].update(config["exception_dict"].values())

    # This is an Event Loop
    while True:
        event, values = window.read(timeout=100)
        if event in (None, 'Exit'):
            break
        elif event == 'About':
            sg.popup(txt_about, keep_on_top=True)
        elif event == 'Save settings as config.json':
            with open('config.json', 'w') as fp:
                json.dump(config, fp, indent=4)
        elif event == 'Import settings from vcxproj':
            xml_name = sg.popup_get_file('Select vcxproj file', keep_on_top=True)
            yes_no = sg.popup_yes_no('For "Debug" settings in project click yes, for "Release" settings in project click no', keep_on_top=True)
            parse_xml(xml_name, yes_no)
            window['-macro keys-'].update(config["predefined_macro_dict"].keys())
            window['-macro values-'].update(config["predefined_macro_dict"].values())
        elif event == 'user guide':
            sg.popup(txt_user_guide, keep_on_top=True)
        elif event == 'Convert':
            progress_bar = window['-PROGRESS BAR-']
            parser = Parser()
            parser.env = config
            parser()
            with open('config.json', 'w') as fp:
                json.dump(config, fp, indent=4)
            sg.popup("Please check debug.log.", keep_on_top=True)
        elif event == "Add Folder":
            folder = sg.popup_get_folder('Choose your folder', keep_on_top=True)
            if folder:
                config["project_folders"].append(folder)
                window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Add File":
            files = sg.popup_get_file('Choose your file', keep_on_top=True)
            if files:
                config["header_files"].append(files)
                window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Add Macro":
            macro_key = sg.popup_get_text('Input the Macro name', keep_on_top=True)
            if macro_key:
                macro_value = sg.popup_get_text('Input the Macro value', keep_on_top=True)
                if macro_value is None:
                    macro_value = ''
                config["predefined_macro_dict"].update({macro_key: macro_value})
                window['-macro keys-'].update(config["predefined_macro_dict"].keys())
                window['-macro values-'].update(config["predefined_macro_dict"].values())
        elif event == "Add Var":
            var_key = sg.popup_get_text('Input the skipped variable name', keep_on_top=True)
            if var_key:
                var_value = sg.popup_get_text('Input the skipped variable value', keep_on_top=True)
                if var_value is None:
                    var_value = ''
                config["exception_dict"].update({var_key: var_value})
                window['-skipped keys-'].update(config["exception_dict"].keys())
                window['-skipped values-'].update(config["exception_dict"].values())
        elif event == "Delete":
            item_chosen = values['-files and folders-'][0]
            if item_chosen in config["header_files"]:
                config["header_files"].remove(item_chosen)
            else:
                config["project_folders"].remove(item_chosen)
            window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Delete Macro":
            item_chosen = values['-macro keys-'][0]
            config["predefined_macro_dict"].pop(item_chosen)
            window['-macro keys-'].update(config["predefined_macro_dict"].keys())
            window['-macro values-'].update(config["predefined_macro_dict"].values())
        elif event == "Delete Var":
            item_chosen = values['-skipped keys-'][0]
            config["exception_dict"].pop(item_chosen)
            window['-skipped keys-'].update(config["exception_dict"].keys())
            window['-skipped values-'].update(config["exception_dict"].values())
        elif event == "Clear":
            config["header_files"] = list()
            config["project_folders"] = list()
            window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Clear Vars":
            config["exception_dict"] = dict()
            window['-skipped keys-'].update(config["exception_dict"].keys())
            window['-skipped values-'].update(config["exception_dict"].values())
        elif event == "Clear Macros":
            config["predefined_macro_dict"] = dict()
            window['-macro keys-'].update(config["predefined_macro_dict"].keys())
            window['-macro values-'].update(config["predefined_macro_dict"].values())
        elif event == 'Versions':
            sg.popup_scrolled(f'Version=2.1.2', keep_on_top=True, non_blocking=True)

    window.close()
    exit(0)

