"""
Dock Widget - Panneau ancrable Qt5 natif pour Magic Search.
Comportement dynamique : compact au repos, s'etend avec les resultats.
"""
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QFrame
)
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor, QCursor, QPixmap
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsGeometry, Qgis, QgsMessageLog
)
from qgis.gui import QgsRubberBand
import os

TAG = 'Magic Search'
VC_NAVY = '#13235b'
VC_TURQUOISE = '#00a096'
COLOR_HIGHLIGHT = '#ff00ff'

ITEM_H = 26
EXPAND_H = 20
MAX_RESULTS = 15
MAX_LIST_H = 350

_LAYER_COLORS = [
    ('#eef2ff', '#3730a3'),
    ('#fef3c7', '#92400e'),
    ('#dcfce7', '#166534'),
    ('#fce7f3', '#9d174d'),
    ('#e0f2fe', '#075985'),
    ('#fef9c3', '#854d0e'),
    ('#f3e8ff', '#6b21a8'),
    ('#ccfbf1', '#115e59'),
    ('#fee2e2', '#991b1b'),
    ('#e0e7ff', '#3b0764'),
]
_layer_color_map = {}


def _color_for_layer(layer_id):
    if layer_id not in _layer_color_map:
        idx = len(_layer_color_map) % len(_LAYER_COLORS)
        _layer_color_map[layer_id] = _LAYER_COLORS[idx]
    return _layer_color_map[layer_id]


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

        self.lbl = QLabel(f"... {remaining} autre(s) - zoom global")
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

    def __init__(self, iface, index_manager, ban_provider, osm_provider, layer_provider, parent=None):
        super().__init__("Magic Search", parent)
        self._iface = iface
        self._index_manager = index_manager
        self._ban_provider = ban_provider
        self._osm_provider = osm_provider
        self._layer_provider = layer_provider

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
        self._input.setPlaceholderText('Rechercher adresses, parcelles...')
        self._input.setStyleSheet("""
            QLineEdit {
                background: white; border: 1px solid #cbd5e1;
                border-radius: 6px; padding: 8px 12px;
                font-size: 12px; color: #334155;
            }
            QLineEdit:focus { border: 1px solid #00a096; }
        """)
        self._input.textChanged.connect(self._on_text_changed)
        input_layout.addWidget(self._input)

        self._btn_clear = QPushButton('\u2715')
        self._btn_clear.setFixedSize(24, 24)
        self._btn_clear.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_clear.setToolTip('Effacer')
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

        # Bouton synchronisation
        self._btn_sync = QPushButton('\u27F3')
        self._btn_sync.setFixedSize(24, 24)
        self._btn_sync.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_sync.setToolTip('Synchroniser les couches')
        self._btn_sync.clicked.connect(self.sync_requested.emit)
        input_layout.addWidget(self._btn_sync)

        # Etat initial + connexion au signal
        self._update_sync_style(self._index_manager.sync_state)
        self._index_manager.sync_state_changed.connect(self._update_sync_style)

        self._btn_config = QPushButton('\u2699')
        self._btn_config.setFixedSize(24, 24)
        self._btn_config.setCursor(QCursor(Qt.PointingHandCursor))
        self._btn_config.setToolTip('Configuration')
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

    def _on_text_changed(self, text):
        self._btn_clear.setVisible(bool(text))
        if not text or len(text) < 2:
            self._clear_list()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            return
        self._ban_provider.search(text)
        self._osm_provider.search(text)
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
            lbl = QLabel("  Aucun resultat")
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
        canvas = self._iface.mapCanvas()
        crs_src = QgsCoordinateReferenceSystem('EPSG:4326')
        crs_dst = canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        point = transform.transform(QgsPointXY(data['lon'], data['lat']))
        canvas.setCenter(point)
        canvas.zoomScale(2000)
        canvas.refresh()
        self._show_point_rubber(point, canvas)

    def _highlight_ban(self, data):
        canvas = self._iface.mapCanvas()
        crs_src = QgsCoordinateReferenceSystem('EPSG:4326')
        crs_dst = canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        point = transform.transform(QgsPointXY(data['lon'], data['lat']))
        self._show_point_rubber(point, canvas)

    def _zoom_to_features(self, data):
        layer_id = data.get('layer_id')
        fids = data.get('fids', [])
        if not layer_id or not fids: return
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer: return
        canvas = self._iface.mapCanvas()
        combined = QgsGeometry()
        for fid in fids:
            feat = layer.getFeature(fid)
            if feat.hasGeometry():
                if combined.isEmpty():
                    combined = QgsGeometry(feat.geometry())
                else:
                    combined = combined.combine(feat.geometry())
        if not combined.isEmpty():
            crs_src = layer.crs()
            crs_dst = canvas.mapSettings().destinationCrs()
            if crs_src != crs_dst:
                transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
                combined.transform(transform)
            canvas.setExtent(combined.boundingBox())
            if canvas.scale() < 2000:
                canvas.setCenter(combined.centroid().asPoint())
                canvas.zoomScale(2000)
            else:
                canvas.zoomScale(canvas.scale() * 1.1)
            canvas.refresh()
        layer.selectByIds(fids)

    def _highlight_features(self, data):
        layer_id = data.get('layer_id')
        fids = data.get('fids', [])
        if not layer_id or not fids: return
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer: return
        canvas = self._iface.mapCanvas()
        self._rubber_band = QgsRubberBand(canvas, layer.geometryType())
        self._rubber_band.setColor(QColor(COLOR_HIGHLIGHT))
        self._rubber_band.setWidth(3)
        self._rubber_band.setFillColor(QColor(255, 0, 255, 40))
        crs_src = layer.crs()
        crs_dst = canvas.mapSettings().destinationCrs()
        need_transform = crs_src != crs_dst
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance()) if need_transform else None
        for fid in fids[:20]:
            feat = layer.getFeature(fid)
            if feat.hasGeometry():
                geom = QgsGeometry(feat.geometry())
                if transform:
                    geom.transform(transform)
                self._rubber_band.addGeometry(geom, None)

    def _show_point_rubber(self, point, canvas):
        try:
            geom_type = Qgis.GeometryType.Point
        except AttributeError:
            from qgis.core import QgsWkbTypes
            geom_type = QgsWkbTypes.PointGeometry
        self._rubber_band = QgsRubberBand(canvas, geom_type)
        self._rubber_band.setColor(QColor(VC_TURQUOISE))
        self._rubber_band.setWidth(3)
        self._rubber_band.setIcon(QgsRubberBand.ICON_CIRCLE)
        self._rubber_band.setIconSize(15)
        self._rubber_band.addPoint(point)

    def _clear_rubber_band(self):
        if self._rubber_band:
            self._rubber_band.reset()
            self._rubber_band = None

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
        tips = {
            'never': 'Synchronisation requise (jamais synchronise)',
            'syncing': 'Synchronisation en cours...',
            'complete': 'Synchronisation complete',
        }
        self._btn_sync.setToolTip(tips.get(state, ''))

    def set_focus(self):
        self._input.setFocus()
        self.raise_()

    def cleanup(self):
        self._clear_rubber_band()
