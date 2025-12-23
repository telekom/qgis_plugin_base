# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

from typing import Callable, Optional

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDialog

from .base_class import UiModuleBase
from ..constants import STYLE_SHEET_EDIT_ERROR

FORM_CLASS, _ = UiModuleBase.get_uic_classes(__file__)


class ConfirmationDialog(QDialog, FORM_CLASS):
    """ dialog to display message to user and let him confirm before he can click confirm button
    """
    aborted = pyqtSignal(name="aborted")
    confirmed = pyqtSignal(name="confirmed")

    def __init__(self,
                 window_title: str = "Confirmation Dialog",
                 message: str = "Ich bin ein Platzhaltertext und habe keinerlei Funktion",
                 confirmation_text: str = "Ich habe die Nachricht gelesen und verstanden",
                 abort_but_visible: bool = False,
                 captcha_hint: Optional[str] = None,
                 captcha_solution: Optional[str] = None,
                 parent=None):
        """ Dialog with checkbox clicked to confirm user read message

            :param window_title: Title of dialog window
            :param message: Message displayed where confirmation is needed
            :param confirmation_text: text for checkBox
            :param abort_but_visible: bool if second button (abort) should be visible
            :param captcha_hint: Hint to solve the captcha.
                                 Only valid with provided string value in `captcha_solution`.
            :param captcha_solution: The secret captcha solution (case-sensitive).
                                     Only valid with provided string value in `captcha_hint`.
            :param parent: parent widget for dialog
        """
        QDialog.__init__(self, parent)
        self.setupUi(self)

        # initial setting of title, message and confirmation text
        self.setWindowTitle(window_title)
        self.Label_Message.setText(message)
        self.CheckBox_Confirm.setText(confirmation_text)

        # initial link to confirmation and abort button method, can be exchanged
        self.__confirmation_method = self.__confirmation_given
        self.__abort_method = self.close
        # initial connections
        self.__load_connections()
        # initial setting of button texts
        self.set_confirmation_but_text()
        self.set_abort_but_text()
        # set initial visibility of abort button
        self.set_abort_but_visible(abort_but_visible)
        # word wrap for message label
        self.Label_Message.setWordWrap(True)
        # set captcha data
        self.__captcha_hint = captcha_hint
        self.__captcha_solution = captcha_solution
        if self.__captcha_hint and self.__captcha_solution:
            self.Frame_Captcha.show()
            self.Label_Captcha_Hint.setText(self.__captcha_hint)
        else:
            self.Frame_Captcha.hide()
        # fitting size of window to message size
        self.adjustSize()

        # variable to save if confirmation button was clicked
        self.__confirmed = False

        # initial state of confirmation button
        self.__set_confirmable()

    # region additional init methods
    def __load_connections(self):
        """ load all initial connections needed for dialog
        """
        # button connections
        self.But_Abort.clicked.connect(lambda *_: self.__abort_method())
        self.But_Confirmation.clicked.connect(lambda *_: self.__confirmation_method())
        # connection for checkbox checkstate switch
        self.CheckBox_Confirm.toggled.connect(lambda *_: self.__set_confirmable())
        # load captcha connection
        self.Edit_Captcha.textChanged.connect(lambda *_: self.__set_confirmable())

    def __confirmation_given(self):
        """ initial confirmation method for button, can be exchanged
        """
        self.__confirmed = True
        self.confirmed.emit()
        self.close()

    # endregion additional init methods

    # region methods
    def __set_confirmable(self):
        """ methods to enable / disable confirming button
        """
        # resets style sheet form captcha edit
        self.Edit_Captcha.setStyleSheet("")

        checked = not bool(self.CheckBox_Confirm.checkState())

        # check, if the captcha should be solved or not
        if self.__captcha_hint and self.__captcha_solution:
            # case sensitive compare captcha
            captcha_ok = self.Edit_Captcha.text() == self.__captcha_solution
            if not captcha_ok:
                self.Edit_Captcha.setStyleSheet(STYLE_SHEET_EDIT_ERROR)
        else:
            # no need to solve the captcha
            captcha_ok = True

        self.But_Confirmation.setDisabled(checked or not captcha_ok)

    def set_confirmation_method(self, confirmation_method: Callable):
        """ sets method called when confirmation button is clicked, if exchange is needed

            :param confirmation_method: Callable to set new method to confirmation button clicked
        """
        self.__confirmation_method = confirmation_method

    def set_abort_method(self, abort_method: Callable):
        """ sets method called when abort button is clicked, if exchange is needed

            :param abort_method: Callable to set new method to abort button clicked
        """
        self.__abort_method = abort_method

    def set_confirmation_but_text(self, text: str = "Ok"):
        """ sets button text for confirmation button

            :param text: str button text
        """
        self.But_Confirmation.setText(text)
        self.adjustSize()

    def set_abort_but_text(self, text: str = "Abbrechen"):
        """ sets button text for aborting button

            :param text: str button text
        """
        self.But_Abort.setText(text)
        self.adjustSize()

    def set_message_text(self, message: str = ""):
        """ sets message text for dialog

            :param message: str message displayed in dialog
        """
        self.Label_Message.setText(message)
        self.adjustSize()

    def set_window_title(self, new_title: str):
        """ method to change window title

            :param new_title: str displayed as window title
        """
        self.setWindowTitle(new_title)

    def set_abort_but_visible(self, visible: bool = True):
        """ sets visibility of button for aborting

            :param visible: bool if abort button should be visible
        """
        self.But_Abort.setVisible(visible)

    def is_confirmed(self) -> bool:
        """ returns bool if corfimation button was clicked at least once

            :returns: bool if confirmation button was clicked at least once
        """
        return self.__confirmed

    def reset_confirmation(self):
        """ resets bool if confirmation button was clicked at least once
        """
        self.__confirmed = False

    # endregion methods

    # region class method
    @classmethod
    def confirm_message(cls,
                        window_title: str = "Confirmation Dialog",
                        message: str = "Ich bin ein Platzhaltertext und habe keinerlei Funktion",
                        confirmation_text: str = "Ich habe die Nachricht gelesen und verstanden",
                        confirmation_but_text: str = "Ok",
                        abort_but_text: str = "Abbrechen",
                        abort_but_visible: bool = False,
                        captcha_hint: Optional[str] = None,
                        captcha_solution: Optional[str] = None,
                        parent=None) -> bool:
        """ runs dialog and returns bool True if confirmation button was clicked or False if aborted

            :param window_title: Title of dialog window
            :param message: Message displayed where confirmation is needed
            :param confirmation_text: text for checkBox
            :param confirmation_but_text: text on confirmation button
            :param abort_but_text: text on abort button
            :param abort_but_visible: bool if second button (abort) should be visible
            :param captcha_hint: Hint to solve the captcha.
                                 Only valid with provided string value in `captcha_solution`.
            :param captcha_solution: The secret captcha solution (case-sensitive).
                                     Only valid with provided string value in `captcha_hint`.
            :param parent: parent widget for dialog
            :returns: bool if confirmation button was clicked (True) or aborted (False)
        """
        # variable to store confirmation
        confirmation = False

        def set_confirmation():
            """ changes variable of outer function, connected to signal of confirmation button
            """
            nonlocal confirmation
            confirmation = True

        # instantiate class with given parameters to run dialog
        dialog_window = cls(window_title=window_title,
                            message=message,
                            confirmation_text=confirmation_text,
                            abort_but_visible=abort_but_visible,
                            captcha_hint=captcha_hint,
                            captcha_solution=captcha_solution,
                            parent=parent)

        dialog_window.set_confirmation_but_text(confirmation_but_text)
        dialog_window.set_abort_but_text(abort_but_text)

        dialog_window.confirmed.connect(set_confirmation)
        dialog_window.exec_()

        return confirmation

    # endregion class method

    # region closing methods
    def reject(self):
        """ prevent ESC key of user closing window
        """
        return

    def closeEvent(self, event):
        """ cleanup before closing
        """
        self.aborted.emit()
        event.accept()

    # endregion closing methods
