# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2025 Deutsche Telekom Technik GmbH <f.vonstudsinske@telekom.de>
# SPDX-License-Identifier: GPL-3.0-only

""" Developer tool: pick a Plan[Goo] frame on screen and hot-reload its module
    from disk - without restarting the plugin or logging in again.

    Plan[Goo] builds its UI by replacing placeholder QFrames at runtime with
    module widgets (see ``UiModuleBase.add_ui_module``).  Every replaced widget
    keeps a back-reference to its module via the ``_ui_module_base`` attribute,
    and ``UiModuleBase._get_module`` resolves any child widget back to that
    module.  This tool uses that mechanism to let the developer click a frame,
    re-read its source from disk and swap the live frame for a fresh instance.
"""
import sys
import importlib
import traceback
from typing import List, Optional, Tuple, Type

import sip
from qgis.PyQt.QtCore import Qt, QObject, QEvent, QTimer, QRect, QPoint
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QCursor, QFont
from qgis.PyQt.QtWidgets import (QApplication, QWidget, QFrame, QGridLayout,
                                 QAction)

from ..base_class import ModuleBase, UiModuleBase
from ..base_plugin import Plugin


# ---------------------------------------------------------------------------
# reload helpers
# ---------------------------------------------------------------------------

def reload_module_source(cls: Type[UiModuleBase]) -> Type[UiModuleBase]:
    """ Re-read the source of ``cls`` (and its sibling files) from disk and
        return the freshly compiled class object.

        For feature packages under ``<plugin>.modules.<feature>`` the whole
        package subtree is purged from ``sys.modules`` so that changes in any
        sibling file (e.g. ``megaplan_point_insider.py``) are reflected, not
        only the single file that defines the class.  For everything else only
        the single defining module is reloaded, to avoid purging shared
        infrastructure such as ``submodules.base`` (which would change the
        identity of ``UiModuleBase`` and break the whole plugin).

        Reloading happens before any UI is touched, so a syntax or import error
        in the edited code aborts the reload and leaves the running frame
        untouched.
    """
    module_name = cls.__module__
    module = sys.modules.get(module_name)
    is_package = hasattr(module, "__path__")

    base_pkg = module_name if is_package else module_name.rsplit(".", 1)[0]
    base_parts = base_pkg.split(".")

    # only reload whole feature packages that live under "<plugin>.modules.*"
    if len(base_parts) >= 3 and base_parts[1] == "modules":
        purge_prefix = base_pkg
    else:
        purge_prefix = module_name

    purge_names = [
        name for name in list(sys.modules)
        if name == purge_prefix or name.startswith(purge_prefix + ".")
    ]
    purged_modules = {name: sys.modules[name] for name in purge_names}

    for name in purge_names:
        sys.modules.pop(name, None)

    def restore_purged_modules():
        for name in list(sys.modules):
            if name == purge_prefix or name.startswith(purge_prefix + "."):
                sys.modules.pop(name, None)
        sys.modules.update(purged_modules)

    try:
        fresh_module = importlib.import_module(module_name)
    except Exception:
        restore_purged_modules()
        raise

    try:
        return getattr(fresh_module, cls.__name__)
    except AttributeError as exc:
        restore_purged_modules()
        raise AttributeError(
            f"Klasse '{cls.__name__}' wurde nach dem Neuladen nicht in "
            f"'{module_name}' gefunden."
        ) from exc


def _detach_grid_frame_to_placeholder(module: UiModuleBase) -> QFrame:
    """ Replace the module's live frame inside a QGridLayout with an empty
        placeholder QFrame (same objectName, same cell + span) and unload the
        module.

        This mirrors ``UiModuleBase.replace_with_empty_frame`` but locates the
        grid cell via ``indexOf``/``getItemPosition`` instead of scanning every
        cell.  The base-class scan calls ``itemAtPosition(row, col).widget()``
        for every cell and raises ``'NoneType' object has no attribute
        'widget'`` as soon as the grid contains an empty cell or a spacer item -
        which is the normal case (e.g. the asbuilt frame sits at row 9 of a
        sparse grid).

        :return: the empty placeholder frame, registered as ``parent.<name>``
    """
    parent = module.get_parent()
    main_widget = module.MainWidget
    object_name = main_widget.objectName()

    container = main_widget.parent()
    layout = container.layout() if container is not None else None
    if not isinstance(layout, QGridLayout):
        raise NotImplementedError(
            f"Layout '{type(layout).__name__}' wird für das Neuladen nicht "
            f"unterstützt (nur QGridLayout).")

    index = layout.indexOf(main_widget)
    if index < 0:
        raise RuntimeError("Frame-Widget wurde in seinem Layout nicht gefunden.")
    row, column, row_span, col_span = layout.getItemPosition(index)

    frame = QFrame()
    frame.setObjectName(object_name)
    frame.setFrameShape(QFrame.NoFrame)
    frame.setContentsMargins(1, 1, 1, 1)

    layout.removeWidget(main_widget)
    layout.addWidget(frame, row, column, row_span, col_span)
    setattr(parent, object_name, frame)
    main_widget.setParent(None)

    module.unload(self_unload=True)
    return frame


def reload_frame_in_place(module: UiModuleBase) -> UiModuleBase:
    """ Reload ``module`` from disk and replace its live frame with a fresh
        instance, keeping the same parent, dictionary keyword and layout slot.

        :param module: the (UiModuleBase) frame to reload
        :return: the newly created module
    """
    parent = module.get_parent()
    if parent is None:
        raise ValueError("Frame besitzt kein Eltern-Modul und kann nicht "
                         "neu geladen werden.")

    main_widget = getattr(module, "MainWidget", None)
    if main_widget is None or sip.isdeleted(main_widget):
        raise ValueError("Frame besitzt kein gültiges 'MainWidget'.")

    keyword = module.module_name
    use_directly = main_widget is module
    object_name = main_widget.objectName()
    if not object_name:
        raise ValueError("Frame-Widget besitzt keinen objectName und kann "
                         "nicht eindeutig ersetzt werden.")

    # 1) reload source FIRST - a broken edit aborts here, UI stays intact
    fresh_class = reload_module_source(module.__class__)

    # 2) detach the old frame and restore an empty placeholder in its slot
    container = main_widget.parent()
    layout = container.layout() if container is not None else None

    if isinstance(layout, QGridLayout):
        # robust cell lookup (the base-class scan crashes on sparse grids)
        _detach_grid_frame_to_placeholder(module)
    elif layout is not None:
        if use_directly:
            raise NotImplementedError(
                "Das Neuladen eines direkt eingesetzten Moduls wird nur "
                "innerhalb eines QGridLayout unterstützt.")
        module.unload(self_unload=True)
        # the embedded MainWidget survives the module unload -> replace it
        parent.replace_widget_with_widget(getattr(parent, object_name), QFrame())
    else:
        raise NotImplementedError(
            "Der Eltern-Container des Frames besitzt kein Layout und kann "
            "nicht neu geladen werden.")

    placeholder = getattr(parent, object_name, None)
    if placeholder is None or sip.isdeleted(placeholder):
        raise RuntimeError("Platzhalter-Frame konnte nicht wiederhergestellt "
                           "werden.")

    # 3) load the fresh class into the restored placeholder
    return parent.add_ui_module(keyword, placeholder, fresh_class,
                                use_directly=use_directly)


def resolve_module_chain(widget: Optional[QWidget]) -> List[UiModuleBase]:
    """ Return the chain of reloadable UiModuleBase frames for ``widget``,
        ordered from the innermost (the clicked frame) to the outermost
        (stopping before the plugin itself).
    """
    chain: List[UiModuleBase] = []
    if widget is None:
        return chain

    try:
        module = UiModuleBase._get_module(widget)
    except StopIteration:
        return chain

    guard = 0
    while isinstance(module, ModuleBase) and not isinstance(module, Plugin):
        main_widget = getattr(module, "MainWidget", None)
        if (isinstance(module, UiModuleBase)
                and main_widget is not None
                and not sip.isdeleted(main_widget)):
            if not chain or chain[-1] is not module:
                chain.append(module)
        module = module.get_parent()
        guard += 1
        if guard > 100:
            break

    return chain


def _module_global_rect(module: UiModuleBase) -> Optional[QRect]:
    """ Returns the on-screen rectangle of the module's frame, or None. """
    widget = getattr(module, "MainWidget", None)
    if widget is None or sip.isdeleted(widget) or not widget.isVisible():
        return None
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())


# ---------------------------------------------------------------------------
# highlight overlay
# ---------------------------------------------------------------------------

class _HighlightOverlay(QWidget):
    """ Frameless, click-through overlay that marks the frame to be reloaded. """

    def __init__(self):
        flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                 | Qt.Tool | Qt.WindowTransparentForInput)
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._text = ""

    def show_for(self, global_rect: QRect, text: str):
        self._text = text
        self.setGeometry(global_rect)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor(0, 120, 215, 45))
        pen = QPen(QColor(0, 120, 215))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)

        if self._text:
            font = QFont()
            font.setBold(True)
            painter.setFont(font)
            band = QRect(rect.left(), rect.top(), rect.width(),
                         min(22, rect.height()))
            painter.fillRect(band, QColor(0, 120, 215, 210))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(band.adjusted(5, 0, -5, 0),
                             Qt.AlignVCenter | Qt.AlignLeft, self._text)


# ---------------------------------------------------------------------------
# frame picker
# ---------------------------------------------------------------------------

class FramePicker(ModuleBase, QObject):
    """ Interactive picker that hot-reloads the clicked Plan[Goo] frame.

        Usage (dev mode only):
            * activate the tool -> the cursor turns into a cross-hair and the
              frame under the mouse is highlighted,
            * mouse wheel walks the highlight up to a parent frame,
            * left click reloads the highlighted frame from disk,
            * ``Esc`` or right click cancels.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        QObject.__init__(self, None)

        self._active: bool = False
        self._overlay: Optional[_HighlightOverlay] = None
        self._depth: int = 0
        self._last_innermost: Optional[UiModuleBase] = None
        self._action: Optional[QAction] = None

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self.connect(self._timer.timeout, self._update_hover)

    # -- public api ---------------------------------------------------------

    def set_action(self, action: QAction):
        """ Bind the (checkable) toolbar/menu action used to toggle the tool. """
        self._action = action

    @property
    def is_active(self) -> bool:
        return self._active

    def toggle(self):
        if self._active:
            self.cancel()
        else:
            self.start()

    def start(self):
        if self._active:
            return
        self._active = True
        self._depth = 0
        self._last_innermost = None
        self._overlay = _HighlightOverlay()
        QApplication.setOverrideCursor(Qt.CrossCursor)
        QApplication.instance().installEventFilter(self)
        self._timer.start()
        self._set_action_checked(True)
        self._status("Frame-Picker aktiv – Frame anklicken zum Neuladen. "
                     "Mausrad: Eltern-Frame · Esc/Rechtsklick: Abbrechen.")

    def cancel(self):
        was_active = self._active
        self._stop()
        if was_active:
            self._status("Frame-Picker abgebrochen.", timeout=3000)

    # -- lifecycle ----------------------------------------------------------

    def unload(self, self_unload: bool = False):
        self._stop()
        super().unload(self_unload)

    def _stop(self):
        if not self._active:
            return
        self._active = False
        self._timer.stop()
        QApplication.instance().removeEventFilter(self)
        QApplication.restoreOverrideCursor()
        if self._overlay is not None and not sip.isdeleted(self._overlay):
            self._overlay.hide()
            self._overlay.deleteLater()
        self._overlay = None
        self._set_action_checked(False)

    def _set_action_checked(self, checked: bool):
        if self._action is not None and not sip.isdeleted(self._action):
            self._action.blockSignals(True)
            self._action.setChecked(checked)
            self._action.blockSignals(False)

    # -- hover / resolution -------------------------------------------------

    def _widget_at(self, global_pos: QPoint) -> Optional[QWidget]:
        """ Widget under the cursor, ignoring our own (click-through) overlay. """
        widget = QApplication.widgetAt(global_pos)
        overlay = self._overlay
        if (overlay is not None and not sip.isdeleted(overlay)
                and widget is not None and widget.window() is overlay):
            overlay.hide()
            widget = QApplication.widgetAt(global_pos)
            overlay.show()
        return widget

    def _resolve_target(self, global_pos: QPoint
                        ) -> Tuple[Optional[UiModuleBase], List[UiModuleBase]]:
        chain = resolve_module_chain(self._widget_at(global_pos))
        if not chain:
            self._last_innermost = None
            self._depth = 0
            return None, []

        # reset the parent-walk whenever the innermost frame changes
        if chain[0] is not self._last_innermost:
            self._last_innermost = chain[0]
            self._depth = 0

        index = max(0, min(self._depth, len(chain) - 1))
        return chain[index], chain

    def _update_hover(self):
        if not self._active:
            return

        target, chain = self._resolve_target(QCursor.pos())
        if target is None:
            if self._overlay is not None and not sip.isdeleted(self._overlay):
                self._overlay.hide()
            self._status("Kein Plan[Goo]-Frame unter dem Mauszeiger.")
            return

        rect = _module_global_rect(target)
        if rect is None:
            if self._overlay is not None and not sip.isdeleted(self._overlay):
                self._overlay.hide()
            return

        index = max(0, min(self._depth, len(chain) - 1))
        depth_info = f"  [{index + 1}/{len(chain)}]" if len(chain) > 1 else ""
        self._overlay.show_for(rect, f"{target.__class__.__name__}{depth_info}")
        self._status(f"Neu laden: {target.__class__.__name__} "
                     f"({target.module_name}) – Klick zum Neuladen, "
                     f"Mausrad für Eltern-Frame ({index + 1}/{len(chain)}).")

    # -- event handling -----------------------------------------------------

    def eventFilter(self, obj, event):  # noqa: N802 (Qt naming)
        if not self._active:
            return False

        etype = event.type()

        if etype == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self._commit(QCursor.pos())
            else:
                self.cancel()
            return True

        if etype in (QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            # swallow the rest of a consumed click so it never reaches widgets
            return True

        if etype == QEvent.Wheel:
            delta = event.angleDelta().y()
            if delta > 0:
                self._depth = min(self._depth + 1, 99)
            elif delta < 0:
                self._depth = max(self._depth - 1, 0)
            self._update_hover()
            return True

        if etype == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.cancel()
            return True

        return False

    # -- reload -------------------------------------------------------------

    def _commit(self, global_pos: QPoint):
        target, _ = self._resolve_target(global_pos)
        self._stop()
        if target is None:
            self._status("Kein Frame ausgewählt.", timeout=4000)
            return
        # defer so the consumed click fully settles before dialogs/heavy work
        QTimer.singleShot(0, lambda: self._do_reload(target))

    def _do_reload(self, module: UiModuleBase):
        name = module.__class__.__name__
        try:
            new_module = reload_frame_in_place(module)
        except Exception as exc:  # dev tool: surface every failure
            self.log(f"Frame-Reload fehlgeschlagen für {name}: "
                     f"{traceback.format_exc()}", level=self.ERROR)
            self._message_error(
                f"Frame '{name}' konnte nicht neu geladen werden:\n\n{exc}")
            return

        self.log(f"Frame '{name}' neu geladen.", level=self.INFO)
        self._message_success(
            f"Frame '{new_module.__class__.__name__}' neu geladen.")

    # -- messaging ----------------------------------------------------------

    def _status(self, text: str, timeout: int = 0):
        iface = self.iface
        if iface is not None and iface.mainWindow() is not None:
            iface.mainWindow().statusBar().showMessage(text, timeout)

    def _message_success(self, text: str):
        iface = self.iface
        if iface is not None:
            iface.messageBar().pushSuccess("Frame-Picker", text)

    def _message_error(self, text: str):
        iface = self.iface
        if iface is not None:
            iface.messageBar().pushWarning("Frame-Picker", text)
