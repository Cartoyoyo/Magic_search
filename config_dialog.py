"""
Config Dialog - Panneau de configuration Magic Search.
Couches/colonnes a exclure, activer/desactiver BAN, seuil cache.
i18n 5 langues + About dialog.
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QGroupBox, QScrollArea, QWidget, QSpinBox, QComboBox, QFrame,
    QTreeWidget, QTreeWidgetItem
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QFont, QPixmap
from qgis.core import QgsProject, QgsVectorLayer

from .i18n import tr

AUTHOR_URL = 'https://www.linkedin.com/in/ylaloux/'
REPO_URL = 'https://github.com/Cartoyoyo/Magic_search'

LANGS = ['fr', 'en', 'es', 'pt', 'de']
LANG_LABELS = {
    'fr': 'Francais', 'en': 'English', 'es': 'Espanol',
    'pt': 'Portugues', 'de': 'Deutsch'
}
LANG_FLAGS = {
    'fr': '\U0001F1EB\U0001F1F7', 'en': '\U0001F1EC\U0001F1E7',
    'es': '\U0001F1EA\U0001F1F8', 'pt': '\U0001F1F5\U0001F1F9',
    'de': '\U0001F1E9\U0001F1EA'
}

TR = {
    'window_title': {
        'fr': "Magic Search - Configuration",
        'en': "Magic Search - Settings",
        'es': "Magic Search - Configuracion",
        'pt': "Magic Search - Configuracao",
        'de': "Magic Search - Einstellungen"},
    'ban_group': {
        'fr': "Recherche BAN",
        'en': "BAN Search",
        'es': "Busqueda BAN",
        'pt': "Pesquisa BAN",
        'de': "BAN-Suche"},
    'geocoder_label': {
        'fr': "Geocodeur",
        'en': "Geocoder",
        'es': "Geocodificador",
        'pt': "Geocodificador",
        'de': "Geocoder"},
    'geocoder_ban': {
        'fr': "BAN (adresses FR)",
        'en': "BAN (FR addresses)",
        'es': "BAN (direcciones FR)",
        'pt': "BAN (enderecos FR)",
        'de': "BAN (FR-Adressen)"},
    'geocoder_osm': {
        'fr': "OSM / Nominatim (mondial)",
        'en': "OSM / Nominatim (worldwide)",
        'es': "OSM / Nominatim (mundial)",
        'pt': "OSM / Nominatim (mundial)",
        'de': "OSM / Nominatim (weltweit)"},
    'geocoder_none': {
        'fr': "Aucun",
        'en': "None",
        'es': "Ninguno",
        'pt': "Nenhum",
        'de': "Keiner"},
    'layers_group': {
        'fr': "Couches a indexer",
        'en': "Layers to index",
        'es': "Capas a indexar",
        'pt': "Camadas a indexar",
        'de': "Zu indexierende Ebenen"},
    'cache_group': {
        'fr': "Cache",
        'en': "Cache",
        'es': "Cache",
        'pt': "Cache",
        'de': "Cache"},
    'cache_max': {
        'fr': "Taille max du cache (Mo)",
        'en': "Max cache size (MB)",
        'es': "Tamano max del cache (MB)",
        'pt': "Tamanho max do cache (MB)",
        'de': "Max. Cache-Grosse (MB)"},
    'cache_info': {
        'fr': "Le cache est stocke a cote du fichier projet (.qgz) sous le nom\n"
              "[projet]_magic_search_cache.gz\n"
              "Il accelere la recherche en evitant de reindexer les couches a chaque ouverture.",
        'en': "The cache is stored next to the project file (.qgz) as\n"
              "[project]_magic_search_cache.gz\n"
              "It speeds up search by avoiding re-indexing layers on each project load.",
        'es': "El cache se almacena junto al archivo del proyecto (.qgz) como\n"
              "[proyecto]_magic_search_cache.gz",
        'pt': "O cache e armazenado junto ao arquivo do projeto (.qgz) como\n"
              "[projeto]_magic_search_cache.gz",
        'de': "Der Cache wird neben der Projektdatei (.qgz) gespeichert als\n"
              "[Projekt]_magic_search_cache.gz"},
    'ok': {
        'fr': "OK",         'en': "OK",
        'es': "OK",         'pt': "OK",        'de': "OK"},
    'cancel': {
        'fr': "Annuler",    'en': "Cancel",
        'es': "Cancelar",   'pt': "Cancelar",  'de': "Abbrechen"},
    'about': {
        'fr': "A propos",   'en': "About",
        'es': "Acerca de",  'pt': "Sobre",     'de': "Uber"},
    'reindex': {
        'fr': "Reindexer maintenant",
        'en': "Reindex now",
        'es': "Reindexar ahora",
        'pt': "Reindexar agora",
        'de': "Jetzt neu indizieren"},
    'ui_style_group': {
        'fr': "Style d'interface", 'en': "UI Style", 'es': "Estilo de interfaz",
        'pt': "Estilo de interface", 'de': "Stil der Benutzeroberflache"},
    'ui_style_qt5': {
        'fr': "Panneau ancrable (Qt5)", 'en': "Dockable Panel (Qt5)",
        'es': "Panel acoplable (Qt5)", 'pt': "Painel acoplavel (Qt5)",
        'de': "Andockbares Panel (Qt5)"},
    'ui_style_maps': {
        'fr': "Barre flottante (Maps)", 'en': "Floating Bar (Maps)",
        'es': "Barra flotante (Maps)", 'pt': "Barra flutuante (Maps)",
        'de': "Schwebende Leiste (Maps)"},
    'appearance_group': {
        'fr': "Apparence", 'en': "Appearance", 'es': "Apariencia",
        'pt': "Aparencia", 'de': "Erscheinungsbild"},
    'opacity': {
        'fr': "Opacite (0-100%)", 'en': "Opacity (0-100%)", 'es': "Opacidad (0-100%)",
        'pt': "Opacidade (0-100%)", 'de': "Deckkraft (0-100%)"},
}


class AboutDialog(QDialog):
    _ABOUT_TR = {
        'title': {'fr': "A propos", 'en': "About", 'es': "Acerca de",
                  'pt': "Sobre", 'de': "Uber"},
        'close': {'fr': "Fermer", 'en': "Close", 'es': "Cerrar",
                  'pt': "Fechar", 'de': "Schliessen"},
    }

    def __init__(self, lang='fr', parent=None):
        super().__init__(parent)
        tr = lambda k: self._ABOUT_TR[k].get(lang, self._ABOUT_TR[k]['en'])
        self.setWindowTitle(tr('title'))
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Logo
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignCenter)
            pix = QPixmap(icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pix)
            layout.addWidget(logo_label)

        # Titre
        title = QLabel("Magic Search")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet('color: #13235b;')
        layout.addWidget(title)

        # Sous-titre
        subtitle = QLabel("Universal Search for QGIS")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #00a096; font-size: 11px;')
        layout.addWidget(subtitle)

        layout.addSpacing(10)

        # Version / auteur depuis metadata.txt
        _meta_vals = {'version': '?', 'author': 'Yoan Laloux', 'email': ''}
        _meta = os.path.join(os.path.dirname(__file__), 'metadata.txt')
        if os.path.exists(_meta):
            with open(_meta, encoding='utf-8') as _f:
                for _line in _f:
                    for _k in _meta_vals:
                        if _line.startswith(_k + '='):
                            _meta_vals[_k] = _line.split('=', 1)[1].strip()

        lbl_version = QLabel("Version " + _meta_vals['version'])
        lbl_version.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_version)

        _author = _meta_vals['author']
        _email = _meta_vals['email']

        # Auteur : lien vers le profil LinkedIn
        lbl_author = QLabel(f'<a href="{AUTHOR_URL}">{_author}</a>')
        lbl_author.setOpenExternalLinks(True)
        lbl_author.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_author)

        if _email:
            lbl_email = QLabel(f'<a href="mailto:{_email}">{_email}</a>')
            lbl_email.setOpenExternalLinks(True)
            lbl_email.setAlignment(Qt.AlignCenter)
            lbl_email.setStyleSheet('font-size: 10px;')
            layout.addWidget(lbl_email)

        # Licence
        lbl_license = QLabel(
            '<a href="https://www.gnu.org/licenses/gpl-3.0.html">'
            'GNU General Public License v3.0</a>'
        )
        lbl_license.setOpenExternalLinks(True)
        lbl_license.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_license)

        # GitHub
        lbl_github = QLabel(f'<a href="{REPO_URL}">GitHub</a>')
        lbl_github.setOpenExternalLinks(True)
        lbl_github.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_github)

        layout.addSpacing(10)

        # Bouton fermer
        btn_close = QPushButton(tr('close'))
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #13235b; color: white;
                border-radius: 5px; font-weight: bold;
                padding: 8px 24px; font-size: 11px;
            }
            QPushButton:hover { background-color: #1e3a7a; }
        """)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)


class ConfigDialog(QDialog):
    """Dialog de configuration Magic Search."""

    config_changed = pyqtSignal(dict)
    reindex_requested = pyqtSignal()

    def __init__(self, current_config=None, lang='fr', parent=None):
        super().__init__(parent)
        self.lang = lang
        self._config = current_config or {}
        self._layer_items = {}

        self.setFixedWidth(440)
        self.setWindowTitle(self.tr_('window_title'))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Langue + About (barre compacte)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)
        self.combo_lang = QComboBox()
        self.combo_lang.setFixedWidth(150)
        for code in LANGS:
            self.combo_lang.addItem(f"{LANG_FLAGS[code]}  {LANG_LABELS[code]}")
        self.combo_lang.setCurrentIndex(LANGS.index(self.lang))
        self.combo_lang.currentIndexChanged.connect(self._on_lang_changed)
        top_bar.addWidget(self.combo_lang)
        top_bar.addStretch()

        btn_about = QPushButton(self.tr_('about'))
        btn_about.setCursor(Qt.PointingHandCursor)
        btn_about.setStyleSheet("""
            QPushButton {
                background-color: #00a096; color: white;
                border-radius: 4px; font-weight: bold;
                padding: 4px 12px; font-size: 10px;
            }
            QPushButton:hover { background-color: #00b8ac; }
        """)
        btn_about.clicked.connect(self._show_about)
        top_bar.addWidget(btn_about)
        main_layout.addLayout(top_bar)

        # --- Groupe unifie : Interface + BAN + Apparence ---
        self._general_group = QGroupBox(self.tr_('ui_style_group'))
        gen_layout = QVBoxLayout(self._general_group)
        gen_layout.setSpacing(4)
        gen_layout.setContentsMargins(8, 12, 8, 8)

        # UI Style (ligne)
        ui_row = QHBoxLayout()
        ui_row.setSpacing(6)
        self._combo_ui = QComboBox()
        self._combo_ui.addItem(self.tr_('ui_style_qt5'), 'qt5')
        self._combo_ui.addItem(self.tr_('ui_style_maps'), 'maps')
        current_style = self._config.get('ui_style', 'maps')
        idx = self._combo_ui.findData(current_style)
        self._combo_ui.setCurrentIndex(idx if idx >= 0 else 0)
        ui_row.addWidget(self._combo_ui)

        gen_layout.addLayout(ui_row)

        # Geocodeur (ligne)
        geo_row = QHBoxLayout()
        geo_row.setSpacing(6)
        self._lbl_geocoder = QLabel(self.tr_('geocoder_label'))
        geo_row.addWidget(self._lbl_geocoder)
        self._combo_geocoder = QComboBox()
        self._combo_geocoder.addItem(self.tr_('geocoder_ban'), 'ban')
        self._combo_geocoder.addItem(self.tr_('geocoder_osm'), 'osm')
        self._combo_geocoder.addItem(self.tr_('geocoder_none'), 'none')
        current_geo = self._config.get('geocoder', 'ban' if self.lang == 'fr' else 'osm')
        geo_idx = self._combo_geocoder.findData(current_geo)
        self._combo_geocoder.setCurrentIndex(geo_idx if geo_idx >= 0 else 0)
        geo_row.addWidget(self._combo_geocoder)
        geo_row.addStretch()
        gen_layout.addLayout(geo_row)

        # Opacite (ligne)
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(6)
        self._lbl_opacity = QLabel(self.tr_('opacity'))
        opacity_row.addWidget(self._lbl_opacity)
        from qgis.PyQt.QtWidgets import QSlider
        self._slider_opacity = QSlider(Qt.Horizontal)
        self._slider_opacity.setMinimum(10)
        self._slider_opacity.setMaximum(100)
        self._slider_opacity.setValue(self._config.get('opacity', 100))
        opacity_row.addWidget(self._slider_opacity)
        self._lbl_opacity_val = QLabel(f"{self._slider_opacity.value()}%")
        self._lbl_opacity_val.setFixedWidth(32)
        self._slider_opacity.valueChanged.connect(lambda v: self._lbl_opacity_val.setText(f"{v}%"))
        opacity_row.addWidget(self._lbl_opacity_val)
        gen_layout.addLayout(opacity_row)

        main_layout.addWidget(self._general_group)

        # --- Couches ---
        self._layers_group = QGroupBox(self.tr_('layers_group'))
        layers_layout = QVBoxLayout(self._layers_group)
        layers_layout.setContentsMargins(8, 12, 8, 8)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(120)
        self._populate_layers_tree()
        layers_layout.addWidget(self._tree)
        main_layout.addWidget(self._layers_group)

        # --- Cache (compact) ---
        self._cache_group = QGroupBox(self.tr_('cache_group'))
        cache_layout = QVBoxLayout(self._cache_group)
        cache_layout.setSpacing(4)
        cache_layout.setContentsMargins(8, 12, 8, 8)

        # Chemin cache
        project_path = QgsProject.instance().fileName()
        if project_path:
            cache_file = os.path.splitext(project_path)[0] + '_magic_search_cache.gz'
            cache_exists = os.path.exists(cache_file)
            if cache_exists:
                size_kb = os.path.getsize(cache_file) / 1024
                path_text = f"{cache_file}  ({size_kb:.0f} Ko)"
            else:
                path_text = f"{cache_file}  {tr('cache_not_created', lang=self.lang)}"
        else:
            path_text = tr('cache_no_project', lang=self.lang)
        self._lbl_cache_path = QLabel(path_text)
        self._lbl_cache_path.setWordWrap(True)
        self._lbl_cache_path.setStyleSheet(
            'color: #64748b; font-size: 9px; background: #f8fafc; '
            'padding: 4px; border-radius: 3px; border: 1px solid #e2e8f0;'
        )
        self._lbl_cache_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cache_layout.addWidget(self._lbl_cache_path)

        # Taille max
        cache_row = QHBoxLayout()
        self._lbl_cache = QLabel(self.tr_('cache_max'))
        cache_row.addWidget(self._lbl_cache)
        self._spin_cache = QSpinBox()
        self._spin_cache.setMinimum(1)
        self._spin_cache.setMaximum(500)
        self._spin_cache.setValue(self._config.get('max_cache_mb', 50))
        self._spin_cache.setSuffix(' Mo')
        cache_row.addWidget(self._spin_cache)
        cache_row.addStretch()
        cache_layout.addLayout(cache_row)

        main_layout.addWidget(self._cache_group)

        # --- Boutons bas ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._btn_reindex = QPushButton(self.tr_('reindex'))
        self._btn_reindex.setCursor(Qt.PointingHandCursor)
        self._btn_reindex.setStyleSheet("""
            QPushButton {
                background-color: #f29400; color: white;
                border-radius: 4px; font-weight: bold;
                padding: 6px 12px; font-size: 10px;
            }
            QPushButton:hover { background-color: #ffaa22; }
        """)
        self._btn_reindex.clicked.connect(self._on_reindex)
        btn_layout.addWidget(self._btn_reindex)

        btn_layout.addStretch()

        self._btn_cancel = QPushButton(self.tr_('cancel'))
        self._btn_cancel.setCursor(Qt.PointingHandCursor)
        self._btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b; color: white;
                border-radius: 4px; padding: 6px 12px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #7a8da0; }
        """)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_ok = QPushButton(self.tr_('ok'))
        self._btn_ok.setCursor(Qt.PointingHandCursor)
        self._btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #13235b; color: white;
                border-radius: 4px; font-weight: bold;
                padding: 6px 18px; font-size: 10px;
            }
            QPushButton:hover { background-color: #1e3a7a; }
        """)
        self._btn_ok.clicked.connect(self._on_accept)
        btn_layout.addWidget(self._btn_ok)

        main_layout.addLayout(btn_layout)

    def tr_(self, key):
        return TR[key].get(self.lang, TR[key]['en'])

    def _on_lang_changed(self, index):
        self.lang = LANGS[index]
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(self.tr_('window_title'))
        self._general_group.setTitle(self.tr_('ui_style_group'))
        self._combo_ui.setItemText(0, self.tr_('ui_style_qt5'))
        self._combo_ui.setItemText(1, self.tr_('ui_style_maps'))
        self._lbl_geocoder.setText(self.tr_('geocoder_label'))
        self._combo_geocoder.setItemText(0, self.tr_('geocoder_ban'))
        self._combo_geocoder.setItemText(1, self.tr_('geocoder_osm'))
        self._combo_geocoder.setItemText(2, self.tr_('geocoder_none'))
        self._lbl_opacity.setText(self.tr_('opacity'))
        self._layers_group.setTitle(self.tr_('layers_group'))
        self._cache_group.setTitle(self.tr_('cache_group'))
        self._lbl_cache.setText(self.tr_('cache_max'))
        self._btn_reindex.setText(self.tr_('reindex'))
        self._btn_cancel.setText(self.tr_('cancel'))
        self._btn_ok.setText(self.tr_('ok'))

    def _populate_layers_tree(self):
        self._tree.clear()
        self._layer_items = {}
        project = QgsProject.instance()
        layers_config = self._config.get('layers', {})

        for layer_id, layer in project.mapLayers().items():
            if not isinstance(layer, QgsVectorLayer):
                continue

            layer_conf = layers_config.get(layer_id, {})
            excluded = layer_conf.get('excluded', False)
            excluded_fields = layer_conf.get('excluded_fields', [])

            layer_item = QTreeWidgetItem([layer.name()])
            layer_item.setCheckState(0, Qt.Unchecked if excluded else Qt.Checked)
            layer_item.setData(0, Qt.UserRole, layer_id)

            field_items = []
            for field in layer.fields():
                field_item = QTreeWidgetItem([field.name()])
                is_excluded = field.name() in excluded_fields
                field_item.setCheckState(0, Qt.Unchecked if is_excluded else Qt.Checked)
                field_item.setData(0, Qt.UserRole, field.name())
                layer_item.addChild(field_item)
                field_items.append(field_item)

            self._tree.addTopLevelItem(layer_item)
            self._layer_items[layer_id] = {
                'item': layer_item,
                'fields': field_items,
            }

    def _build_config(self):
        config = {
            'ui_style': self._combo_ui.currentData(),
            'geocoder': self._combo_geocoder.currentData(),
            'max_cache_mb': self._spin_cache.value(),
            'opacity': self._slider_opacity.value(),
            'lang': self.lang,
            'layers': {},
        }

        for layer_id, data in self._layer_items.items():
            layer_item = data['item']
            excluded = layer_item.checkState(0) == Qt.Unchecked
            excluded_fields = []
            for field_item in data['fields']:
                if field_item.checkState(0) == Qt.Unchecked:
                    excluded_fields.append(field_item.data(0, Qt.UserRole))

            config['layers'][layer_id] = {
                'excluded': excluded,
                'excluded_fields': excluded_fields,
            }

        return config

    def _on_accept(self):
        config = self._build_config()
        self.config_changed.emit(config)
        self.accept()

    def _on_reindex(self):
        config = self._build_config()
        self.config_changed.emit(config)
        self.reindex_requested.emit()
        self.accept()

    def _show_about(self):
        dlg = AboutDialog(self.lang, self)
        dlg.exec_()
