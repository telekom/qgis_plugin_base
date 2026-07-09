# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

import argparse
from lxml import etree

from pathlib import Path
from re import compile, Pattern
from typing import Dict, Union, Optional, List, Tuple

Rules: Dict[str, Dict[str, Pattern | None] | Dict[str, Pattern | Dict[str, Tuple[bool, Pattern]]]] = {
    "QCalendarWidget": {
        'names': compile(r"^Calendar$"),
        'options': None
    },
    "QComboBox": {
        'names': compile(r"^(DrD|Combo)(_[A-Za-z_]+)?"),
        'options': {
            # key: xpath starting at combo box tree element
            # value: (necessary=True, pattern)
            './property[@name="sizeAdjustPolicy"]/enum': (True, compile(r"QComboBox::"
                                                                        "(AdjustToMinimumContentsLengthWithIcon"
                                                                        "|AdjustToMinimumContentsLength)"))
        }
    },
    "QCheckBox": {
        'names': compile(r"^CheckBox(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QDateEdit": {
        'names': compile(r"^(DateEdit|Date_Edit)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QFrame": {
        'names': compile(r"^(frame(_\d+)?|MainWidget|(Frame|Module)(_[A-Za-z_]+)?)$"),
        'options': None
    },
    "QGroupBox": {
        'names': compile(r"^(groupBox(_\d+)?|(Group|GroupBox)(_[A-Za-z_]+)?)$"),
        'options': None
    },
    "QLabel": {
        'names': compile(r"^(label(_\d+)?|(Lab|Label)(_[A-Za-z_]+)?).*$"),
        'options': None
    },
    "QLineEdit": {
        'names': compile(r"^(Edit|Line_Edit|LineEdit|Input)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QListView": {
        'names': compile(r"^(List|ListView)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QListWidget": {
        'names': compile(r"^(List|ListWidget)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QProgressBar": {
        'names': compile(r"^(Progress)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QPushButton": {
        'names': compile(r"^(But|Btn)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QRadioButton": {
        'names': compile(r"^(Radio|RadioBtn|RadioBut)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QScrollArea": {
        'names': compile(r"^scrollArea|(ScrollArea|Scroll)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QSpinBox": {
        'names': compile(r"^(Spin|SpinBox)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTabWidget": {
        'names': compile(r"^(tabWidget(_\d+)?|Tab|TabWidget)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTableView": {
        'names': compile(r"^(Table|TableView)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTableWidget": {
        'names': compile(r"^(Table|TableWidget)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTextEdit": {
        'names': compile(r"^(TextEdit|Text_Edit)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QPlainTextEdit": {
        'names': compile(r"^(PlainEdit)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTimeEdit": {
        'names': compile(r"^(TimeEdit)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QToolButton": {
        'names': compile(r"^(But|Btn)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTreeView": {
        'names': compile(r"^(Tree|TreeView)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QTreeWidget": {
        'names': compile(r"^(Tree|TreeWidget)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QWidget": {
        # some of this object names are default values from Qt Designer
        'names': compile(r"^(widget(_\d+)?|Form|dockWidgetContents|centralwidget|MainWidget|Widget(_[A-Za-z_]+)?)$"),
        'options': None
    },
    "Line": {
        # simple line element
        'names': compile("^(Line|LineSpacer|Line_Spacer)(_[A-Za-z_]+)?$"),
        'options': None
    },
    "QGraphicsView": {
            'names': compile("^(Graphics|GraphicsView)(_[A-Za-z_]+)?$"),
            'options': None
    },

    # qgis classes
    "QgsFileWidget": {
        # some of this object names are default values from Qt Designer
        'names': compile(r"^(FileEdit|File(_[A-Za-z_]+)?)$"),
        'options': None
    },
}


def validate_file(input_file: Union[Path, str], output_file: Optional[Union[Path, str]] = None) -> Optional[Path]:
    """ Tests ui file with defined QWidgets via Qt Designer.
        Overwrites existing files.

        Tests:
        - object naming
        - attributes set

    :param input_file: input ui file
    :param output_file: output file, defaults to "input.ui" -> "input_result.md"
    :return: created file, defaults to None
    """

    final_result = []

    path = Path(input_file)

    if not output_file:
        # no output file defined, fall back to default
        # input: "C:/Users/Desktop/menu.ui"
        # output: "C:/Users/Desktop/menu_result.md"
        output_file = path.parent / Path(path.name.replace(".ui", "_result.md"))
    else:
        # using given output path
        output_file = Path(output_file)

    if output_file.is_dir():
        # if output path is a directory
        # output before: "C:/Users/Desktop/output"
        # output after: "C:/Users/Desktop/output/menu_result.md"
        output_file = output_file / Path(path.name.replace(".ui", "_result.md"))

    if not output_file.parent.is_dir():
        # create directories
        output_file.parent.mkdir(parents=True)

    # read ui/xml
    tree = etree.parse(str(path))
    for widget in tree.findall(".//widget"):

        result = []

        # read xml values from element
        class_ = widget.attrib['class']
        name = widget.attrib['name']

        rule = Rules.get(class_, None)
        if rule is None:
            # no rule defined
            continue

        # skip direct child from parents, when it is a QWidget
        parents = ["QScrollArea", "QTabWidget"]
        parent = widget.getparent()
        is_scroll_area_child = False
        if parent.tag == "widget":
            is_scroll_area_child = parent.attrib['class'] in parents
            is_scroll_area_child = is_scroll_area_child and class_ == "QWidget"

        if is_scroll_area_child:
            continue

        names = rule.get('names')
        if names is not None and names:

            # ignore the name check?
            node_ignore_name_check = widget.find(".//property[@name='ignore_ui_file_validation_object_name']")
            ignore_name_check = False
            if node_ignore_name_check is not None and node_ignore_name_check.getparent() is widget:
                ignore_name_check = True
            # test naming rule (regex pattern)
            if not ignore_name_check and names.search(name) is None:
                result.append(f"{name} is not valid, expecting pattern {names.pattern}")
            elif ignore_name_check:
                ...

        options = rule.get('options')
        if options is not None and options:
            # test xpath option inside this element and test "element.text" with regex pattern
            for option_path, option_value in options.items():
                # needed/optional option?
                # regex pattern
                option_necessary, option_pattern = option_value

                element_option = widget.find(option_path)
                if element_option is None and option_necessary:
                    # option not set, but necessary
                    result.append(f"{option_path}: missing option {option_pattern.pattern}")
                    continue

                if option_pattern.search(element_option.text) is None:
                    # option is set, but wrong
                    result.append(f"{option_path}: wrong option set, expecting {option_pattern.pattern}")

        if result:
            # prepare result for file result
            result.insert(0, f"### {name} ({class_})")
            result.append("-----")
            result.append("\n")
            final_result.append(result)

    # sort result
    final_result.sort()

    if final_result:
        # write to output file and returns the file path

        with output_file.open("a+", encoding="utf-8") as file:
            file.write(f"# {input_file}\n\n")
            for result in final_result:
                file.write('\n\n'.join(result))
        return output_file

    return None


def validate_folder(folder_input: Union[Path, str],
                            folder_output: Union[Path, str]) -> List[Path]:
    """ Tests all .ui-files (recursive search) in given directory.
        File test is done with `validate_file`.

    :param folder_input: input ui file
    :param folder_output: output file, defaults to "input.ui" -> "input_result.md"
    :return: created file paths
    """
    files = []
    path = Path(folder_input)
    for x in sorted(path.glob('**/*.ui')):
        result = validate_file(x, folder_output)
        if result:
            files.append(result)

    return files


def run_from_terminal():
    """ Entry point for running the UI file validator from the command line.

        Parses command-line arguments for input and output paths.
        If not provided as arguments, prompts the user interactively.

        - If the input path is a file, validates that single UI file.
        - If the input path is a directory, recursively validates all UI files found within it.

        Arguments:
            -input: Path to a .ui file or a directory containing .ui files (required).
            -output: Path to the output result file or directory (optional).
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-input", dest="input", type=str, required=False, default=None)
    parser.add_argument("-output", dest="output", type=str, required=False, default=None)
    args = parser.parse_args()

    input_ = args.input if args.input else input("-input(needed)=")
    output = args.output if args.output else input("-output(optional)=")

    path = Path(input_)
    if path.is_file():
        validate_file(input_, output)
    elif path.is_dir():
        validate_folder(input_, output)

        if Path(output).is_file():
            print(f"result file {output} created")
        else:
            print(f"UI files ok.")


if __name__ == "__main__":
    run_from_terminal()
