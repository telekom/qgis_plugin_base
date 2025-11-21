# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.core import QgsLocatorFilter, QgsLocatorResult, QgsMessageLog, Qgis


class BaseLocatorFilter(QgsLocatorFilter):
    """ This is used to add functions/searchable stuff to the QGIS search line edit (bottom left).
        Attributes from
         https://github.com/qgis/QGIS/blob/master/src/core/locator/qgslocatorfilter.h
        for all attributes/members/functions to be implemented.

        See in `ModuleBase`.`install_filter` for more information.
    """

    def __init__(self, iface):
        # you REALLY REALLY have to save the handle to iface, else segfaults!!
        self.iface = iface
        super(QgsLocatorFilter, self).__init__()

    def name(self):
        return self.__class__.__name__

    def clone(self):
        return self.__class__(self.iface)

    def displayName(self):
        """ Reimplemented example from c++ inheritance.
            Overwrite this method for your filters!
        """
        return self.name() + " - sad man"

    def prefix(self):
        """ Reimplemented example from c++ inheritance.
            Overwrite this method for your filters!
        """
        return 'baseplugin'

    def fetchResults(self, search, context, feedback):
        """ Reimplemented example from c++ inheritance.
            Overwrite this method for your filters!
        """

        if len(search) < 2:
            return

        result = QgsLocatorResult()
        result.filter = self
        result.displayString = f"Test result for {self.name()}"
        # use the json full item as userData, so all info is in it:
        result.userData = "HERE IS NOTHING"

        self.resultFetched.emit(result)

    def triggerResult(self, result):
        """ Reimplemented example from c++ inheritance.
            Overwrite this method for your filters!
        """
        self.info("UserClick: {}".format(result.displayString))
        # Newer Version of PyQT does not expose the .userData (Leading to core dump)
        # Try via get Function, otherwise access attribute
        try:
            data = result.getUserData()
        except AttributeError:
            data = result.userData

        self.iface.messageBar().pushSuccess("WORKED", data)

    def info(self, msg=""):
        QgsMessageLog.logMessage('{} {}'.format(self.__class__.__name__, msg), self.__class__.__name__, Qgis.Info)
