<!--
SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# About
Main language of this plugin is German, so some translation from German to English may not be valid.
Per default English will be used. In you QGIS Profile settings you have to activated German locale.

References:
[pyqt-programming/internationalization](https://www.pythonstudio.us/pyqt-programming/internationalization.html)


## Load a translator in PyQt5

### 1. recommended imports
```python
from pathlib import Path
from qgis.PyQt.QtCore import QTranslator, QCoreApplication
```

### 2. load a translation
You have to attach a successfull loaded translator object at something to prevent from collecting from Pythons garbage collector
```python
def load_translator(self):
    translator = QTranslator()
    path = str(Path(__file__).parent / "i18n" / "translation_de.qm")
    if translator.load(path):
        # IMPORT STEP
        # ATTACH IT ON A OBJECT, KEEP IT ALIVE!!!
        # If you don't do it, the the Python garbage collector will come and eat it.
        self.translator = translator
        QCoreApplication.instance().installTranslator(self.translator)
```


## Translation files:
# translation_de.ts
Ui translation from Qt Designer and Qt Linguist.

# .ts file
Individual messages/translations in the xml format expected by lrelease.
[Qt DTD TS File](https://doc.qt.io/qt-5/linguist-ts-file-format.html)
Translations will be avaiable on QgsApplication.
More information on [i18n on riverbankcomputing](https://www.riverbankcomputing.com/static/Docs/PyQt5/i18n.html)

A little assistance menu is available. See translations.py.

# With QGIS Installation on Windows

1. Set up environment variables to find the QGIS installation and dependencies
2. Create or the ts-file from the ui files
3. Open the linguist application from the QGIS installation


## Build ts-file and open linguist app
```
:: QGIS version (installation folder in C:/Program Files
SET "QGIS_VERSION=QGIS 3.34.6"
:: Python paths within the QGIS installation "app" folder
SET "PYTHON_PIP_EXE_PATH=Python312\Scripts\pip3.exe"
SET "PYTHON_PYLUPDATE5_PATH=Python312\Scripts\pylupdate5.exe"
SET "QGIS_INSTALLATION=C:\Program Files\%QGIS_VERSION%"
:: set some QGIS/Python environment variables with a test run
call "%QGIS_INSTALLATION%\bin\python-qgis-ltr.bat" -c "pass"


:: translate the ui files
"%QGIS_INSTALLATION%\apps\%PYTHON_PYLUPDATE5_PATH%" -noobsolete "path/to/ui1.file" "path/to/ui2.file" "path/to/ui3.file" -ts "path/to/file.ts"

:: messages_de.ts use the QGIS Qt Linguist app
"%QGIS_INSTALLATION%\apps\qt5\bin\linguist.exe" "path/to/file.ts"
```

### Qt Linguist Application

With the Linguist application you can translate/edit the ts file and release them as a qm file.
