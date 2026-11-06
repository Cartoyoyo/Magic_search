"""
Search Widget - Barre de recherche flottante style carte-interactive.
- Centree en haut du canevas par defaut
- Retractable en cercle (fleche de retractation)
- Clic sur le cercle = deplie la barre
- Drag & drop : maintenir clic gauche pour deplacer
- Dropdown = widget separe (pas clippe par le parent)
"""

import os
import html
import math
from qgis.PyQt.QtWidgets import (
    QWidget, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGraphicsDropShadowEffect, QScrollArea, QSizePolicy, QProgressBar,
    QPushButton, QDialog, QToolButton, QMenu
)
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal, QPoint, QEvent, QRect, QRectF, QSize
from qgis.PyQt.QtGui import QColor, QCursor, QPainter, QPen, QBrush, QPixmap, QIcon

from .ui_common import StayOnTopEventFilter, sync_button_glyph
from ..core.qt_compat import event_pos, event_global_pos
from ..core import geo_actions
from ..core.street_view_tool import SERVICE_LABELS, COPY_COORDS
from ..core.coord_parser import coordinate_candidates, to_lonlat as coord_to_lonlat
from ..core.index_manager import normalize_text, _query_words
from ..i18n import tr, current_lang

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
BAR_H = 44                 # pilule (modele M2c)

# Couleur de l'etat de l'index : pastille de la barre et jauge du pied.
SYNC_COLORS = {
    'never': '#dc2626',
    'partial': '#f29400',
    'syncing': '#d97706',
    'complete': '#16a34a',
}


def _binoculars_pixmap(color, size=18, ratio=2.0):
    """Jumelles dessinees (aucune police Windows n'a de pictogramme fiable) :
    deux oculaires, deux objectifs ronds, un pont."""
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    s = size / 18.0
    p.drawRoundedRect(QRectF(3.2 * s, 3 * s, 3.6 * s, 6 * s), 1.2 * s, 1.2 * s)    # oculaire gauche
    p.drawRoundedRect(QRectF(11.2 * s, 3 * s, 3.6 * s, 6 * s), 1.2 * s, 1.2 * s)   # oculaire droit
    p.drawRect(QRectF(7.5 * s, 8 * s, 3 * s, 2.6 * s))                              # pont
    p.drawEllipse(QRectF(0.8 * s, 7.6 * s, 8 * s, 8 * s))                            # objectif gauche
    p.drawEllipse(QRectF(9.2 * s, 7.6 * s, 8 * s, 8 * s))                            # objectif droit
    p.setBrush(QBrush(QColor('white')))
    p.drawEllipse(QRectF(2.9 * s, 9.7 * s, 3.8 * s, 3.8 * s))                        # verres
    p.drawEllipse(QRectF(11.3 * s, 9.7 * s, 3.8 * s, 3.8 * s))
    p.end()
    return px


def _binoculars_icon():
    """Icone de la vue de rue : grise au repos, marine au survol."""
    icon = QIcon()
    icon.addPixmap(_binoculars_pixmap(COLOR_MUTED), QIcon.Mode.Normal)
    icon.addPixmap(_binoculars_pixmap(VC_NAVY), QIcon.Mode.Active)
    return icon


def _fmt_count(n):
    """1234567 -> '1,2 M' ; 12345 -> '12 k' : le pied de liste reste court."""
    sep = '.' if current_lang() == 'en' else ','
    if n >= 1_000_000:
        return ('%.1f M' % (n / 1_000_000)).replace('.', sep)
    if n >= 10_000:
        return '%d k' % round(n / 1000)
    return str(n)


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


ROW_H = 30                 # ligne "normale" (modele M2c)
ROW_H_MIN = 20             # ligne la plus serree
FOOTER_H = 26
ROWS_COMPACT = 14          # reponses affichees d'office
ROWS_ALL = 60              # reponses affichees apres Tab "tout voir"
LIST_MAX_H = 352           # hauteur de liste (~ celle de l ancienne barre) ; au-dela, elle defile


def _row_metrics(n_rows):
    """Densite adaptative : (hauteur de ligne, police valeur, police detail,
    detail sur la meme ligne).

    Peu de reponses : lignes de 30 px sur deux niveaux. Plus il y en a, plus
    lignes et polices se resserrent pour tout faire tenir dans LIST_MAX_H,
    jusqu'a 20 px ; sous 26 px le detail "couche · champ" passe a droite de
    la valeur. Au-dela, la liste defile.
    """
    if n_rows * ROW_H <= LIST_MAX_H:
        row_h = ROW_H
    else:
        row_h = max(ROW_H_MIN, LIST_MAX_H // max(1, n_rows))
    main = 12 if row_h >= 28 else (11 if row_h >= 25 else 10)
    return row_h, main, main - 2, row_h < 26


def _highlight(text, query):
    """Met en gras la partie de `text` qui correspond a `query`.

    La comparaison se fait sur le texte normalise (accents, casse, ligatures),
    comme la recherche elle-meme : "eglise" surligne "Église". Chaque
    caractere est normalise seul pour garder la correspondance des positions.
    """
    text = str(text)
    q = normalize_text(query or '').strip()
    if not q:
        return html.escape(text)
    norm, owner = [], []
    for i, ch in enumerate(text):
        for c in normalize_text(ch):
            norm.append(c)
            owner.append(i)
    flat = ''.join(norm)
    # La phrase entiere si elle y est, sinon chaque mot (recherche par mots
    # dans le desordre : "chatel step" -> STEP Chatel Montagne).
    pos = flat.find(q)
    needles = [q] if pos >= 0 else _query_words(q)
    bold = [False] * len(text)
    for w in needles:
        start = flat.find(w)
        while start >= 0:
            for k in range(start, start + len(w)):
                bold[owner[k]] = True
            start = flat.find(w, start + len(w))
    if not any(bold):
        return html.escape(text)
    out, inside = [], False
    for ch, b in zip(text, bold):
        if b != inside:
            out.append('<b>' if b else '</b>')
            inside = b
        out.append(html.escape(ch))
    if inside:
        out.append('</b>')
    return ''.join(out)


def _distance_text(center, lon, lat):
    """Distance a vol d'oiseau depuis le centre de la carte, ou ''."""
    if not center or lon is None or lat is None:
        return ''
    lon0, lat0 = center
    p1, p2 = math.radians(lat0), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - lon0)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))
    sep = '.' if current_lang() == 'en' else ','
    if km < 1:
        return '%d m' % round(km * 1000)
    if km < 10:
        return ('%.1f km' % km).replace('.', sep)
    return '%d km' % round(km)


# Types renvoyes par l'API BAN (en anglais) -> libelles traduits
BAN_TYPES = {
    'housenumber': 'ban_housenumber',
    'street': 'ban_street',
    'locality': 'ban_locality',
    'municipality': 'ban_municipality',
}


def _source_color(data):
    source = data.get('source')
    if source == 'ban':
        return VC_TURQUOISE
    if source == 'osm':
        return '#f59e0b'
    if source == 'coord':
        return VC_NAVY
    return _color_for_layer(data.get('layer_id', ''))[1]


class ResultItem(QFrame):
    """Une reponse sur deux niveaux (modele M2c) : la valeur, correspondance
    en gras, puis "couche · champ" en gris ; a droite le nombre d'objets ou
    la distance ; a gauche une bordure a la couleur de la source."""

    clicked = pyqtSignal(dict)
    hovered = pyqtSignal(dict)
    unhovered = pyqtSignal()

    def __init__(self, data, query='', center=None, parent=None, opacity=100,
                 metrics=None):
        super().__init__(parent)
        self._data = data
        self._selected = False
        self._alpha = int(255 * (opacity / 100.0))
        self._border = _source_color(data)
        row_h, f_main, f_sub, inline = metrics or _row_metrics(1)
        self.setObjectName('resultItem')
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)
        self.setFixedHeight(row_h)
        self._apply_style()

        source = data.get('source')
        if source in ('ban', 'osm'):
            main = _highlight(data.get('label', ''), query)
            kind = data.get('type', '')
            if source == 'ban' and kind in BAN_TYPES:
                kind = tr(BAN_TYPES[kind])
            sub = '%s %s%s' % (tr('sub_address'), source.upper(),
                               ' · ' + kind if kind else '')
            right = _distance_text(center, data.get('lon'), data.get('lat'))
        elif source == 'coord':
            main = html.escape(data.get('label', ''))
            sub = tr('sub_coord')
            right = _distance_text(center, data.get('lon'), data.get('lat'))
        else:
            main = _highlight(data.get('original', ''), query)
            sub = '%s · %s' % (data.get('layer_name', ''), data.get('field_name', ''))
            right = tr('count_objects', n=len(data.get('fids', [])))

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 1, 10, 1)
        row.setSpacing(8)
        # Deux niveaux en temps normal ; une seule ligne quand la liste se
        # resserre (le detail passe a droite de la valeur).
        col = QHBoxLayout() if inline else QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8 if inline else 0)
        lbl_main = QLabel(main)
        lbl_main.setTextFormat(Qt.TextFormat.RichText)
        lbl_main.setStyleSheet(f'color: {COLOR_TEXT}; font-size: {f_main}px; border: none; background: transparent;')
        lbl_sub = QLabel(html.escape(sub))
        lbl_sub.setStyleSheet(f'color: {COLOR_MUTED}; font-size: {f_sub}px; border: none; background: transparent;')
        for lbl in (lbl_main, lbl_sub):
            # Une valeur trop longue est coupee au lieu d'elargir la liste
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            col.addWidget(lbl, 3 if (inline and lbl is lbl_main) else 2 if inline else 0)
        row.addLayout(col, 1)
        lbl_right = QLabel(right)
        lbl_right.setStyleSheet(f'color: {COLOR_TEXT}; font-size: {max(9, f_sub)}px; font-weight: 600; border: none; background: transparent;')
        lbl_right.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(lbl_right, 0, Qt.AlignmentFlag.AlignVCenter)

    def data(self):
        return self._data

    def set_selected(self, selected):
        if selected != self._selected:
            self._selected = selected
            self._apply_style()

    def _apply_style(self):
        bg = 'rgba(230, 246, 244, %d)' % self._alpha if self._selected \
            else 'rgba(255, 255, 255, %d)' % self._alpha
        self.setStyleSheet(f"""
            #resultItem {{
                background: {bg};
                border-left: 3px solid {self._border};
                border-bottom: 1px solid #f1f5f9;
            }}
            #resultItem:hover {{ background: rgba(240, 244, 248, {self._alpha}); }}
        """)

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
    """"... N autres" sous une couche : clic = zoom sur l'ensemble."""

    clicked = pyqtSignal(dict)

    def __init__(self, data, remaining, parent=None, opacity=100, height=20, font=10):
        super().__init__(parent)
        self._data = data
        self.setObjectName('expandItem')
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(height)
        alpha = int(255 * (opacity / 100.0))
        self.setStyleSheet(f"""
            #expandItem {{
                background: rgba(255, 255, 255, {alpha});
                border-left: 3px solid {_source_color(data)};
                border-bottom: 1px solid #f1f5f9;
            }}
            #expandItem:hover {{ background: rgba(240, 244, 248, {alpha}); }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 10, 0)
        lbl = QLabel(tr('expand_more', count=remaining))
        lbl.setStyleSheet(f'color: {VC_TURQUOISE}; font-size: {font}px; border: none; background: transparent;')
        layout.addWidget(lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)


# ============================================================
# Liste de resultats (carte separee sous la barre)
# ============================================================

class DropdownWidget(QFrame):
    """Liste de resultats du modele M2c : carte arrondie sous la pilule,
    lignes serrees, pied avec compteur et etat de l'index."""

    result_clicked = pyqtSignal(dict)
    result_hovered = pyqtSignal(dict)
    result_unhovered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('dropdown')
        self._opacity = 100
        self._widgets = []
        self._items = []           # ResultItem selectionnables, dans l'ordre
        self._sel = -1
        self._apply_style()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 40))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet('QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }')
        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._scroll.setWidget(self._rows)
        outer.addWidget(self._scroll)

        self._footer = QWidget()
        self._footer.setFixedHeight(FOOTER_H)
        self._footer.setObjectName('footer')
        self._footer.setStyleSheet('#footer { border-top: 1px solid %s; background: transparent; }' % COLOR_BORDER)
        fl = QHBoxLayout(self._footer)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(8)
        self._lbl_count = QLabel()
        self._lbl_state = QLabel()
        self._gauge = QProgressBar()
        self._gauge.setTextVisible(False)
        self._gauge.setFixedSize(70, 5)
        self._gauge.setRange(0, 100)
        self._lbl_stats = QLabel()
        for lbl in (self._lbl_count, self._lbl_state, self._lbl_stats):
            lbl.setStyleSheet(f'color: {COLOR_MUTED}; font-size: 10px; background: transparent;')
        fl.addWidget(self._lbl_count)
        fl.addStretch(1)
        fl.addWidget(self._lbl_state)
        fl.addWidget(self._gauge)
        fl.addWidget(self._lbl_stats)
        outer.addWidget(self._footer)
        self.hide()

    def _apply_style(self):
        alpha = int(255 * (self._opacity / 100.0))
        self.setStyleSheet(f"""
            #dropdown {{
                background: rgba(255, 255, 255, {alpha});
                border-radius: 14px;
            }}
        """)

    def set_opacity(self, opacity):
        self._opacity = opacity
        self._apply_style()

    def set_index_state(self, state, ratio, layers, values):
        """Pied de liste : etat de l'index, jauge, volume indexe."""
        color = SYNC_COLORS.get(state, SYNC_COLORS['never'])
        self._lbl_state.setText(f'<span style="color:{color}">●</span> ' + tr('state_' + state))
        self._gauge.setValue(int(round(ratio * 100)))
        self._gauge.setStyleSheet(f"""
            QProgressBar {{ background: {COLOR_BORDER}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}
        """)
        self._lbl_stats.setText(tr('footer_stats', layers=layers,
                                   values=_fmt_count(values)))

    def show_results(self, ban_results, osm_results, layer_results,
                     coord_results=(), query='', center=None, show_all=False):
        self._clear()
        limit = ROWS_ALL if show_all else ROWS_COMPACT
        shown = 0
        # 1er temps : les lignes a afficher ; 2e temps : leur taille, qui
        # depend de leur nombre (densite adaptative, cf. _row_metrics).
        rows = []   # ('item', data) ou ('expand', data, restant)

        for coord in coord_results:
            rows.append(('item', {**coord, 'source': 'coord'}))
            shown += 1
        for source, results in (('ban', ban_results), ('osm', osm_results)):
            for r in results:
                if shown >= limit:
                    break
                rows.append(('item', {**r, 'source': source}))
                shown += 1

        total = len(coord_results) + len(ban_results) + len(osm_results)
        for group in layer_results:
            total += group['total_matches']
            for match in group.get('matches', []):
                if shown >= limit:
                    break
                rows.append(('item', {**match, 'source': 'layer',
                                      'layer_id': group['layer_id'],
                                      'layer_name': group['layer_name'],
                                      'field_name': group['field_name']}))
                shown += 1
            remaining = group['total_matches'] - len(group['matches'])
            if remaining > 0 and shown < limit:
                fids = []
                for m in group['matches']:
                    fids.extend(m.get('fids', []))
                rows.append(('expand', {'source': 'layer_group',
                                        'layer_id': group['layer_id'],
                                        'layer_name': group['layer_name'],
                                        'field_name': group['field_name'],
                                        'fids': fids}, remaining))

        metrics = _row_metrics(len(rows))
        row_h, f_main, f_sub, _inline = metrics
        expand_h = max(18, row_h - 8)
        rows_h = 0
        for row in rows:
            if row[0] == 'item':
                item = ResultItem(row[1], query=query, center=center,
                                  opacity=self._opacity, metrics=metrics)
                item.clicked.connect(self.result_clicked.emit)
                item.hovered.connect(self.result_hovered.emit)
                item.unhovered.connect(self.result_unhovered.emit)
                self._rows_layout.addWidget(item)
                self._widgets.append(item)
                self._items.append(item)
                rows_h += row_h
            else:
                expand = ExpandItem(row[1], row[2], opacity=self._opacity,
                                    height=expand_h, font=max(9, f_sub))
                expand.clicked.connect(self.result_clicked.emit)
                self._rows_layout.addWidget(expand)
                self._widgets.append(expand)
                rows_h += expand_h

        if not self._widgets:
            lbl = QLabel(tr('no_results'))
            lbl.setStyleSheet(f'color: {COLOR_MUTED}; font-size: 11px; padding: 8px 14px; background: transparent;')
            self._rows_layout.addWidget(lbl)
            self._widgets.append(lbl)
            rows_h = 34

        if total > shown:
            self._lbl_count.setText('%s · %s' % (tr('footer_count', shown=shown, total=total),
                                                 tr('footer_less' if show_all else 'footer_all')))
        elif show_all and total > ROWS_COMPACT:
            self._lbl_count.setText('%d · %s' % (total, tr('footer_less')))
        else:
            self._lbl_count.setText(str(total) if total else '')

        # Hauteur reelle du contenu : sans elle, la zone de defilement tasse
        # les lignes a la hauteur visible au lieu de faire defiler.
        self._rows.setMinimumHeight(rows_h)
        list_h = min(rows_h, LIST_MAX_H)
        self._scroll.setFixedHeight(list_h)
        self.setFixedHeight(list_h + FOOTER_H)
        self._sel = 0 if self._items else -1
        if self._items:
            self._items[0].set_selected(True)
        self.show()

    # ---- Navigation clavier ----

    def move_selection(self, delta):
        if not self._items:
            return
        if 0 <= self._sel < len(self._items):
            self._items[self._sel].set_selected(False)
        self._sel = max(0, min(len(self._items) - 1, self._sel + delta))
        item = self._items[self._sel]
        item.set_selected(True)
        self._scroll.ensureWidgetVisible(item, 0, 0)
        self.result_hovered.emit(item.data())

    def selected_data(self):
        if 0 <= self._sel < len(self._items):
            return self._items[self._sel].data()
        return None

    def _clear(self):
        for w in self._widgets:
            self._rows_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self._items = []
        self._sel = -1

    def hide_results(self):
        self._clear()
        self.hide()


# ============================================================
# Widget principal
# ============================================================

class PillMixin:
    """Pilule et liste du modele M2c, communes a la barre flottante et au
    panneau ancrable : perimetre, menu ⋮, puce "?", etat de l'index, clavier.

    La classe hote fournit self._iface, self._index_manager, les fournisseurs,
    les signaux (reverse_toggled, scope_changed...), _on_text_changed,
    _do_layer_search, _on_result_clicked/_hovered, _clear_rubber_band, et les
    deux points d'accroche _close_list() / _refresh_list().
    """

    def _build_pill(self, logo=False):
        """Construit la pilule (self._bar) et la liste (self._dropdown).
        L'appelant les place dans sa mise en page puis appelle
        _update_sync_style(self._sync_state)."""
        # ---- Pilule (modele M2c) : perimetre, saisie, etat de l'index, menu ----
        self._bar = QFrame()
        self._bar.setFixedHeight(BAR_H)
        self._bar.setObjectName('searchBar')
        self._update_bar_style()
        shadow = QGraphicsDropShadowEffect(self._bar)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(19, 35, 91, 46))
        shadow.setOffset(0, 3)
        self._bar.setGraphicsEffect(shadow)

        bar_layout = QHBoxLayout(self._bar)
        bar_layout.setContentsMargins(6, 0, 6, 0)
        bar_layout.setSpacing(4)

        if logo:
            # Logo du plugin en tete de pilule (panneau ancrable)
            icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon.png')
            if os.path.exists(icon_path):
                self._logo_label = QLabel()
                self._logo_label.setPixmap(QPixmap(icon_path).scaled(
                    22, 22, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                self._logo_label.setStyleSheet('background: transparent; margin-left: 4px;')
                bar_layout.addWidget(self._logo_label)

        # Perimetre de la recherche dans les couches (cochees / toutes) :
        # l'ancienne case de la configuration devient un geste direct.
        self._search_all = False
        self._btn_scope = QToolButton()
        self._btn_scope.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_scope.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Bordure declaree (meme teinte que le fond) : sans elle, Qt dessine
        # un bouton a menu en rectangle et ignore l'arrondi. Hauteur fixe pour
        # que la puce epouse la courbe gauche de la pilule.
        self._btn_scope.setFixedHeight(30)
        self._btn_scope.setStyleSheet(f"""
            QToolButton {{
                background: #eef2ff; color: {VC_NAVY};
                border: 1px solid #eef2ff; border-radius: 15px;
                padding: 0 12px; font-size: 11px; font-weight: 600;
            }}
            QToolButton:hover {{ background: #e0e7ff; border-color: #e0e7ff; }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
        """)
        scope_menu = QMenu(self._btn_scope)
        scope_menu.setStyleSheet(MENU_QSS)
        self._act_scope_checked = scope_menu.addAction(tr('menu_scope_checked'))
        self._act_scope_all = scope_menu.addAction(tr('menu_scope_all'))
        for act, value in ((self._act_scope_checked, False), (self._act_scope_all, True)):
            act.setCheckable(True)
            act.triggered.connect(lambda checked=False, v=value: self._on_scope_chosen(v))
        self._btn_scope.setMenu(scope_menu)
        self._update_scope_text()
        bar_layout.addWidget(self._btn_scope)

        self._input = QLineEdit()
        self._input.setPlaceholderText(tr('placeholder'))
        self._input.setFrame(False)
        self._set_input_style(muted=False)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        bar_layout.addWidget(self._input)

        # Outil "?" actif : rappel visible dans la pilule (l'outil se lance
        # depuis le menu ⋮), un clic l'arrete.
        self._reverse_active = False
        self._chip_reverse = QPushButton('?')
        self._chip_reverse.setFixedSize(24, 24)
        self._chip_reverse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._chip_reverse.setToolTip(tr('tip_reverse_active'))
        self._chip_reverse.setStyleSheet(f"""
            QPushButton {{
                background: {VC_TURQUOISE}; color: white; border: none;
                border-radius: 12px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #00b8ac; }}
        """)
        self._chip_reverse.clicked.connect(lambda: self.reverse_toggled.emit(False))
        self._chip_reverse.hide()
        bar_layout.addWidget(self._chip_reverse)

        self._btn_clear = QPushButton('✕')
        self._btn_clear.setFixedSize(24, 24)
        self._btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_clear.setToolTip(tr('tip_clear'))
        self._btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 12px; color: {COLOR_MUTED}; border-radius: 12px;
            }}
            QPushButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        self._btn_clear.clicked.connect(lambda: self._input.clear())
        self._btn_clear.hide()
        bar_layout.addWidget(self._btn_clear)

        # Vue de rue : bouton direct dans la pilule (Google, Mapillary,
        # Panoramax, Bing ou copie des coordonnees, puis clic sur la carte)
        self._btn_street = QToolButton()
        self._btn_street.setIcon(_binoculars_icon())
        self._btn_street.setIconSize(QSize(18, 18))
        self._btn_street.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_street.setFixedSize(26, 26)
        self._btn_street.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_street.setToolTip(tr('tip_street_view'))
        self._btn_street.setStyleSheet(f"""
            QToolButton {{
                background: transparent; border: none;
                font-size: 15px; color: {COLOR_MUTED}; border-radius: 13px;
            }}
            QToolButton::menu-indicator {{ image: none; width: 0; }}
            QToolButton:hover {{ background: #f1f5f9; color: {VC_NAVY}; }}
        """)
        street_menu = QMenu(self._btn_street)
        street_menu.setStyleSheet(MENU_QSS)
        for service_key in ('google', 'mapillary', 'panoramax', 'bing'):
            act = street_menu.addAction(SERVICE_LABELS[service_key])
            act.triggered.connect(
                lambda checked=False, sk=service_key: self.street_view_requested.emit(sk))
        street_menu.addSeparator()
        act_copy = street_menu.addAction(tr('menu_copy_coords'))
        act_copy.triggered.connect(
            lambda checked=False: self.street_view_requested.emit(COPY_COORDS))
        self._btn_street.setMenu(street_menu)
        self._act_copy_coords = act_copy

        # Etat de l'index : pastille de couleur + bouton de synchronisation
        self._dot = QLabel()
        self._dot.setFixedSize(9, 9)
        bar_layout.addWidget(self._dot)

        self._btn_sync = QPushButton()
        self._btn_sync.setFixedSize(26, 26)
        self._btn_sync.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_sync.clicked.connect(self.sync_requested.emit)
        bar_layout.addWidget(self._btn_sync)
        # Jumelles a droite de la synchronisation (demande utilisateur)
        bar_layout.addWidget(self._btn_street)

        # Menu ⋮ : adresse au clic, vue de rue, favoris, recentes,
        # configuration, repli (reconstruit a chaque ouverture).
        self._favorites = []
        self._search_history = []
        self._btn_more = QToolButton()
        self._btn_more.setText('⋮')
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

        self._sync_state = self._index_manager.sync_state
        self._index_manager.sync_state_changed.connect(self._update_sync_style)

        # ---- Liste de resultats : carte separee ----
        self._show_all = False
        self._dropdown = DropdownWidget()
        self._dropdown.result_clicked.connect(self._on_result_clicked)
        self._dropdown.result_hovered.connect(self._on_result_hovered)
        self._dropdown.result_unhovered.connect(self._clear_rubber_band)


    def set_reverse_active(self, active):
        """Suit l'etat reel de l'outil "?" (ex: arrete si l'utilisateur bascule
        vers un autre outil QGIS) : puce turquoise dans la pilule, case
        cochee dans le menu ⋮."""
        self._reverse_active = bool(active)
        self._chip_reverse.setVisible(self._reverse_active)

    # ---- Perimetre ----

    def set_scope(self, search_all):
        """Perimetre courant (False = couches cochees, True = toutes)."""
        self._search_all = bool(search_all)
        self._update_scope_text()

    def _update_scope_text(self):
        label = tr('scope_all') if self._search_all else tr('scope_checked')
        self._btn_scope.setText('◉ %s ▾' % label)
        self._btn_scope.setToolTip(tr('tip_scope'))
        self._act_scope_checked.setText(tr('menu_scope_checked'))
        self._act_scope_all.setText(tr('menu_scope_all'))
        self._act_scope_checked.setChecked(not self._search_all)
        self._act_scope_all.setChecked(self._search_all)

    def _on_scope_chosen(self, search_all):
        self.set_scope(search_all)
        self.scope_changed.emit(self._search_all)
        # Le filtre s'applique a la recherche : relancer sur la saisie en cours
        self._do_layer_search()

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
        """Reconstruit le menu "⋮" a chaque ouverture. Modele M2c : la pilule
        ne garde que l'essentiel, tous les outils sont ici."""
        self._more_menu.clear()

        act_rev = self._more_menu.addAction('?   ' + tr('menu_reverse'))
        act_rev.setCheckable(True)
        act_rev.setChecked(self._reverse_active)
        act_rev.setToolTip(tr('tip_reverse_geocode'))
        act_rev.triggered.connect(lambda checked=False: self.reverse_toggled.emit(checked))
        # La vue de rue a son propre bouton "◎" dans la pilule.
        self._more_menu.addSeparator()

        fav_menu = self._more_menu.addMenu('★   ' + tr('tip_favorites'))
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

        hist_menu = self._more_menu.addMenu('↺   ' + tr('tip_history'))
        hist_menu.setStyleSheet(MENU_QSS)
        if self._search_history:
            for query in self._search_history:
                act = hist_menu.addAction(query)
                act.triggered.connect(lambda checked=False, q=query: self._input.setText(q))
        else:
            act = hist_menu.addAction(tr('history_empty'))
            act.setEnabled(False)

        self._more_menu.addSeparator()
        act_cfg = self._more_menu.addAction('⚙   ' + tr('tip_config'))
        act_cfg.triggered.connect(lambda checked=False: self.config_requested.emit())
        if hasattr(self, '_collapse'):
            act_col = self._more_menu.addAction('▸   ' + tr('menu_collapse'))
            act_col.triggered.connect(lambda checked=False: self._collapse())

    def _zoom_to_favorite(self, fav):
        self._clear_rubber_band()
        point = geo_actions.zoom_to_point(self._iface, fav['lon'], fav['lat'])
        self._rubber_band = geo_actions.make_point_rubber(self._iface.mapCanvas(), point)

    def _update_bar_style(self):
        alpha = int(255 * (self._opacity / 100.0))
        self._bar.setStyleSheet(f"""
            QFrame#searchBar {{
                background: rgba(255, 255, 255, {alpha});
                border-radius: 22px;
                border: 1px solid #dbe2ea;
            }}
        """)

    # ========================================
    # Sync button
    # ========================================

    def _update_sync_style(self, state):
        """Etat de l'index (modele M2c) : pastille de couleur et glyphe du
        bouton de synchronisation dans la pilule, jauge dans le pied de liste.

        Rien n'etant indexe sans un clic sur ce bouton, l'etat 'never'
        remplace la fleche par un avertissement rouge.
        """
        self._sync_state = state
        color = SYNC_COLORS.get(state, SYNC_COLORS['never'])
        tip = tr(f'tip_sync_{state}') if state in SYNC_COLORS else ''
        self._dot.setStyleSheet(f'background: {color}; border-radius: 4px;')
        self._dot.setToolTip(tip)
        self._btn_sync.setText(sync_button_glyph(state))
        self._btn_sync.setToolTip(tip)
        self._btn_sync.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 13px;
                color: {color}; font-size: 15px; font-weight: bold; padding: 0;
            }}
            QPushButton:hover {{ background: #f1f5f9; }}
        """)
        self._refresh_footer()

    def _refresh_footer(self):
        """Pied de liste : etat, part des couches indexees, volume."""
        layers, values, total = self._index_manager.stats()
        if self._sync_state == 'complete':
            ratio = 1.0
        else:
            ratio = (layers / total) if total else 0.0
        self._dropdown.set_index_state(self._sync_state, ratio, layers, values)

    def _on_input_key(self, event):
        """Clavier dans la saisie : fleches pour choisir, Entree pour zoomer,
        Echap pour fermer la liste, Tab pour tout voir / reduire."""
        key = event.key()
        listing = self._dropdown.isVisible()
        if key == Qt.Key.Key_Down and listing:
            self._dropdown.move_selection(1)
            return True
        if key == Qt.Key.Key_Up and listing:
            self._dropdown.move_selection(-1)
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and listing:
            data = self._dropdown.selected_data()
            if data:
                self._on_result_clicked(data)
            return True
        if key == Qt.Key.Key_Escape and listing:
            self._close_list()
            return True
        if key == Qt.Key.Key_Tab and listing:
            self._show_all = not self._show_all
            self._do_layer_search()
            self._refresh_list()
            return True
        return False

    def _per_field(self):
        """Reponses par champ : 5 d'office, 50 apres Tab "tout voir"."""
        return 50 if self._show_all else 5



class MagicSearchWidget(PillMixin, QDialog):
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
    scope_changed = pyqtSignal(bool)   # True = toutes les couches

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
        self._coord_results = []
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

        # ---- Pilule et liste (modele M2c, partagees avec le panneau) ----
        self._build_pill()
        self._bar.setFixedWidth(SEARCH_BAR_W)
        self._main_layout.addWidget(self._bar)
        self._main_layout.addSpacing(8)
        self._dropdown.setFixedWidth(SEARCH_BAR_W)
        self._main_layout.addWidget(self._dropdown)
        self._update_sync_style(self._sync_state)

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
        # Methode liee et non lambda : Qt coupe d'office une connexion vers
        # une methode d'un widget detruit, pas vers une lambda (apres une
        # bascule barre/panneau, l'ancienne barre levait RuntimeError a
        # chaque indexation).
        self._index_manager.indexing_started.connect(self._on_indexing_started)
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

    # ========================================
    # Collapse / Expand
    # ========================================

    def _collapse(self):
        self._collapsed = True
        self._dropdown.hide_results()
        self._input.clear()
        self._bar.hide()
        self._main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetDefaultConstraint)
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
        self._dropdown.setFixedWidth(self._bar_w)
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
        self._dropdown.setFixedWidth(new_w)
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
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            return self._on_input_key(event)

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

    def _on_indexing_started(self):
        self._set_status('▶ ' + tr('status_indexing'))

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
            self._hide_dropdown()
            self._ban_results = []
            self._osm_results = []
            self._layer_results = []
            self._coord_results = []
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
            self._coord_results = coords
            self._update_dropdown()
            self._layer_search_debounce.start()
            return

        self._coord_results = []
        self._ban_provider.search(text)
        self._osm_provider.search(text)
        self._layer_search_debounce.start()

    def _do_layer_search(self):
        text = self._input.text()
        if text and len(text) >= 2:
            self._layer_provider.search(text, max_per_field=self._per_field())

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
            self._ban_results, self._osm_results, self._layer_results,
            self._coord_results, query=text,
            center=geo_actions.canvas_center_lonlat(self._iface),
            show_all=self._show_all
        )
        self._refresh_footer()
        self.adjustSize()
        self._update_sub_widgets_pos()

    def _close_list(self):
        self._hide_dropdown()

    def _refresh_list(self):
        self._update_dropdown()

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

    def _disconnect_sources(self):
        """Coupe les signaux des objets qui survivent a ce widget (index,
        fournisseurs) : apres une bascule de style, l'ancien widget ne doit
        plus rien recevoir."""
        for signal, slot in (
                (self._ban_provider.results_ready, self._on_ban_results),
                (self._osm_provider.results_ready, self._on_osm_results),
                (self._layer_provider.results_ready, self._on_layer_results),
                (self._index_manager.sync_state_changed, self._update_sync_style),
                (self._index_manager.indexing_started, self._on_indexing_started),
                (self._index_manager.indexing_progress, self._set_status),
                (self._index_manager.indexing_finished, self._hide_status),
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
