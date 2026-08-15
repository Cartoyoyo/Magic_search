"""
StayOnTopEventFilter - partage entre les styles d'UI 'maps' (barre flottante)
et 'qt5' (panneau ancrable) pour que les correctifs de comportement fenetre
(voir Fix.md) s'appliquent aux deux styles au lieu d'un seul.
"""
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import QObject, QTimer, QEvent


class StayOnTopEventFilter(QObject):
    def __init__(self, dialog, qgis_main_window, reposition_cb=None):
        super().__init__(dialog)
        self.dialog = dialog
        self.qgis_main_window = qgis_main_window
        self._was_visible = False
        self._reposition_cb = reposition_cb

    def eventFilter(self, watched, event):
        if watched == self.qgis_main_window:
            if event.type() == QEvent.WindowActivate:
                QTimer.singleShot(0, self._maybe_raise)
            elif event.type() == QEvent.WindowStateChange:
                QTimer.singleShot(0, self._sync_visibility)
            elif event.type() == QEvent.Move and self._reposition_cb:
                QTimer.singleShot(0, self._reposition_cb)
        return super().eventFilter(watched, event)

    def _sync_visibility(self):
        """Cache le widget quand QGIS est reduit, le restaure apres."""
        if self.qgis_main_window.isMinimized():
            if self.dialog.isVisible():
                self._was_visible = True
                self.dialog.hide()
        else:
            if self._was_visible:
                self._was_visible = False
                self.dialog.show()
                if self._reposition_cb:
                    QTimer.singleShot(0, self._reposition_cb)

    def _maybe_raise(self):
        """Raise seulement si la fenetre principale QGIS est toujours active
        (pas une table d'attributs ou autre fenetre secondaire)."""
        modal = QApplication.activeModalWidget()
        active_win = QApplication.activeWindow()
        if (modal is None
                and self.dialog.isVisible()
                and not self.dialog.isActiveWindow()
                and active_win == self.qgis_main_window):
            self.dialog.raise_()
