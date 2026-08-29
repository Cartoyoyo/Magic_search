"""
Search Widget - Barre de recherche flottante style carte-interactive.
- Centree en haut du canevas par defaut
- Retractable en cercle (fleche de retractation)
- Clic sur le cercle = deplie la barre
- Drag & drop : maintenir clic gauche pour deplacer
- Dropdown = widget separe (pas clippe par le parent)
"""

import os
from qgis.PyQt.QtWidgets import (
    QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect,
    QPushButton, QDialog, QToolButton, QMenu
)
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QPoint, QEvent, QRect
from qgis.PyQt.QtGui import QColor, QCursor, QPainter, QPen, QBrush, QPixmap

from .ui_common import StayOnTopEventFilter, sync_button_style, sync_button_glyph
from ..core.qt_compat import event_pos, event_global_pos
from ..core import geo_actions
from ..core.street_view_tool import SERVICE_LABELS, COPY_COORDS
from ..core.coord_parser import parse_coordinates, to_lonlat as coord_to_lonlat
from ..i18n import tr

TAG = 'Magic Search'

# ---- Charte couleurs Vichy Communaute ----
VC_NAVY = '#13235b'
VC_TURQUOISE = '#00a096'
VC_ORANGE = '#f29400'
COLOR_BORDER = '#e2e8f0'
COLOR_HOVER = '#f0f4f8'
COLOR_TEXT = '#1e293b'
COLOR_MUTED = '#64748b'
COLOR_HIGHLIGHT = '#ff00ff'

# Couleurs de couches et actions geo (zoom/surbrillance) : voir core/geo_actions.py
_color_for_layer = geo_actions.color_for_layer

# QSS des menus deroulants ("◎" / "⋮" et leurs sous-menus) : par defaut Qt les
# dessine avec le style natif de l'OS (blanc generique), en rupture avec la
# barre flottante habillee sur-mesure. Applique une seule fois sur les menus
# racine ("◎", "⋮") : les sous-menus (Favoris, Supprimer, Historique...) sont
# des enfants Qt et heritent du style en cascade.
MENU_QSS = f"""
    QMenu {{
        background: white;
        border: 1.5px solid {VC_NAVY};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 22px 6px 12px;
        border-radius: 5px;
        color: {COLOR_TEXT};
        font-size: 11px;
    }}
    QMenu::item:selected {{
        background: {COLOR_HOVER};
        color: {VC_NAVY};
    }}
    QMenu::item:disabled {{
        color: {COLOR_MUTED};
    }}
    QMenu::separator {{
        height: 1px;
        background: {COLOR_BORDER};
        margin: 4px 8px;
    }}
"""

SEARCH_BAR_W = 500
SEARCH_BAR_H = 40
COLLAPSED_SIZE = 42
MARGIN_TOP = 14
DRAG_THRESHOLD = 5
RESIZE_HANDLE = 8      # pixels on each side that trigger resize
BAR_MIN_W = 200
BAR_MAX_W = 1200
LAYER_SEARCH_DEBOUNCE_MS = 250


# ============================================================
# Sous-widgets
# ============================================================

class CollapsedButton(QWidget):
    """Cercle retracte avec icone loupe. Cliquable + draggable."""

    clicked = pyqtSignal()
    drag_started = pyqtSignal(QPoint)
    drag_moved = pyqtSignal(QPoint)
    drag_finished = pyqtSignal()

    def __init__(self, parent=None, opacity=100):
        super().__init__(parent)
        self.setFixedSize(COLLAPSED_SIZE, COLLAPSED_SIZE)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dragging = False
        self._press_pos = QPoint()
        self._opacity = opacity

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.png')
        self._pixmap = QPixmap(icon_path) if os.path.exists(icon_path) else None

    def set_opacity(self, opacity):
        self._opacity = opacity
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(VC_NAVY), 2))
        alpha = int(255 * (self._opacity / 100.0))
        p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
        p.drawEllipse(2, 2, COLLAPSED_SIZE - 4, COLLAPSED_SIZE - 4)
        
        if self._pixmap and not self._pixmap.isNull():
            # Dessiner le logo au centre (90% de la taille interne environ)
            target_rect = QRect(6, 6, COLLAPSED_SIZE - 12, COLLAPSED_SIZE - 12)
            p.drawPixmap(target_rect, self._pixmap)
        else:
            # Fallback loupe
            p.setPen(QPen(QColor(VC_NAVY), 2.5))
            p.drawEllipse(12, 10, 14, 14)
            p.drawLine(24, 22, 30, 28)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event_global_pos(event)
            self._dragging = False

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event_global_pos(event) - self._press_pos
            if not self._dragging and delta.manhattanLength() > DRAG_THRESHOLD:
                self._dragging = True
                self.drag_started.emit(event_global_pos(event))
            if self._dragging:
                self.drag_moved.emit(event_global_pos(event))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                self._dragging = False
                self.drag_finished.emit()
            else:
                self.clicked.emit()


class ResultItem(QFrame):
    """Item de resultat avec tag source a droite (BAN ou couche|colonne)."""

    clicked = pyqtSignal(dict)
    hovered = pyqtSignal(dict)
    unhovered = pyqtSignal()

    def __init__(self, data, font_size=11, parent=None, opacity=100):
        super().__init__(parent)
        self._data = data
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)
        self._opacity = opacity

        source = data.get('source')
        if source == 'ban':
            tag_bg = '#ccfbf1'
            tag_color = '#0f766e'
            border_color = VC_TURQUOISE
        elif source == 'osm':
            tag_bg = '#fef3c7'
            tag_color = '#92400e'
            border_color = '#f59e0b'
        elif source == 'coord':
            tag_bg = '#e0e7ff'
            tag_color = VC_NAVY
            border_color = VC_NAVY
        else:
            layer_id = data.get('layer_id', '')
            tag_bg, tag_color = _color_for_layer(layer_id)
            border_color = tag_color

        alpha = int(255 * (self._opacity / 100.0))
        self.setStyleSheet(f"""
            ResultItem {{
                background: rgba(255, 255, 255, {alpha});
                border-left: 3px solid {border_color};
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            ResultItem:hover {{
                background: rgba(240, 244, 248, {alpha});
            }}
        """)

        # Layout horizontal : contenu a gauche, tag source a droite
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 2, 8, 2)
        row.setSpacing(6)

        # Contenu principal
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        tag_font_size = max(6, font_size - 3)

        if source in ('ban', 'osm', 'coord'):
            lbl_main = QLabel(data.get('label', ''))
            lbl_main.setStyleSheet(f'color: {COLOR_TEXT}; font-size: {font_size}px; border: none;')
            content.addWidget(lbl_main)
        else:
            original = data.get('original', '')
            count = len(data.get('fids', []))
            count_text = f"  ({count})" if count > 1 else ""
            lbl_val = QLabel(f"{original}{count_text}")
            lbl_val.setStyleSheet(f'color: {COLOR_TEXT}; font-size: {font_size}px; border: none;')
            content.addWidget(lbl_val)

        row.addLayout(content, 1)

        # Tag source a droite
        if source == 'ban':
            tag_text = 'BAN'
        elif source == 'osm':
            tag_text = 'OSM'
        elif source == 'coord':
            tag_text = tr('tag_coord')
        else:
            layer_name = data.get('layer_name', '')
            field_name = data.get('field_name', '')
            tag_text = f"{field_name} | {layer_name}"

        tag = QLabel(tag_text)
        tag.setStyleSheet(f"""
            color: {tag_color};
            background: {tag_bg};
            font-size: {tag_font_size}px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            border: none;
        """)
        row.addWidget(tag, 0, Qt.AlignmentFlag.AlignVCenter)

    def enterEvent(self, event):
        self.hovered.emit(self._data)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unhovered.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)


class ExpandItem(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, data, remaining, font_size=9, parent=None, opacity=100):
        super().__init__(parent)
        self._data = data
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        alpha = int(255 * (opacity / 100.0))
        self.setStyleSheet(f"""
            ExpandItem {{
                background: rgba(255, 255, 255, {alpha});
                border-left: 3px solid {VC_NAVY};
                border-bottom: 1px solid {COLOR_BORDER};
            }}
            ExpandItem:hover {{ background: rgba(240, 244, 248, {alpha}); }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 2, 14, 2)
        lbl = QLabel(tr('expand_more', count=remaining))
        lbl.setStyleSheet(f'color: {VC_TURQUOISE}; font-size: {font_size}px; font-style: italic; border: none;')
        layout.addWidget(lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)


# ============================================================
# Dropdown separe (widget independant sur le canevas)
# ============================================================

class DropdownWidget(QFrame):
    """Dropdown de resultats integre directement a la barre."""

    result_clicked = pyqtSignal(dict)
    result_hovered = pyqtSignal(dict)
    result_unhovered = pyqtSignal()

    ITEM_H = 26
    EXPAND_H = 20
    NO_RESULT_H = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 4, 0, 4)
        self._main_layout.setSpacing(0)

        self._widgets = []
        self._opacity = 100
        self.hide()

    def set_opacity(self, opacity):
        self._opacity = opacity

    MAX_RESULTS = 15

    def show_results(self, ban_results, osm_results, layer_results, coord_result=None):
        self._clear()
        has_any = False
        shown = 0

        geocode_results = len(ban_results) + len(osm_results) + (1 if coord_result else 0)

        # --- Compter les items pour calculer la hauteur disponible par ligne ---
        item_count = min(geocode_results, self.MAX_RESULTS)
        remaining_slots = self.MAX_RESULTS - item_count
        for group in layer_results:
            if remaining_slots <= 0:
                break
            n = min(len(group.get('matches', [])), remaining_slots)
            item_count += n
            remaining_slots -= n
            if group['total_matches'] - len(group['matches']) > 0 and remaining_slots > 0:
                item_count += 1
                remaining_slots -= 1
        if item_count == 0:
            item_count = 1  # 'Aucun resultat'

        total_h_est = 8 + item_count * self.ITEM_H
        usable_h = min(total_h_est, 350) - 8
        item_h_actual = (usable_h / item_count) if item_count > 0 else self.ITEM_H
        font_size = max(7, min(11, int(item_h_actual * 0.45)))
        tag_expand_font = max(5, font_size - 2)
        total_h = 8

        if coord_result:
            has_any = True
            item_data = {**coord_result, 'source': 'coord'}
            item = ResultItem(item_data, font_size=font_size, opacity=self._opacity)
            item.clicked.connect(self.result_clicked.emit)
            item.hovered.connect(self.result_hovered.emit)
            item.unhovered.connect(self.result_unhovered.emit)
            self._main_layout.addWidget(item)
            self._widgets.append(item)
            total_h += self.ITEM_H
            shown += 1

        for r in ban_results:
            if shown >= self.MAX_RESULTS:
                break
            has_any = True
            item_data = {**r, 'source': 'ban'}
            item = ResultItem(item_data, font_size=font_size, opacity=self._opacity)
            item.clicked.connect(self.result_clicked.emit)
            item.hovered.connect(self.result_hovered.emit)
            item.unhovered.connect(self.result_unhovered.emit)
            self._main_layout.addWidget(item)
            self._widgets.append(item)
            total_h += self.ITEM_H
            shown += 1

        for r in osm_results:
            if shown >= self.MAX_RESULTS:
                break
            has_any = True
            item_data = {**r, 'source': 'osm'}
            item = ResultItem(item_data, font_size=font_size, opacity=self._opacity)
            item.clicked.connect(self.result_clicked.emit)
            item.hovered.connect(self.result_hovered.emit)
            item.unhovered.connect(self.result_unhovered.emit)
            self._main_layout.addWidget(item)
            self._widgets.append(item)
            total_h += self.ITEM_H
            shown += 1

        if layer_results:
            has_any = True
            for group in layer_results:
                if shown >= self.MAX_RESULTS:
                    break
                for match in group.get('matches', []):
                    if shown >= self.MAX_RESULTS:
                        break
                    item_data = {
                        **match,
                        'source': 'layer',
                        'layer_id': group['layer_id'],
                        'layer_name': group['layer_name'],
                        'field_name': group['field_name'],
                    }
                    item = ResultItem(item_data, font_size=font_size, opacity=self._opacity)
                    item.clicked.connect(self.result_clicked.emit)
                    item.hovered.connect(self.result_hovered.emit)
                    item.unhovered.connect(self.result_unhovered.emit)
                    self._main_layout.addWidget(item)
                    self._widgets.append(item)
                    total_h += self.ITEM_H
                    shown += 1

                if shown >= self.MAX_RESULTS:
                    break
                remaining = group['total_matches'] - len(group['matches'])
                if remaining > 0:
                    all_fids = []
                    for m in group['matches']:
                        all_fids.extend(m.get('fids', []))
                    expand_data = {
                        'source': 'layer_group',
                        'layer_id': group['layer_id'],
                        'layer_name': group['layer_name'],
                        'field_name': group['field_name'],
                        'fids': all_fids,
                    }
                    expand = ExpandItem(expand_data, remaining, font_size=tag_expand_font, opacity=self._opacity)
                    expand.clicked.connect(self.result_clicked.emit)
                    self._main_layout.addWidget(expand)
                    self._widgets.append(expand)
                    total_h += self.EXPAND_H
                    shown += 1

        if not has_any:
            lbl = QLabel('  ' + tr('no_results'))
            lbl.setStyleSheet(f'color: {COLOR_MUTED}; font-size: 11px; padding: 9px 14px; border: none;')
            self._main_layout.addWidget(lbl)
            self._widgets.append(lbl)
            total_h += self.NO_RESULT_H

        h = min(total_h, 350)
        self.setFixedHeight(h)
        self.show()

    def _clear(self):
        for w in self._widgets:
            self._main_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()

    def hide_results(self):
        self._clear()
        self.hide()


# ============================================================
# Widget principal
# ============================================================

class SearchIconWidget(QWidget):
    """Icone affichant le logo de l'app."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.png')
        self._pixmap = QPixmap(icon_path) if os.path.exists(icon_path) else None
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pixmap and not self._pixmap.isNull():
            p.drawPixmap(self.rect(), self._pixmap)
        else:
            # Fallback loupe
            p.setPen(QPen(QColor(COLOR_MUTED), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawEllipse(4, 4, 11, 11)
            p.drawLine(12, 12, 18, 18)
        p.end()

class MagicSearchWidget(QDialog):
    """
    Widget flottant style carte-interactive.
    - True QDialog to float over everything without clipping.
    """

    config_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    reverse_toggled = pyqtSignal(bool)
    street_view_requested = pyqtSignal(str)
    add_favorite_requested = pyqtSignal()
    remove_favorite_requested = pyqtSignal(int)

    def __init__(self, iface, index_manager, ban_provider, osm_provider, layer_provider, parent=None, opacity=100):
        main_win = iface.mainWindow()
        super().__init__(main_win, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._opacity = opacity
        
        self.event_filter = StayOnTopEventFilter(self, main_win, reposition_cb=self._reposition_keep_center)
        main_win.installEventFilter(self.event_filter)
        
        self._iface = iface
        self._index_manager = index_manager
        self._ban_provider = ban_provider
        self._osm_provider = osm_provider
        self._layer_provider = layer_provider
        self._rubber_band = None
        self._ban_results = []
        self._osm_results = []
        self._layer_results = []
        self._coord_result = None
        self._collapsed = False
        self._custom_pos = None
        self._dragging = False
        self._drag_offset = QPoint()
        self._bar_w = SEARCH_BAR_W
        self._resizing = False
        self._resize_side = None   # 'left' or 'right'
        self._resize_start_x = 0
        self._resize_start_w = 0
        self._resize_start_global_x = 0

        self.setFixedWidth(SEARCH_BAR_W + 20)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(10, 10, 10, 10)
        self._main_layout.setSpacing(0)
        self._main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # ---- Cercle retracte ----
        self._collapsed_btn = CollapsedButton(self, opacity=self._opacity)
        self._collapsed_btn.clicked.connect(self._expand)
        self._collapsed_btn.drag_started.connect(self._on_drag_start_collapsed)
        self._collapsed_btn.drag_moved.connect(self._on_drag_move)
        self._collapsed_btn.drag_finished.connect(self._on_drag_finish)
        self._collapsed_btn.hide()

        # ---- Barre de recherche (conteneur global avec shadow) ----
        self._bar = QFrame()
        self._bar.setFixedWidth(SEARCH_BAR_W)
        self._bar.setObjectName('searchBar')
        self._update_bar_style()
        shadow = QGraphicsDropShadowEffect(self._bar)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 46))
        shadow.setOffset(0, 4)
        self._bar.setGraphicsEffect(shadow)
        self._main_layout.addWidget(self._bar)

        bar_vlayout = QVBoxLayout(self._bar)
        bar_vlayout.setContentsMargins(0, 0, 0, 0)
        bar_vlayout.setSpacing(0)

        input_container = QWidget()
        input_container.setFixedHeight(SEARCH_BAR_H)
        bar_layout = QHBoxLayout(input_container)
        bar_layout.setContentsMargins(14, 0, 4, 0)
        bar_layout.setSpacing(4)
        bar_vlayout.addWidget(input_container)

        self._input = QLineEdit()
        self._input.setPlaceholderText(tr('placeholder'))
        self._input.setFrame(False)
        self._set_input_style(muted=False)
        self._input.textChanged.connect(self._on_text_changed)
        bar_layout.addWidget(self._input)

        self._btn_clear = QPushButton('\u2715')
        self._btn_clear.setFixedSize(22, 22)
        self._btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 12px; color: {COLOR_MUTED}; border-radius: 11px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_clear.clicked.connect(lambda: self._input.clear())
        self._btn_clear.hide()
        bar_layout.addWidget(self._btn_clear)

        self._icon_search = SearchIconWidget()
        bar_layout.addWidget(self._icon_search)

        self._btn_reverse = QPushButton('?')
        self._btn_reverse.setFixedSize(26, 26)
        self._btn_reverse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_reverse.setCheckable(True)
        self._btn_reverse.setToolTip(tr('tip_reverse_geocode'))
        self._update_reverse_style()
        self._btn_reverse.toggled.connect(self.reverse_toggled.emit)
        bar_layout.addWidget(self._btn_reverse)

        self._btn_street = QToolButton()
        self._btn_street.setText('◎')
        self._btn_street.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_street.setFixedSize(26, 26)
        self._btn_street.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_street.setToolTip(tr('tip_street_view'))
        self._update_street_style()
        street_menu = QMenu(self._btn_street)
        street_menu.setStyleSheet(MENU_QSS)
        for service_key in ('google', 'mapillary', 'panoramax', 'bing'):
            act = street_menu.addAction(SERVICE_LABELS[service_key])
            act.triggered.connect(
                lambda checked=False, s=service_key: self.street_view_requested.emit(s)
            )
        street_menu.addSeparator()
        act_copy = street_menu.addAction(tr('menu_copy_coords'))
        act_copy.triggered.connect(
            lambda checked=False: self.street_view_requested.emit(COPY_COORDS)
        )
        self._btn_street.setMenu(street_menu)
        bar_layout.addWidget(self._btn_street)

        self._favorites = []
        self._search_history = []
        self._btn_more = QToolButton()
        self._btn_more.setText('\u22ee')
        self._btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_more.setFixedSize(26, 26)
        self._btn_more.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_more.setToolTip(tr('tip_more'))
        self._update_more_style()
        self._more_menu = QMenu(self._btn_more)
        self._more_menu.setStyleSheet(MENU_QSS)
        self._more_menu.aboutToShow.connect(self._rebuild_more_menu)
        self._btn_more.setMenu(self._more_menu)
        bar_layout.addWidget(self._btn_more)

        self._btn_config = QPushButton('\u2699')
        self._btn_config.setFixedSize(26, 26)
        self._btn_config.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_config.setToolTip(tr('tip_config'))
        self._btn_config.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 15px; color: {COLOR_MUTED}; border-radius: 13px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_config.clicked.connect(self.config_requested.emit)
        bar_layout.addWidget(self._btn_config)

        # Bouton synchronisation
        self._btn_sync = QPushButton()
        self._btn_sync.setFixedSize(26, 26)
        self._btn_sync.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_sync.setToolTip(tr('tip_sync_never'))
        self._btn_sync.clicked.connect(self.sync_requested.emit)
        bar_layout.addWidget(self._btn_sync)

        # Etat initial + connexion au signal
        self._update_sync_style(self._index_manager.sync_state)
        self._index_manager.sync_state_changed.connect(self._update_sync_style)

        self._btn_collapse = QPushButton('\u25B6')
        self._btn_collapse.setFixedSize(26, 26)
        self._btn_collapse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_collapse.setToolTip(tr('tip_collapse'))
        self._btn_collapse.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 10px; color: {COLOR_MUTED}; border-radius: 13px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_collapse.clicked.connect(self._collapse)
        bar_layout.addWidget(self._btn_collapse)

        # DropdownWidget (integre dans _bar)
        self._dropdown = DropdownWidget()
        self._dropdown.result_clicked.connect(self._on_result_clicked)
        self._dropdown.result_hovered.connect(self._on_result_hovered)
        self._dropdown.result_unhovered.connect(self._clear_rubber_band)
        bar_vlayout.addWidget(self._dropdown)

        # ---- Status indexation (sous la barre) ----
        self._status_label = QLabel(main_win)
        self._status_label.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._status_label.setStyleSheet(
            f'color: {VC_TURQUOISE}; font-size: 11px; padding: 2px 14px; background: transparent;'
        )
        self._status_label.hide()
        
        self._status_filter = StayOnTopEventFilter(self._status_label, main_win)
        main_win.installEventFilter(self._status_filter)

        # Drag + resize sur la barre
        self._bar.setMouseTracking(True)
        self._bar.installEventFilter(self)
        self._bar_press_pos = None
        self._bar_dragging = False

        self._ban_provider.results_ready.connect(self._on_ban_results)
        self._osm_provider.results_ready.connect(self._on_osm_results)
        self._layer_provider.results_ready.connect(self._on_layer_results)
        self._index_manager.indexing_started.connect(
            lambda: self._set_status('▶ ' + tr('status_indexing'))
        )
        self._index_manager.indexing_progress.connect(self._set_status)
        self._index_manager.indexing_finished.connect(self._hide_status)
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

        self._iface.mapCanvas().installEventFilter(self)

        self._reposition()
        self._expand()
        self.show()
        self.raise_()

    def set_opacity(self, opacity):
        self._opacity = opacity
        self._update_bar_style()
        self._dropdown.set_opacity(opacity)
        self._collapsed_btn.set_opacity(opacity)

    def _update_reverse_style(self):
        self._btn_reverse.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 14px; font-weight: bold; color: {COLOR_MUTED}; border-radius: 13px;
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
        if self._collapsed:
            self._expand()
        self._hide_dropdown()
        self._set_input_style(muted=False)
        self._input.blockSignals(True)
        self._input.setText(label)
        self._input.blockSignals(False)
        self._btn_clear.setVisible(bool(label))

    def show_reverse_not_found(self, message):
        """Affiche le message "aucune adresse trouvee" (style attenue) dans le
        champ de recherche, sans declencher une nouvelle recherche."""
        if self._collapsed:
            self._expand()
        self._hide_dropdown()
        self._set_input_style(muted=True)
        self._input.blockSignals(True)
        self._input.setText(message)
        self._input.blockSignals(False)
        self._btn_clear.setVisible(True)

    def _update_street_style(self):
        self._btn_street.setStyleSheet(f"""
            QToolButton {{
                background: transparent; border: none;
                font-size: 14px; color: {COLOR_MUTED}; border-radius: 13px;
            }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
            QToolButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)

    def _update_more_style(self):
        self._btn_more.setStyleSheet(f"""
            QToolButton {{
                background: transparent; border: none;
                font-size: 15px; font-weight: bold; color: {COLOR_MUTED}; border-radius: 13px;
            }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
            QToolButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)

    def set_favorites(self, favorites):
        self._favorites = favorites or []

    def _push_history(self, text):
        text = text.strip()
        if not text or len(text) < 2:
            return
        if text in self._search_history:
            self._search_history.remove(text)
        self._search_history.insert(0, text)
        self._search_history = self._search_history[:5]

    def _rebuild_more_menu(self):
        """Reconstruit le menu "⋮" a chaque ouverture : Favoris / Recherches
        recentes, regroupes derriere un seul bouton pour garder la barre
        compacte (la vue de rue garde son propre bouton "◎")."""
        self._more_menu.clear()

        fav_menu = self._more_menu.addMenu(tr('tip_favorites'))
        fav_menu.setStyleSheet(MENU_QSS)
        if self._favorites:
            for fav in self._favorites:
                act = fav_menu.addAction(fav.get('label', ''))
                act.triggered.connect(lambda checked=False, f=fav: self._zoom_to_favorite(f))
            fav_menu.addSeparator()
        else:
            act = fav_menu.addAction(tr('favorites_empty'))
            act.setEnabled(False)
            fav_menu.addSeparator()
        act_add = fav_menu.addAction(tr('menu_add_favorite'))
        act_add.triggered.connect(lambda checked=False: self.add_favorite_requested.emit())
        if self._favorites:
            remove_menu = fav_menu.addMenu(tr('menu_remove_favorite'))
            remove_menu.setStyleSheet(MENU_QSS)
            for idx, fav in enumerate(self._favorites):
                act = remove_menu.addAction(fav.get('label', ''))
                act.triggered.connect(
                    lambda checked=False, i=idx: self.remove_favorite_requested.emit(i)
                )

        hist_menu = self._more_menu.addMenu(tr('tip_history'))
        hist_menu.setStyleSheet(MENU_QSS)
        if self._search_history:
            for query in self._search_history:
                act = hist_menu.addAction(query)
                act.triggered.connect(lambda checked=False, q=query: self._input.setText(q))
        else:
            act = hist_menu.addAction(tr('history_empty'))
            act.setEnabled(False)

    def _zoom_to_favorite(self, fav):
        self._clear_rubber_band()
        point = geo_actions.zoom_to_point(self._iface, fav['lon'], fav['lat'])
        self._rubber_band = geo_actions.make_point_rubber(self._iface.mapCanvas(), point)

    def _update_bar_style(self):
        alpha = int(255 * (self._opacity / 100.0))
        self._bar.setStyleSheet(f"""
            QFrame#searchBar {{
                background: rgba(255, 255, 255, {alpha});
                border-radius: 10px;
                border: 1.5px solid {VC_NAVY};
            }}
        """)

    # ========================================
    # Sync button
    # ========================================

    def _update_sync_style(self, state):
        """Met a jour l'aspect du bouton sync selon l'etat.

        Rien n'etant indexe sans un clic sur ce bouton, les etats incomplets
        (rouge 'never', orange 'partial') sont peints en pastille pleine pour
        qu'ils sautent aux yeux ; l'etat complet reste discret.
        """
        self._btn_sync.setText(sync_button_glyph(state))
        self._btn_sync.setStyleSheet(sync_button_style(state, 13))
        self._sync_state = state
        self._btn_sync.setToolTip(tr(f'tip_sync_{state}') if state in
                                  ('never', 'partial', 'syncing', 'complete') else '')

    def retranslate(self):
        """Rafraichit les libelles deja construits apres un changement de langue."""
        self._input.setPlaceholderText(tr('placeholder'))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._btn_reverse.setToolTip(tr('tip_reverse_geocode'))
        self._btn_street.setToolTip(tr('tip_street_view'))
        self._btn_more.setToolTip(tr('tip_more'))
        self._btn_config.setToolTip(tr('tip_config'))
        self._btn_collapse.setToolTip(tr('tip_collapse'))
        self._update_sync_style(self._sync_state)
        # Les resultats sont reconstruits a chaque frappe : rien a retraduire ici.

    # ========================================
    # Collapse / Expand
    # ========================================

    def _collapse(self):
        self._collapsed = True
        self._dropdown.hide_results()
        self._input.clear()
        self._bar.hide()
        self._main_layout.setSizeConstraint(QVBoxLayout.SetDefaultConstraint)
        self.setMinimumSize(0, 0)
        self.setFixedSize(COLLAPSED_SIZE + 20, COLLAPSED_SIZE + 20)
        self._collapsed_btn.setGeometry(10, 10, COLLAPSED_SIZE, COLLAPSED_SIZE)
        self._collapsed_btn.show()
        self._collapsed_btn.raise_()
        self._reposition_keep_center()

    def _expand(self):
        self._collapsed = False
        self._collapsed_btn.hide()
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self._main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self._bar.setFixedWidth(self._bar_w)
        self.setFixedWidth(self._bar_w + 20)
        self._bar.show()
        self.adjustSize()
        self._reposition_keep_center()
        self._input.setFocus()

    def _reposition_keep_center(self):
        if self._custom_pos is not None:
            self._clamp_position(self._custom_pos)
        else:
            self._reposition()

    # ========================================
    # Position : centree en haut par defaut
    # ========================================

    def _reposition(self):
        if self._custom_pos is not None:
            self._clamp_position(self._custom_pos)
            return
        canvas = self._iface.mapCanvas()
        x = (canvas.width() - self.width()) // 2
        y = MARGIN_TOP
        global_pos = canvas.mapToGlobal(QPoint(x, y))
        self.move(global_pos)
        self._update_sub_widgets_pos()
        self.raise_()

    def _clamp_position(self, pos):
        canvas = self._iface.mapCanvas()
        global_pos = canvas.mapToGlobal(pos)
        self.move(global_pos)
        self._custom_pos = pos
        self._update_sub_widgets_pos()

    def _update_sub_widgets_pos(self):
        """Met a jour la position du status et du dropdown par rapport a la barre."""
        pos = self.pos()
        self._status_label.move(pos.x() + 10, pos.y() + self.height() - 4)
        self._status_label.setFixedWidth(self.width() - 20)
        self._status_label.raise_()

    def _set_bar_width(self, new_w, adjust_left=False):
        """Resize la barre. Si adjust_left=True, decale la position pour garder le bord droit fixe."""
        old_w = self._bar_w
        self._bar_w = new_w
        self._bar.setFixedWidth(new_w)
        self.setFixedWidth(new_w + 20)
        if adjust_left and self._custom_pos is not None:
            # Le bord droit doit rester fixe : decaler x de (old_w - new_w)
            dx = old_w - new_w
            new_pos = QPoint(self._custom_pos.x() + dx, self._custom_pos.y())
            self._custom_pos = new_pos
            canvas = self._iface.mapCanvas()
            self.move(canvas.mapToGlobal(new_pos))
        elif adjust_left:
            # Pas encore de position custom : recalculer depuis la position globale actuelle
            cur_global = self.pos()
            dx = old_w - new_w
            self.move(cur_global.x() + dx, cur_global.y())
        self._update_sub_widgets_pos()

    # ========================================
    # Drag & drop (barre expandee)
    # ========================================

    def _bar_edge(self, local_x):
        """Returns 'left', 'right' or None depending on proximity to bar edge."""
        if local_x <= RESIZE_HANDLE:
            return 'left'
        if local_x >= self._bar.width() - RESIZE_HANDLE:
            return 'right'
        return None

    def eventFilter(self, obj, event):
        if obj == self._iface.mapCanvas() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._reposition()
            return False

        if obj == self._bar:
            etype = event.type()

            # --- Cursor change on hover ---
            if etype == QEvent.Type.MouseMove and not self._bar_dragging and not self._resizing:
                edge = self._bar_edge(event_pos(event).x())
                if edge:
                    self._bar.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                else:
                    self._bar.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

            # --- Button press: start resize or drag ---
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                edge = self._bar_edge(event_pos(event).x())
                if edge:
                    self._resizing = True
                    self._resize_side = edge
                    self._resize_start_global_x = event_global_pos(event).x()
                    self._resize_start_w = self._bar_w
                    return True
                else:
                    self._bar_press_pos = event_global_pos(event)
                    self._bar_dragging = False
                    return False

            # --- Mouse move: resize or drag ---
            if etype == QEvent.Type.MouseMove:
                if self._resizing:
                    dx = event_global_pos(event).x() - self._resize_start_global_x
                    if self._resize_side == 'right':
                        new_w = max(BAR_MIN_W, min(BAR_MAX_W, self._resize_start_w + dx))
                    else:  # left
                        new_w = max(BAR_MIN_W, min(BAR_MAX_W, self._resize_start_w - dx))
                    self._set_bar_width(new_w, adjust_left=(self._resize_side == 'left'))
                    return True

                if self._bar_press_pos is not None:
                    delta = event_global_pos(event) - self._bar_press_pos
                    if not self._bar_dragging and delta.manhattanLength() > DRAG_THRESHOLD:
                        self._bar_dragging = True
                        self._drag_offset = self._bar_press_pos - self.mapToGlobal(QPoint(0, 0))
                    if self._bar_dragging:
                        canvas = self._iface.mapCanvas()
                        global_pos = event_global_pos(event) - self._drag_offset
                        local_pos = canvas.mapFromGlobal(global_pos)
                        self._custom_pos = local_pos
                        self._clamp_position(local_pos)
                        return True

            # --- Button release ---
            if etype == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._resizing:
                    self._resizing = False
                    self._resize_side = None
                    self._bar.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                    return True
                self._bar_press_pos = None
                if self._bar_dragging:
                    self._bar_dragging = False
                    return True

        return False

    def _on_drag_start_collapsed(self, global_pos):
        self._dragging = True
        self._drag_offset = global_pos - self.mapToGlobal(QPoint(0, 0))

    def _on_drag_move(self, global_pos):
        if self._dragging:
            canvas = self._iface.mapCanvas()
            local_pos = canvas.mapFromGlobal(global_pos - self._drag_offset)
            self._custom_pos = local_pos
            self._clamp_position(local_pos)

    def _on_drag_finish(self):
        self._dragging = False

    # ========================================
    # Status indexation
    # ========================================

    def _set_status(self, text):
        self._status_label.setText(text)
        self._status_label.show()
        self._update_sub_widgets_pos()

    def _hide_status(self):
        self._status_label.hide()

    # ========================================
    # Recherche
    # ========================================

    def _on_index_changed(self, *args):
        """Debounce : attend 1s apres le dernier layer_ready avant de relancer."""
        self._index_debounce.start()

    def _on_index_updated(self, *args):
        """Relance la recherche couches si du texte est saisi."""
        self._index_debounce.stop()
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text)

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
        self._set_input_style(muted=False)
        self._btn_clear.setVisible(bool(text))
        if not text or len(text) < 2:
            self._layer_search_debounce.stop()
            self._hide_dropdown()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._coord_result = None
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            return

        coord = parse_coordinates(text)
        if coord:
            lon, lat = coord_to_lonlat(coord)
            coord['lon'], coord['lat'] = lon, lat
            self._layer_search_debounce.stop()
            self._ban_provider.cancel()
            self._osm_provider.cancel()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._coord_result = coord
            self._update_dropdown()
            return

        self._coord_result = None
        self._ban_provider.search(text)
        self._osm_provider.search(text)
        self._layer_search_debounce.start()

    def _do_layer_search(self):
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text)

    def _on_ban_results(self, results):
        self._ban_results = results
        self._update_dropdown()

    def _on_osm_results(self, results):
        self._osm_results = results
        self._update_dropdown()

    def _on_layer_results(self, results):
        self._layer_results = results
        self._update_dropdown()

    def _update_dropdown(self):
        if self._collapsed:
            return
        text = self._input.text()
        if not text or len(text) < 2:
            return

        self._dropdown.show_results(
            self._ban_results, self._osm_results, self._layer_results, self._coord_result
        )
        self.adjustSize()
        self._update_sub_widgets_pos()

    def _hide_dropdown(self):
        self._dropdown.hide_results()
        if not self._collapsed:
            self.adjustSize()
            self._update_sub_widgets_pos()
        self._clear_rubber_band()

    # ========================================
    # Actions sur resultats
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
        self._hide_dropdown()
        self._input.clear()

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

    # ========================================
    # Public API
    # ========================================

    def set_focus(self):
        if self._collapsed:
            self._expand()
        self._input.setFocus()
        self.show()
        self.raise_()

    def reset_position(self):
        self._custom_pos = None
        self._reposition()

    def cleanup(self):
        self._clear_rubber_band()
        self._dropdown.hide_results()
        self._dropdown.setParent(None)
        self._dropdown.deleteLater()
        self._status_label.setParent(None)
        self._status_label.deleteLater()
        canvas = self._iface.mapCanvas()
        canvas.removeEventFilter(self)
        self._bar.removeEventFilter(self)
        self.setParent(None)
        self.deleteLater()
