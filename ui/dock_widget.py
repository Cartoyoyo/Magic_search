"""
Dock Widget - Panneau ancrable natif (QDockWidget) pour Magic Search.
Identifiant de style 'qt5' : nom historique conserve pour ne pas invalider
les preferences enregistrees, l'interface suit la version de Qt de QGIS.

Meme pilule et meme liste que la barre flottante (modele M2c, cf.
search_widget.PillMixin), avec le logo du plugin en tete de pilule.
Comportement dynamique : compact au repos, s'etend avec les resultats.
"""
from qgis.PyQt.QtWidgets import QDockWidget, QWidget, QVBoxLayout
from qgis.PyQt.QtCore import Qt, QTimer, QEvent, pyqtSignal

from .ui_common import StayOnTopEventFilter
from .search_widget import (PillMixin, BAR_H, COLOR_MUTED, COLOR_TEXT,
                            LAYER_SEARCH_DEBOUNCE_MS)
from ..core import geo_actions
from ..core.coord_parser import coordinate_candidates, to_lonlat as coord_to_lonlat
from ..i18n import tr

TAG = 'Magic Search'
LIST_GAP = 8        # espace entre la pilule et la liste
DOCK_MARGIN = 8
TITLE_H = 25        # barre de titre du QDockWidget flottant


class MagicSearchDockWidget(PillMixin, QDockWidget):

    config_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    reverse_toggled = pyqtSignal(bool)
    street_view_requested = pyqtSignal(str)
    add_favorite_requested = pyqtSignal()
    remove_favorite_requested = pyqtSignal(int)
    scope_changed = pyqtSignal(bool)   # True = toutes les couches

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
        self._coord_results = []
        self._geo_errors = {}
        self._rubber_band = None
        self._opacity = 100

        self.setAllowedAreas(Qt.DockWidgetArea.NoDockWidgetArea)
        self.setFloating(True)
        self.setMinimumWidth(380)
        self.setMinimumHeight(70)

        main_widget = QWidget()
        main_widget.setObjectName("MSDockMain")
        self._main_widget = main_widget
        self._main_layout = QVBoxLayout(main_widget)
        self._main_layout.setContentsMargins(DOCK_MARGIN, DOCK_MARGIN, DOCK_MARGIN, DOCK_MARGIN)
        self._main_layout.setSpacing(0)

        # Pilule (avec le logo) + liste, communes a la barre flottante
        self._build_pill(logo=True)
        self._main_layout.addWidget(self._bar)
        self._main_layout.addSpacing(LIST_GAP)
        self._main_layout.addWidget(self._dropdown)
        self._main_layout.addStretch(1)
        self._update_sync_style(self._sync_state)
        self._update_styles()

        self.setWidget(main_widget)

        # Signaux
        self._ban_provider.results_ready.connect(self._on_ban_results)
        self._osm_provider.results_ready.connect(self._on_osm_results)
        self._ban_provider.failed.connect(self._on_ban_failed)
        self._osm_provider.failed.connect(self._on_osm_failed)
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

        self._adjust_dock_size()

    def eventFilter(self, obj, event):
        # Clavier de la saisie (fleches, Entree, Echap, Tab) : cf. PillMixin
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            return self._on_input_key(event)
        return super().eventFilter(obj, event)

    # ---- Points d'accroche de PillMixin ----

    def _close_list(self):
        self._clear_list()

    def _refresh_list(self):
        self._update_list()

    # ---- Saisie ----

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
        self._update_bar_style()
        self._dropdown.set_opacity(opacity)

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
            self._layer_provider.search(text, max_per_field=self._per_field())

    def _set_input_style(self, muted):
        color = COLOR_MUTED if muted else COLOR_TEXT
        style = 'italic' if muted else 'normal'
        self._input.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                font-size: 12px; font-style: {style}; color: {color}; padding: 8px 0;
            }}
        """)

    def _on_text_changed(self, text):
        self._show_all = False
        self._set_input_style(muted=False)
        self._btn_clear.setVisible(bool(text))
        if not text or len(text) < 2:
            self._layer_search_debounce.stop()
            self._clear_list()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._coord_results = []
            self._geo_errors = {}
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            return

        coords = coordinate_candidates(
            text, near=geo_actions.canvas_center_lonlat(self._iface))
        if coords:
            for coord in coords:
                coord['lon'], coord['lat'] = coord_to_lonlat(coord)
            # Une paire de nombres n'est pas une adresse : pas de geocodeur.
            # Les couches, elles, sont toujours interrogees (une valeur
            # metier peut ressembler a une coordonnee).
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._geo_errors = {}
            self._coord_results = coords
            self._update_list()
            self._layer_search_debounce.start()
            return

        self._coord_results = []
        self._search_geocoders(text)
        self._layer_search_debounce.start()

    def _do_layer_search(self):
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text, max_per_field=self._per_field())

    def _on_ban_results(self, results):
        self._ban_results = results
        self._geo_errors.pop('ban', None)
        self._update_list()

    def _on_osm_results(self, results):
        self._osm_results = results
        self._geo_errors.pop('osm', None)
        self._update_list()

    def _on_layer_results(self, results):
        self._layer_results = results
        self._update_list()

    # ========================================
    # Liste de resultats
    # ========================================

    def _update_list(self):
        text = self._input.text()
        if not text or len(text) < 2:
            self._clear_list()
            return
        self._dropdown.show_results(
            self._ban_results, self._osm_results, self._layer_results,
            self._coord_results, query=text,
            center=geo_actions.canvas_center_lonlat(self._iface),
            show_all=self._show_all, geo_errors=self._geo_errors
        )
        self._refresh_footer()
        self._adjust_dock_size()

    def _clear_list(self):
        self._dropdown.hide_results()
        self._clear_rubber_band()
        self._adjust_dock_size()

    def _adjust_dock_size(self):
        """Ajuste le panneau flottant a son contenu : pilule seule au repos,
        pilule + liste quand il y a des resultats."""
        list_h = (LIST_GAP + self._dropdown.height()) if self._dropdown.isVisible() else LIST_GAP
        inner = BAR_H + list_h + 2 * DOCK_MARGIN
        self._main_widget.setFixedHeight(inner)
        if self.isFloating():
            self.setFixedHeight(inner + TITLE_H)
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
        if source in ('ban', 'osm', 'coord'):
            self._zoom_to_ban(data)
        elif source in ('layer', 'layer_group'):
            self._zoom_to_features(data)
        if source in ('ban', 'osm', 'layer', 'layer_group'):
            self._push_history(self._input.text())

    def _on_result_hovered(self, data):
        self._clear_rubber_band()
        source = data.get('source', '')
        if source in ('ban', 'osm', 'coord'):
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

    def retranslate(self):
        """Rafraichit les libelles deja construits apres un changement de langue."""
        self._input.setPlaceholderText(tr('placeholder'))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._chip_reverse.setToolTip(tr('tip_reverse_active'))
        self._btn_street.setToolTip(tr('tip_street_view'))
        self._act_copy_coords.setText(tr('menu_copy_coords'))
        self._btn_more.setToolTip(tr('tip_more'))
        self._update_scope_text()
        self._update_sync_style(self._sync_state)
        # Les resultats sont reconstruits a chaque frappe : rien a retraduire ici.

    def set_focus(self):
        self._input.setFocus()
        self.raise_()

    def _disconnect_sources(self):
        """Coupe les signaux des objets qui survivent a ce panneau (index,
        fournisseurs) : apres une bascule de style, il ne doit plus rien
        recevoir."""
        for signal, slot in (
                (self._ban_provider.results_ready, self._on_ban_results),
                (self._osm_provider.results_ready, self._on_osm_results),
                (self._ban_provider.failed, self._on_ban_failed),
                (self._osm_provider.failed, self._on_osm_failed),
                (self._layer_provider.results_ready, self._on_layer_results),
                (self._index_manager.sync_state_changed, self._update_sync_style),
                (self._index_manager.layer_ready, self._on_index_changed),
                (self._index_manager.indexing_finished, self._on_index_updated)):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    def cleanup(self):
        self._disconnect_sources()
        self._index_debounce.stop()
        self._layer_search_debounce.stop()
        self._clear_rubber_band()
