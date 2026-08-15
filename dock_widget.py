"""
Dock Widget - Panneau ancrable Qt5 natif pour Magic Search.
Comportement dynamique : compact au repos, s'etend avec les resultats.
"""
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QFrame
)
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap
import os

from .ui_common import StayOnTopEventFilter
from .core import geo_actions
from .i18n import tr

TAG = 'Magic Search'
VC_NAVY = '#13235b'
VC_TURQUOISE = '#00a096'
COLOR_HIGHLIGHT = '#ff00ff'

ITEM_H = 26
EXPAND_H = 20
MAX_RESULTS = 15
MAX_LIST_H = 350
LAYER_SEARCH_DEBOUNCE_MS = 250

# Couleurs de couches et actions geo (zoom/surbrillance) : voir core/geo_actions.py
_color_for_layer = geo_actions.color_for_layer


class ResultItemDock(QFrame):
    clicked = pyqtSignal(dict)
    hovered = pyqtSignal(dict)
    unhovered = pyqtSignal()

    def __init__(self, data, font_size=11, opacity=100, parent=None):
        super().__init__(parent)
        self._data = data
        self._opacity = opacity
        self.setObjectName("ResultItemDock")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMouseTracking(True)

        source = data.get('source')
        if source == 'ban':
            tag_bg, tag_color = '#ccfbf1', '#0f766e'
            self._border_color = VC_TURQUOISE
        elif source == 'osm':
            tag_bg, tag_color = '#fef3c7', '#92400e'
            self._border_color = '#f59e0b'
        else:
            layer_id = data.get('layer_id', '')
            tag_bg, tag_color = _color_for_layer(layer_id)
            self._border_color = tag_color

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        if source in ('ban', 'osm'):
            txt = data.get('label', '')
            tag_text = 'BAN' if source == 'ban' else 'OSM'
        else:
            original = data.get('original', '')
            count = len(data.get('fids', []))
            txt = f"{original} ({count})" if count > 1 else original
            layer_name = data.get('layer_name', '')
            field_name = data.get('field_name', '')
            tag_text = f"{field_name} | {layer_name}"

        tag_font = max(6, font_size - 3)

        self.lbl_text = QLabel(txt)
        self.lbl_text.setStyleSheet(f"color: #1e293b; font-size: {font_size}px; border: none; background: transparent;")
        layout.addWidget(self.lbl_text, 1)

        self.lbl_tag = QLabel(tag_text)
        self.lbl_tag.setStyleSheet(f"""
            background: {tag_bg}; color: {tag_color}; border-radius: 3px;
            padding: 1px 4px; font-weight: bold; font-size: {tag_font}px;
        """)
        layout.addWidget(self.lbl_tag, 0)

        self._apply_style()

    def _apply_style(self):
        alpha = int(255 * (self._opacity / 100.0))
        self.setStyleSheet(f"""
            #ResultItemDock {{
                background: rgba(255, 255, 255, {alpha});
                border-left: 3px solid {self._border_color};
                border-bottom: 1px solid #e2e8f0;
            }}
            #ResultItemDock:hover {{
                background: rgba(240, 253, 250, {alpha});
            }}
        """)

    def set_opacity(self, opacity):
        self._opacity = opacity
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.hovered.emit(self._data)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unhovered.emit()
        super().leaveEvent(event)


class ExpandItemDock(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, data, remaining, font_size=9, opacity=100, parent=None):
        super().__init__(parent)
        self._data = data
        self._opacity = opacity
        self.setObjectName("ExpandItemDock")
        self.setCursor(QCursor(Qt.PointingHandCursor))

        layer_id = data.get('layer_id', '')
        _, self._tag_color = _color_for_layer(layer_id)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 8, 2)

        self.lbl = QLabel(tr('expand_more', count=remaining))
        self.lbl.setStyleSheet(f"color: {VC_TURQUOISE}; font-style: italic; font-size: {font_size}px; border: none; background: transparent;")
        layout.addWidget(self.lbl)

        self._apply_style()

    def _apply_style(self):
        alpha = int(255 * (self._opacity / 100.0))
        self.setStyleSheet(f"""
            #ExpandItemDock {{
                background: rgba(255, 255, 255, {alpha});
                border-left: 3px solid {self._tag_color};
                border-bottom: 1px solid #e2e8f0;
            }}
            #ExpandItemDock:hover {{ background: rgba(240, 253, 250, {alpha}); }}
        """)

    def set_opacity(self, opacity):
        self._opacity = opacity
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)


_SYNC_COLORS = {
    'never': '#dc2626',     # rouge
    'syncing': '#f59e0b',   # orange
    'complete': '#16a34a',  # vert
}


class MagicSearchDockWidget(QDockWidget):

    config_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    reverse_toggled = pyqtSignal(bool)

    def __init__(self, iface, index_manager, ban_provider, osm_provider, layer_provider, parent=None):
        super().__init__("Magic Search", parent)
        self._iface = iface
        self._index_manager = index_manager
        self._ban_provider = ban_provider
        self._osm_provider = osm_provider
        self._layer_provider = layer_provider

        main_win = iface.mainWindow()
        self.event_filter = StayOnTopEventFilter(self, main_win)
        main_win.installEventFilter(self.event_filter)

        self._ban_results = []
        self._osm_results = []
        self._layer_results = []
        self._rubber_band = None
        self._opacity = 100
        self._widgets = []

        self.setAllowedAreas(Qt.NoDockWidgetArea)
        self.setFloating(True)
        self.setMinimumWidth(350)
        self.setMinimumHeight(70)

        main_widget = QWidget()
        main_widget.setObjectName("MSDockMain")
        self._main_widget = main_widget

        self._main_layout = QVBoxLayout(main_widget)
        self._main_layout.setContentsMargins(8, 8, 8, 8)
        self._main_layout.setSpacing(0)

        # --- Barre de saisie ---
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)

        # Logo icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self._logo_label = QLabel()
            pix = QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._logo_label.setPixmap(pix)
            self._logo_label.setContentsMargins(4, 0, 0, 0)
            input_layout.addWidget(self._logo_label)

        self._input = QLineEdit()
        self._input.setPlaceholderText(tr('placeholder'))
        self._set_input_style(muted=False)
        self._input.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self._input)

        self._btn_clear = QPushButton('\u2715')
        self._btn_clear.setFixedSize(24, 24)
        self._btn_clear.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 12px; border-radius: 12px; color: #94a3b8;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_clear.clicked.connect(lambda: self._input.clear())
        self._btn_clear.hide()
        input_layout.addWidget(self._btn_clear)

        # Bouton geocodage inverse (adresse BAN la plus proche au clic)
        self._btn_reverse = QPushButton('?')
        self._btn_reverse.setFixedSize(24, 24)
        self._btn_reverse.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_reverse.setCheckable(True)
        self._btn_reverse.setToolTip(tr('tip_reverse_geocode'))
        self._update_reverse_style()
        self._btn_reverse.toggled.connect(self.reverse_toggled.emit)
        input_layout.addWidget(self._btn_reverse)

        # Bouton synchronisation
        self._btn_sync = QPushButton('\u27F3')
        self._btn_sync.setFixedSize(24, 24)
        self._btn_sync.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_sync.setToolTip(tr('tip_sync_never'))
        self._btn_sync.clicked.connect(self.sync_requested.emit)
        input_layout.addWidget(self._btn_sync)

        # Etat initial + connexion au signal
        self._update_sync_style(self._index_manager.sync_state)
        self._index_manager.sync_state_changed.connect(self._update_sync_style)

        self._btn_config = QPushButton('\u2699')
        self._btn_config.setFixedSize(24, 24)
        self._btn_config.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_config.setToolTip(tr('tip_config'))
        self._btn_config.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 14px; border-radius: 12px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_config.clicked.connect(self.config_requested.emit)
        input_layout.addWidget(self._btn_config)

        self._main_layout.addWidget(input_container)

        # --- Zone de resultats (dynamique, pas de ScrollArea) ---
        self._results_container = QWidget()
        self._results_container.setObjectName("MSDockResults")
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(0)
        self._results_container.hide()
        self._main_layout.addWidget(self._results_container)

        self.setWidget(main_widget)

        # Signaux
        self._ban_provider.results_ready.connect(self._on_ban_results)
        self._osm_provider.results_ready.connect(self._on_osm_results)
        self._layer_provider.results_ready.connect(self._on_layer_results)

        self._index_debounce = QTimer()
        self._index_debounce.setSingleShot(True)
        self._index_debounce.setInterval(1000)
        self._index_debounce.timeout.connect(self._on_index_updated)
        self._index_manager.layer_ready.connect(self._on_index_changed)
        self._index_manager.indexing_finished.connect(self._on_index_updated)

        self._layer_search_debounce = QTimer()
        self._layer_search_debounce.setSingleShot(True)
        self._layer_search_debounce.setInterval(LAYER_SEARCH_DEBOUNCE_MS)
        self._layer_search_debounce.timeout.connect(self._do_layer_search)

    def _update_reverse_style(self):
        self._btn_reverse.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 13px; font-weight: bold; color: #64748b; border-radius: 12px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
            QPushButton:checked {{ background: {VC_TURQUOISE}; color: white; }}
        """)

    def set_reverse_active(self, active):
        """Synchronise le bouton "?" avec l'etat reel de l'outil de carte
        (ex: decoche si l'utilisateur bascule vers un autre outil QGIS)."""
        self._btn_reverse.blockSignals(True)
        self._btn_reverse.setChecked(active)
        self._btn_reverse.blockSignals(False)

    def show_reverse_address(self, label):
        """Affiche l'adresse trouvee par l'outil "?" dans le champ de recherche,
        sans declencher une nouvelle recherche (textChanged bloque)."""
        self._clear_list()
        self._set_input_style(muted=False)
        self._input.blockSignals(True)
        self._input.setText(label)
        self._input.blockSignals(False)
        self._btn_clear.setVisible(bool(label))

    def show_reverse_not_found(self, message):
        """Affiche le message "aucune adresse trouvee" (style attenue) dans le
        champ de recherche, sans declencher une nouvelle recherche."""
        self._clear_list()
        self._set_input_style(muted=True)
        self._input.blockSignals(True)
        self._input.setText(message)
        self._input.blockSignals(False)
        self._btn_clear.setVisible(True)

    def set_opacity(self, opacity):
        self._opacity = opacity
        self._update_styles()
        for w in self._widgets:
            if hasattr(w, 'set_opacity'):
                w.set_opacity(self._opacity)

    def _update_styles(self):
        alpha = int(255 * (self._opacity / 100.0))
        self._main_widget.setStyleSheet(f"""
            QWidget#MSDockMain {{
                background-color: rgba(248, 250, 252, {alpha});
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            }}
        """)

    def _on_index_changed(self, *args):
        self._index_debounce.start()

    def _on_index_updated(self, *args):
        self._index_debounce.stop()
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text)

    def _set_input_style(self, muted):
        color = '#94a3b8' if muted else '#334155'
        style = 'italic' if muted else 'normal'
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: white; border: 1px solid #cbd5e1;
                border-radius: 6px; padding: 8px 12px;
                font-size: 12px; font-style: {style}; color: {color};
            }}
            QLineEdit:focus {{ border: 1px solid #00a096; }}
        """)

    def _on_text_changed(self, text):
        self._set_input_style(muted=False)
        self._btn_clear.setVisible(bool(text))
        if not text or len(text) < 2:
            self._layer_search_debounce.stop()
            self._clear_list()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            return
        self._ban_provider.search(text)
        self._osm_provider.search(text)
        self._layer_search_debounce.start()

    def _do_layer_search(self):
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text)

    def _on_ban_results(self, results):
        self._ban_results = results
        self._update_list()

    def _on_osm_results(self, results):
        self._osm_results = results
        self._update_list()

    def _on_layer_results(self, results):
        self._layer_results = results
        self._update_list()

    # ========================================
    # Construction dynamique des resultats
    # ========================================

    def _count_items(self):
        """Compte le nombre total d'items a afficher."""
        n = len(self._ban_results) + len(self._osm_results)
        remaining_slots = MAX_RESULTS - min(n, MAX_RESULTS)
        for group in self._layer_results:
            if remaining_slots <= 0:
                break
            matches = min(len(group.get('matches', [])), remaining_slots)
            n += matches
            remaining_slots -= matches
            rem = group.get('total_matches', 0) - len(group.get('matches', []))
            if rem > 0 and remaining_slots > 0:
                n += 1
                remaining_slots -= 1
        return max(n, 1)

    def _update_list(self):
        self._clear_list()
        shown = 0

        item_count = self._count_items()
        total_h_est = item_count * ITEM_H
        usable_h = min(total_h_est, MAX_LIST_H)
        item_h = usable_h / item_count if item_count > 0 else ITEM_H
        font_size = max(7, min(11, int(item_h * 0.45)))
        expand_font = max(5, font_size - 2)

        # --- BAN ---
        for r in self._ban_results:
            if shown >= MAX_RESULTS:
                break
            item_data = {**r, 'source': 'ban'}
            w = ResultItemDock(item_data, font_size=font_size, opacity=self._opacity)
            w.clicked.connect(self._on_result_clicked)
            w.hovered.connect(self._on_result_hovered)
            w.unhovered.connect(self._clear_rubber_band)
            self._results_layout.addWidget(w)
            self._widgets.append(w)
            shown += 1

        # --- OSM ---
        for r in self._osm_results:
            if shown >= MAX_RESULTS:
                break
            item_data = {**r, 'source': 'osm'}
            w = ResultItemDock(item_data, font_size=font_size, opacity=self._opacity)
            w.clicked.connect(self._on_result_clicked)
            w.hovered.connect(self._on_result_hovered)
            w.unhovered.connect(self._clear_rubber_band)
            self._results_layout.addWidget(w)
            self._widgets.append(w)
            shown += 1

        # --- Couches ---
        for group in self._layer_results:
            if shown >= MAX_RESULTS:
                break
            layer_id = group.get('layer_id', '')
            layer_name = group.get('layer_name', '')
            field_name = group.get('field_name', '')

            for match in group.get('matches', []):
                if shown >= MAX_RESULTS:
                    break
                item_data = {
                    **match,
                    'source': 'layer',
                    'layer_id': layer_id,
                    'layer_name': layer_name,
                    'field_name': field_name,
                }
                w = ResultItemDock(item_data, font_size=font_size, opacity=self._opacity)
                w.clicked.connect(self._on_result_clicked)
                w.hovered.connect(self._on_result_hovered)
                w.unhovered.connect(self._clear_rubber_band)
                self._results_layout.addWidget(w)
                self._widgets.append(w)
                shown += 1

            if shown >= MAX_RESULTS:
                break
            remaining = group.get('total_matches', 0) - len(group.get('matches', []))
            if remaining > 0:
                all_fids = []
                for m in group['matches']:
                    all_fids.extend(m.get('fids', []))
                expand_data = {
                    'source': 'layer_group',
                    'layer_id': layer_id,
                    'layer_name': layer_name,
                    'field_name': field_name,
                    'fids': all_fids,
                }
                w = ExpandItemDock(expand_data, remaining, font_size=expand_font, opacity=self._opacity)
                w.clicked.connect(self._on_result_clicked)
                self._results_layout.addWidget(w)
                self._widgets.append(w)
                shown += 1

        if shown == 0 and len(self._input.text()) >= 2:
            lbl = QLabel("  " + tr('no_results'))
            lbl.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 8px; background: transparent;")
            self._results_layout.addWidget(lbl)
            self._widgets.append(lbl)
            shown = 1

        # Afficher/masquer + hauteur dynamique
        if shown > 0:
            h = min(shown * ITEM_H, MAX_LIST_H)
            self._results_container.setMinimumHeight(h)
            self._results_container.setMaximumHeight(h)
            self._results_container.show()
        else:
            self._results_container.hide()

        self._adjust_dock_size()

    def _clear_list(self):
        for w in self._widgets:
            self._results_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self._results_container.setMinimumHeight(0)
        self._results_container.setMaximumHeight(0)
        self._results_container.hide()
        self._adjust_dock_size()

    def _adjust_dock_size(self):
        """Force le QDockWidget a s'adapter a son contenu."""
        # Calculer la hauteur exacte : barre de saisie + resultats + marges
        input_h = 50  # QLineEdit avec padding
        margins = 16  # contentsMargins haut+bas du layout
        title_h = 25  # barre de titre du QDockWidget
        results_h = self._results_container.maximumHeight() if self._results_container.isVisible() else 0
        h = input_h + results_h + margins + title_h

        # Forcer la hauteur sur le widget interne ET le dock
        self._main_widget.setFixedHeight(h - title_h)
        if self.isFloating():
            self.setFixedHeight(h)
            # Relacher immediatement pour permettre l'agrandissement futur
            QTimer.singleShot(0, self._release_height)

    def _release_height(self):
        """Relache les contraintes de hauteur fixe apres le redimensionnement."""
        self.setMinimumHeight(70)
        self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        self._main_widget.setMinimumHeight(0)
        self._main_widget.setMaximumHeight(16777215)

    # ========================================
    # Actions
    # ========================================

    def _on_result_clicked(self, data):
        self._clear_rubber_band()
        source = data.get('source', '')
        if source in ('ban', 'osm'):
            self._zoom_to_ban(data)
        elif source in ('layer', 'layer_group'):
            self._zoom_to_features(data)

    def _on_result_hovered(self, data):
        self._clear_rubber_band()
        source = data.get('source', '')
        if source in ('ban', 'osm'):
            self._highlight_ban(data)
        elif source == 'layer':
            self._highlight_features(data)

    def _zoom_to_ban(self, data):
        point = geo_actions.zoom_to_point(self._iface, data['lon'], data['lat'])
        self._rubber_band = geo_actions.make_point_rubber(self._iface.mapCanvas(), point)

    def _highlight_ban(self, data):
        point = geo_actions.transform_point(self._iface, data['lon'], data['lat'])
        self._rubber_band = geo_actions.make_point_rubber(self._iface.mapCanvas(), point)

    def _zoom_to_features(self, data):
        geo_actions.zoom_to_features(self._iface, data.get('layer_id'), data.get('fids', []))

    def _highlight_features(self, data):
        self._rubber_band = geo_actions.make_features_rubber(
            self._iface, data.get('layer_id'), data.get('fids', [])
        )

    def _clear_rubber_band(self):
        self._rubber_band = geo_actions.clear_rubber(self._rubber_band)

    def _update_sync_style(self, state):
        """Met a jour la couleur du bouton sync selon l'etat."""
        color = _SYNC_COLORS.get(state, '#dc2626')
        self._btn_sync.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 15px; color: {color}; border-radius: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #f1f5f9; }}
        """)
        self._sync_state = state
        self._btn_sync.setToolTip(tr(f'tip_sync_{state}') if state in
                                  ('never', 'syncing', 'complete') else '')

    def retranslate(self):
        """Rafraichit les libelles deja construits apres un changement de langue."""
        self._input.setPlaceholderText(tr('placeholder'))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._btn_reverse.setToolTip(tr('tip_reverse_geocode'))
        self._btn_config.setToolTip(tr('tip_config'))
        self._update_sync_style(self._sync_state)
        # Les resultats sont reconstruits a chaque frappe : rien a retraduire ici.

    def set_focus(self):
        self._input.setFocus()
        self.raise_()

    def cleanup(self):
        self._clear_rubber_band()
