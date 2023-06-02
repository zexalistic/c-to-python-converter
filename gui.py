"""
    @usage: automatically generate Cpython wrapper file according to header files
    @date: 2021-03-05
    @author: Yihao Liu
    @email: lyihao@marvell.com
    @python: 3.7
    @latest modification: 2023-06-03
    @version: 2.1.13
    @update: update gui
"""
import os
import PySimpleGUI as sg
import json
from parse import Parser
import xml.dom.minidom


def parse_xml(xml_name: str, yes_no: str):
    """
    Parse the vcxproj and get the preprocessor definitions
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
        [sg.T('dll name:'), sg.Input(default_text=config["dll_path"], size=(80, 1), key='dll_path')],
        [sg.Text("Files and folders to convert")],
        [sg.Listbox(values=config["header_files"] + config["project_folders"],
                    size=(80, 5),
                    key='-files and folders-',
                    expand_x=True,
                    enable_events=True)],
        [sg.Button("Add Folder"), sg.Button("Add File"), sg.Button("Delete"),
         sg.Button("Clear"), sg.Button('Convert', button_color=('green', 'white'))]]

    advance1_layout = [
            [sg.Text("Preprocessor definitions:")],
            [sg.Listbox(values=config["predefined_macro_dict"].keys(),
                        size=(80, 5),
                        key='-macro keys-',
                        expand_x=False,
                        enable_events=True)],
            [sg.Button("Add Macro"), sg.Button("Delete Macro"), sg.Button("Clear Macros")]
        ]
    advance2_layout = [
            [sg.Text("Manually set the parsing result of variable:")],
            [sg.Listbox(values=config["exception_dict"].keys(),
                        size=(80, 5),
                        key='-skipped keys-',
                        expand_x=False,
                        enable_events=True)],
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
    'email: lyihao@marvell.com\n'

txt_user_guide = "1. Add files or folders to convert\n" \
                 "2. Click Convert Button\n" \
                 "3. Check the log and results in the output folder\n"

blank_config = {"header_files": [], "project_folders": [], "exception_dict": {}, "predefined_macro_dict": {"NULL": "0"}, "dll_path": "Sample.dll"}


def dict_to_list(macro_dict: dict):
    """
    Expand dictionary to a list of ["key0 = value0", "key1 = value1", ...]
    """
    ret = []
    for key, value in macro_dict.items():
        if value:
            ret.append(key + ' = ' + value)
        else:
            ret.append(key)
    return ret


if __name__ == '__main__':
    config = dict()
    if os.path.exists('config.json'):
        with open('config.json', 'r') as fp:    # load previous configuration
            config = json.load(fp)
        if not config.__contains__("dll_path"):
            config["dll_path"] = 'Sample.dll'
    else:
        config = blank_config
        with open('config.json', 'w') as fp:
            json.dump(config, fp, indent=4)

    window = make_window(sg.theme("TealMono"))
    # The four lines below are for bug removing
    window['-macro keys-'].update(dict_to_list(config["predefined_macro_dict"]))
    window['-skipped keys-'].update(dict_to_list(config["exception_dict"]))

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
            if xml_name:
                parse_xml(xml_name, yes_no)
                window['-macro keys-'].update(dict_to_list(config["predefined_macro_dict"]))
        elif event == 'user guide':
            sg.popup(txt_user_guide, keep_on_top=True)
        elif event == 'Convert':
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
                window['-macro keys-'].update(dict_to_list(config["predefined_macro_dict"]))
        elif event == "Add Var":
            var_key = sg.popup_get_text('Input the skipped variable name', keep_on_top=True)
            if var_key:
                var_value = sg.popup_get_text('Input the skipped variable value', keep_on_top=True)
                if var_value is None:
                    var_value = ''
                config["exception_dict"].update({var_key: var_value})
                window['-skipped keys-'].update(dict_to_list(config["exception_dict"]))
        elif event == "Delete":
            item_chosen = values['-files and folders-'][0]
            if item_chosen in config["header_files"]:
                config["header_files"].remove(item_chosen)
            else:
                config["project_folders"].remove(item_chosen)
            window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Delete Macro":
            item_chosen = values['-macro keys-'][0]
            if '=' in item_chosen:
                item_chosen = item_chosen.split('=')[0].strip()
            config["predefined_macro_dict"].pop(item_chosen)
            window['-macro keys-'].update(dict_to_list(config["predefined_macro_dict"]))
        elif event == "Delete Var":
            item_chosen = values['-skipped keys-'][0]
            if '=' in item_chosen:
                item_chosen = item_chosen.split('=')[0].strip()
            config["exception_dict"].pop(item_chosen)
            window['-skipped keys-'].update(dict_to_list(config["exception_dict"]))
        elif event == "Clear":
            config["header_files"] = list()
            config["project_folders"] = list()
            window['-files and folders-'].update(config["header_files"] + config["project_folders"])
        elif event == "Clear Vars":
            config["exception_dict"] = dict()
            window['-skipped keys-'].update(dict_to_list(config["exception_dict"]))
        elif event == "Clear Macros":
            config["predefined_macro_dict"] = dict()
            window['-macro keys-'].update(dict_to_list(config["predefined_macro_dict"]))
        elif event == 'Versions':
            sg.popup_scrolled(f'Version=2.1.13', keep_on_top=True, non_blocking=True)

    window.close()
    exit(0)

