import PySimpleGUI as sg
import os
import shutil
import json

header_files = []


def make_window(theme):
    sg.theme(theme)
    menu_def = [['&File', ['&Import settings from config.json', '&Exit']],
                ['&Help', ['&About', '&user guide']]]
    right_click_menu_def = [[], ['Versions', 'Exit']]

    settings_layout = [
        # [sg.Checkbox('split the output into multiple files', default=False, k='-CB-')],
        # [sg.Combo(values=('Combo 1', 'Combo 2', 'Combo 3'), default_value='Combo 1', readonly=False, k='-COMBO-'),
        #  sg.OptionMenu(values=('Option 1', 'Option 2', 'Option 3'), k='-OPTION MENU-'), ],
        [sg.Text("Files to convert")],
        [sg.Listbox(values=header_files,
                    size=(20, 10),
                    key='-header files-',
                    expand_x=True,
                    enable_events=True)],
         [sg.Button("Add Folder"), sg.Button("Add File"), sg.Button("Delete")],
         [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROGRESS BAR-'), sg.Button('Convert')]]
    logging_layout = [[sg.Text("Anything printed will display here!")],
                      [sg.Multiline(size=(60, 15), font='Courier 8', expand_x=True, expand_y=True, write_only=True,
                                    reroute_stdout=True, reroute_stderr=True, echo_stdout_stderr=True, autoscroll=True,
                                    auto_refresh=True)]
                      ]
    theme_layout = [[sg.Listbox(values=sg.theme_list(),
                                size=(20, 12),
                                key='-THEME LISTBOX-',
                                enable_events=True)],
                    [sg.Button("Set Theme")]]

    layout = [[sg.MenubarCustom(menu_def, key='-MENU-', font='Courier 15', tearoff=True)]]
    layout += [[sg.TabGroup([[sg.Tab('Basic', settings_layout),
                              sg.Tab('Theming', theme_layout),
                              sg.Tab('Debug log', logging_layout)]], key='-TAB GROUP-', expand_x=True, expand_y=True),

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

txt_user_guide = "1.Add files or folders to convert\n" \
                 "2. Click Convert Button\n" \
                 "3. Check the log and results in the output folder\n"


window = make_window(sg.theme("BluePurple"))

# This is an Event Loop
while True:
    event, values = window.read(timeout=100)
    if event in (None, 'Exit'):
        break
    elif event == 'About':
        sg.popup(txt_about, keep_on_top=True)
    elif event == 'Import settings from config.json':
        config_json = sg.popup_get_file('Choose your file', keep_on_top=True)
        shutil.copy(src=config_json, dst='config.json')
    elif event == 'user guide':
        sg.popup(txt_user_guide, keep_on_top=True)
    elif event == 'Convert':
        progress_bar = window['-PROGRESS BAR-']
        for i in range(100):
            progress_bar.update(current_count=i + 1)
        sg.popup("Conversion done.", keep_on_top=True)
    elif event == "Add Folder":
        folder = sg.popup_get_folder('Choose your folder', keep_on_top=True)
        header_files.append(folder)
        window['-header files-'].update(header_files)
    elif event == "Add File":
        files = sg.popup_get_file('Choose your file', keep_on_top=True)
        header_files.append(files)
        window['-header files-'].update(header_files)
    elif event == "Delete":
        item_chosen = values['-header files-'][0]
        header_files.remove(item_chosen)
        window['-header files-'].update(header_files)
    elif event == "Set Theme":
        theme_chosen = values['-header files-'][0]
        window.close()
        window = make_window(theme_chosen)
    elif event == 'Versions':
        sg.popup_scrolled(f'Version=2.0.12', keep_on_top=True, non_blocking=True)

window.close()
exit(0)

