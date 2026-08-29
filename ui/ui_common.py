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
            if event.type() == QEvent.Type.WindowActivate:
                QTimer.singleShot(0, self._maybe_raise)
            elif event.type() == QEvent.Type.WindowStateChange:
                QTimer.singleShot(0, self._sync_visibility)
            elif event.type() == QEvent.Type.Move and self._reposition_cb:
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


# ============================================================
# Bouton de synchronisation : styles par etat
# ============================================================
# L'indexation ne demarre plus toute seule : le bouton est le seul declencheur.
# Il doit donc se voir. Les deux etats incomplets ('never' rouge, 'partial'
# orange) sont peints en pastille pleine, l'etat complet reste discret.
SYNC_STYLES = {
    #  etat      : (fond,       texte,     bordure,   glyphe, taille police)
    'never':      ('#dc2626', '#ffffff', '#991b1b', '\u26A0', 13),
    'partial':    ('#f59e0b', '#ffffff', '#b45309', '\u27F3', 15),
    'syncing':    ('#fef3c7', '#b45309', '#f59e0b', '\u27F3', 15),
    'complete':   ('transparent', '#16a34a', 'transparent', '\u27F3', 15),
}


def sync_button_style(state, radius):
    """Feuille de style du bouton de synchronisation pour un etat donne."""
    bg, fg, border, _glyph, font_size = SYNC_STYLES.get(state, SYNC_STYLES['never'])
    border_css = 'none' if border == 'transparent' else f'1px solid {border}'
    hover_bg = '#f1f5f9' if bg == 'transparent' else bg
    return f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: {border_css};
            border-radius: {radius}px;
            font-size: {font_size}px;
            font-weight: bold;
            padding: 0px;
        }}
        QPushButton:hover {{ background: {hover_bg}; }}
        QPushButton:pressed {{ background: {hover_bg}; }}
    """


def sync_button_glyph(state):
    """Caractere affiche dans le bouton : un avertissement quand rien n'est
    indexe, la fleche circulaire dans tous les autres cas."""
    return SYNC_STYLES.get(state, SYNC_STYLES['never'])[3]
