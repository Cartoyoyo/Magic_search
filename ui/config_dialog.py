"""
Config Dialog - Panneau de configuration Magic Search.
Couches/colonnes a exclure, activer/desactiver BAN, seuil cache.
i18n 5 langues + About dialog.
"""

import os
import html
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QGroupBox, QSpinBox, QComboBox, QFrame,
    QTreeWidget, QTreeWidgetItem, QLineEdit
)
from qgis.PyQt.QtCore import Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QFont, QPixmap, QIcon, QCursor, QDesktopServices
from qgis.core import QgsProject, QgsVectorLayer

from ..i18n import tr
from ..core import geo_actions

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
    'all_types': {
        'fr': "Indexer aussi les dates et les nombres a decimales",
        'en': "Also index dates and decimal numbers",
        'es': "Indexar tambien fechas y numeros decimales",
        'pt': "Indexar tambem datas e numeros decimais",
        'de': "Auch Datums- und Dezimalwerte indizieren"},
    'all_types_tip': {
        'fr': "Par defaut, les dates et les vraies decimales ne sont pas\n"
              "indexees : on ne les recherche pas au clavier. Les colonnes\n"
              "typees en decimal qui ne contiennent que des entiers (numero\n"
              "de regard, de branchement...) restent indexees.",
        'en': "By default dates and true decimals are not indexed: nobody\n"
              "types them in a search box. Decimal-typed columns holding only\n"
              "whole numbers are still indexed.",
        'es': "Por defecto, las fechas y los decimales reales no se indexan.\n"
              "Las columnas decimales con solo enteros si se indexan.",
        'pt': "Por padrao, datas e decimais reais nao sao indexados.\n"
              "Colunas decimais contendo apenas inteiros continuam indexadas.",
        'de': "Datums- und echte Dezimalwerte werden standardmassig nicht\n"
              "indiziert. Dezimalspalten mit ausschliesslich ganzen Zahlen\n"
              "bleiben indiziert."},
    'cache_open_tip': {
        'fr': "Cliquer pour ouvrir le dossier du cache",
        'en': "Click to open the cache folder",
        'es': "Clic para abrir la carpeta de cache",
        'pt': "Clique para abrir a pasta de cache",
        'de': "Zum Offnen des Cache-Ordners klicken"},
    'cache_info': {
        'fr': "Le cache est stocke a cote du fichier projet (.qgz) dans le dossier\n"
              "[projet]_magic_search_cache/ (un fichier par couche)\n"
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
    'zoom_scale': {
        'fr': "Zoom sur un point",   'en': "Zoom on a point",
        'es': "Zoom en un punto",    'pt': "Zoom num ponto",
        'de': "Zoom auf einen Punkt"},
    'zoom_scale_tip': {
        'fr': "Echelle appliquee quand on clique sur un resultat ponctuel.\n"
              "Les lignes et polygones restent cadres sur leur emprise.",
        'en': "Scale applied when clicking a point result.\n"
              "Lines and polygons are still framed on their extent.",
        'es': "Escala aplicada al hacer clic en un resultado puntual.",
        'pt': "Escala aplicada ao clicar num resultado pontual.",
        'de': "Massstab beim Klick auf ein punktformiges Ergebnis."},
    'all_layers': {
        'fr': "Chercher aussi dans les couches masquees",
        'en': "Also search hidden layers",
        'es': "Buscar tambien en las capas ocultas",
        'pt': "Pesquisar tambem nas camadas ocultas",
        'de': "Auch in ausgeblendeten Layern suchen"},
    'all_layers_tip': {
        'fr': "Par defaut, la recherche ne repond que sur les couches\n"
              "cochees dans le panneau des couches. Toutes les couches\n"
              "restent indexees : cocher une couche la rend cherchable\n"
              "aussitot, sans reindexation.",
        'en': "By default, search only answers on layers checked in the\n"
              "layers panel. Every layer stays indexed: ticking a layer\n"
              "makes it searchable at once, with no reindexing.",
        'es': "Por defecto la busqueda solo responde en las capas\n"
              "marcadas. Todas las capas siguen indexadas.",
        'pt': "Por defeito a pesquisa so responde nas camadas marcadas.\n"
              "Todas as camadas continuam indexadas.",
        'de': "Standardmassig durchsucht die Suche nur aktivierte Layer.\n"
              "Alle Layer bleiben indiziert."},
    'reindex': {
        'fr': "Reindexer maintenant",
        'en': "Reindex now",
        'es': "Reindexar ahora",
        'pt': "Reindexar agora",
        'de': "Jetzt neu indizieren"},
    'ui_style_group': {
        'fr': "Style d'interface", 'en': "UI Style", 'es': "Estilo de interfaz",
        'pt': "Estilo de interface", 'de': "Stil der Benutzeroberflache"},
    # Le libelle ne mentionne plus "Qt5" : sous QGIS 4 l'interface est
    # construite avec Qt 6. La valeur stockee reste 'qt5' pour ne pas perdre
    # la preference des utilisateurs venant des versions 1.x.
    'ui_style_qt5': {
        'fr': "Panneau ancrable", 'en': "Dockable Panel",
        'es': "Panel acoplable", 'pt': "Painel acoplavel",
        'de': "Andockbares Panel"},
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
    'reverse_radius': {
        'fr': "Rayon geocodage inverse (m)", 'en': "Reverse geocoding radius (m)",
        'es': "Radio de geocodificacion inversa (m)", 'pt': "Raio de geocodificacao inversa (m)",
        'de': "Radius Rueckwaerts-Geokodierung (m)"},
    'ban_postcode': {
        'fr': "Filtrer BAN par code postal", 'en': "Filter BAN by postcode",
        'es': "Filtrar BAN por codigo postal", 'pt': "Filtrar BAN por codigo postal",
        'de': "BAN nach Postleitzahl filtern"},
}


class _BadgeLabel(QLabel):
    """Badge shields.io cliquable, rendu a sa taille naturelle.

    Les badges sont des PNG rasterises a 2x depuis https://img.shields.io et
    stockes dans icon/ sous la forme `badge-<nom>@2x.png` ; ils sont affiches
    a la moitie de leur taille, ce qui les garde nets aussi bien sur un ecran
    standard que sur un ecran haute densite. Le SVG de shields.io n'est
    volontairement pas utilise tel quel : QtSvg ne suit que SVG Tiny, et son
    rendu du texte sort flou.

    Pour ajouter ou modifier un badge, se reporter a la syntaxe et aux styles
    officiels : https://github.com/badges/shields
    Rasterisation a 2x (le PNG stocke fait donc 40 px de haut), en recuperant
    le SVG shields.io puis en le photographiant dans un navigateur headless :
        curl -o badge.svg "https://img.shields.io/badge/version-2.0.0-blue"
        chrome --headless=new --force-device-scale-factor=2                --default-background-color=00000000 --window-size=<w>,20                --screenshot=badge.png page.html   # page.html : <img src=badge.svg>
    <w> est la largeur annoncee par l'attribut width= du SVG.
    Encodage de l'URL : espace = %20, barre verticale = %7C,
    tiret litteral = --, plus = %2B.
    Le badge "langues" annonce l'interface du plugin, traduite en
    FR / EN / ES / PT / DE ; un badge "docs" ne couvrirait que le README.
    """

    RATIO = 2.0

    def __init__(self, filename, url, parent=None):
        super().__init__(parent)
        self.url = url
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icon', filename)
        pix = QPixmap(path)
        if pix.isNull():
            self.hide()
            return
        pix.setDevicePixelRatio(self.RATIO)
        self.setPixmap(pix)
        self.setFixedSize(int(pix.width() / self.RATIO),
                          int(pix.height() / self.RATIO))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(url)

    def mousePressEvent(self, event):
        if self.url:
            QDesktopServices.openUrl(QUrl(self.url))


class AboutDialog(QDialog):
    _ABOUT_TR = {
        'title': {'fr': "A propos", 'en': "About", 'es': "Acerca de",
                  'pt': "Sobre", 'de': "Uber"},
        'close': {'fr': "Fermer", 'en': "Close", 'es': "Cerrar",
                  'pt': "Fechar", 'de': "Schliessen"},
        'subtitle': {
            'fr': "La barre de recherche universelle de QGIS",
            'en': "The universal search bar for QGIS",
            'es': "La barra de busqueda universal de QGIS",
            'pt': "A barra de pesquisa universal do QGIS",
            'de': "Die universelle Suchleiste fuer QGIS"},
        'description': {
            'fr': "Une seule barre pour tout retrouver dans QGIS : vous tapez, "
                  "et le plugin interroge en meme temps le geocodeur d'adresses "
                  "(BAN pour la France, OSM/Nominatim dans le monde entier) et "
                  "tous les champs de toutes les couches vectorielles du projet. "
                  "Adresse, numero de regard, parcelle ou coordonnees brutes "
                  "(WGS84 ou Lambert 93) : le plugin reconnait ce que vous "
                  "cherchez et vous y emmene. L'indexation se fait en tache de "
                  "fond, sans bloquer QGIS, et le resultat est conserve dans un "
                  "cache compresse pose a cote du fichier projet.",
            'en': "One search bar to find anything in QGIS: as you type, the "
                  "plugin queries at the same time the address geocoder (BAN for "
                  "France, OSM/Nominatim worldwide) and every field of every "
                  "vector layer in the project. An address, an asset number, a "
                  "parcel or raw coordinates (WGS84 or Lambert 93): the plugin "
                  "works out what you are looking for and takes you there. "
                  "Indexing runs in the background without blocking QGIS, and is "
                  "kept in a compressed cache stored next to the project file.",
            'es': "Una sola barra para encontrarlo todo en QGIS: mientras escribe, "
                  "el complemento consulta a la vez el geocodificador de "
                  "direcciones (BAN en Francia, OSM/Nominatim en todo el mundo) y "
                  "todos los campos de todas las capas vectoriales del proyecto. "
                  "Una direccion, un numero de elemento, una parcela o coordenadas "
                  "en bruto (WGS84 o Lambert 93): el complemento reconoce lo que "
                  "busca y le lleva alli. La indexacion se realiza en segundo "
                  "plano, sin bloquear QGIS, y se conserva en una cache comprimida "
                  "junto al archivo de proyecto.",
            'pt': "Uma unica barra para encontrar tudo no QGIS: enquanto escreve, "
                  "o modulo consulta ao mesmo tempo o geocodificador de enderecos "
                  "(BAN em Franca, OSM/Nominatim em todo o mundo) e todos os "
                  "campos de todas as camadas vetoriais do projeto. Um endereco, "
                  "um numero de elemento, um predio ou coordenadas em bruto "
                  "(WGS84 ou Lambert 93): o modulo reconhece o que procura e "
                  "leva-o ate la. A indexacao decorre em segundo plano, sem "
                  "bloquear o QGIS, e e guardada numa cache comprimida junto ao "
                  "ficheiro de projeto.",
            'de': "Eine einzige Leiste, um in QGIS alles zu finden: waehrend Sie "
                  "tippen, fragt die Erweiterung gleichzeitig den Adress-Geocoder "
                  "(BAN fuer Frankreich, OSM/Nominatim weltweit) und alle Felder "
                  "aller Vektorebenen des Projekts ab. Eine Adresse, eine "
                  "Objektnummer, ein Flurstueck oder rohe Koordinaten (WGS84 oder "
                  "Lambert 93): die Erweiterung erkennt, wonach Sie suchen, und "
                  "bringt Sie dorthin. Die Indizierung laeuft im Hintergrund, ohne "
                  "QGIS zu blockieren, und wird in einem komprimierten Cache neben "
                  "der Projektdatei gespeichert."},
    }

    README_URL = REPO_URL + '/blob/main/README.md'

    def __init__(self, lang='fr', parent=None):
        super().__init__(parent)
        tr_ = lambda k: self._ABOUT_TR[k].get(lang, self._ABOUT_TR[k]['en'])
        self.setWindowTitle(tr_('title') + " Magic Search")
        self.setModal(True)
        # Minimum et non largeur fixe : un badge un peu plus long qu'attendu
        # elargit le dialogue au lieu d'etre rogne.
        self.setMinimumWidth(460)

        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(plugin_dir, 'icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        # Logo
        if os.path.exists(icon_path):
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(icon_path).scaled(
                80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pix)
            layout.addWidget(logo_label)

        # Titre
        title = QLabel("Magic Search")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet('color: #13235b;')
        layout.addWidget(title)

        # Sous-titre
        subtitle = QLabel(tr_('subtitle'))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet('color: #00a096; font-size: 11px;')
        layout.addWidget(subtitle)

        # Badges, sur deux rangees : les quatre alignes bout a bout font
        # 471 px, plus large que la zone utile du dialogue, et le dernier
        # (« langues », le plus long) se retrouvait rogne.
        badges = QVBoxLayout()
        badges.setSpacing(5)
        badges.addLayout(self._badge_row((
            ('badge-qgis@2x.png', 'https://qgis.org'),
            ('badge-version@2x.png', self.README_URL + '#-changelog'),
            ('badge-license@2x.png', 'https://www.gnu.org/licenses/gpl-3.0.html'),
        )))
        badges.addLayout(self._badge_row((
            ('badge-langue@2x.png', self.README_URL + '#-langues--languages'),
        )))
        layout.addLayout(badges)

        layout.addWidget(self._sep())

        # Description traduite. metadata.txt alimente encore le gestionnaire
        # d'extensions de QGIS, qui n'a pas de mecanisme de traduction.
        about = QLabel(tr_('description'))
        about.setWordWrap(True)
        about.setAlignment(Qt.AlignmentFlag.AlignJustify)
        about.setStyleSheet('font-size: 11px;')
        layout.addWidget(about)

        layout.addWidget(self._sep())

        # Version et auteur depuis metadata.txt
        meta = self._read_metadata(plugin_dir)

        author = QLabel(
            '<div style="line-height:150%">'
            '<b>{author}</b><br>'
            '<a href="{readme}#-changelog">Version {version}</a>'
            '</div>'.format(author=html.escape(meta['author']),
                            readme=self.README_URL,
                            version=html.escape(meta['version']))
        )
        author.setOpenExternalLinks(True)
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author)

        # Badges auteur
        layout.addLayout(self._badge_row((
            ('badge-github@2x.png', REPO_URL),
            ('badge-linkedin@2x.png', AUTHOR_URL),
        ), spacing=8))

        layout.addWidget(self._sep())

        # Bouton fermer
        btn_close = QPushButton(tr_('close'))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setDefault(True)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #13235b; color: white;
                border-radius: 5px; font-weight: bold;
                padding: 8px 24px; font-size: 11px;
            }
            QPushButton:hover { background-color: #1e3a7a; }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _sep():
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    def _badge_row(self, items, spacing=6):
        """Rangee de badges centree. `items` : suite de (fichier, url)."""
        row = QHBoxLayout()
        row.setSpacing(spacing)
        row.addStretch()
        for filename, url in items:
            row.addWidget(_BadgeLabel(filename, url, self))
        row.addStretch()
        return row

    @staticmethod
    def _read_metadata(plugin_dir):
        vals = {'version': '?', 'author': 'Yoan Laloux'}
        path = os.path.join(plugin_dir, 'metadata.txt')
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    for line in f:
                        for key in vals:
                            if line.startswith(key + '='):
                                vals[key] = line.split('=', 1)[1].strip()
            except OSError:
                pass
        return vals


def _cache_usage(cache_dir):
    """Taille totale (Mo) et nombre de couches du dossier de cache."""
    if not os.path.isdir(cache_dir):
        return 0.0, 0
    total = 0
    n_layers = 0
    try:
        for name in os.listdir(cache_dir):
            full = os.path.join(cache_dir, name)
            if not os.path.isfile(full):
                continue
            total += os.path.getsize(full)
            if name.endswith('.idx'):
                n_layers += 1
    except OSError:
        return 0.0, 0
    return total / 1048576, n_layers


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
        btn_about.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._combo_ui.addItem(self.tr_('ui_style_qt5'), 'qt5')  # 'qt5' : identifiant historique
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

        # Filtre code postal BAN (ligne)
        postcode_row = QHBoxLayout()
        postcode_row.setSpacing(6)
        self._lbl_postcode = QLabel(self.tr_('ban_postcode'))
        postcode_row.addWidget(self._lbl_postcode)
        self._input_postcode = QLineEdit()
        self._input_postcode.setPlaceholderText('ex: 03200')
        self._input_postcode.setFixedWidth(80)
        self._input_postcode.setText(self._config.get('ban_postcode', ''))
        postcode_row.addWidget(self._input_postcode)
        postcode_row.addStretch()
        gen_layout.addLayout(postcode_row)

        # Rayon geocodage inverse (ligne)
        radius_row = QHBoxLayout()
        radius_row.setSpacing(6)
        self._lbl_radius = QLabel(self.tr_('reverse_radius'))
        radius_row.addWidget(self._lbl_radius)
        self._spin_radius = QSpinBox()
        self._spin_radius.setMinimum(5)
        self._spin_radius.setMaximum(500)
        self._spin_radius.setValue(self._config.get('reverse_radius_m', 25))
        self._spin_radius.setSuffix(' m')
        radius_row.addWidget(self._spin_radius)
        radius_row.addStretch()
        gen_layout.addLayout(radius_row)

        # Opacite (ligne)
        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(6)
        self._lbl_opacity = QLabel(self.tr_('opacity'))
        opacity_row.addWidget(self._lbl_opacity)
        from qgis.PyQt.QtWidgets import QSlider
        self._slider_opacity = QSlider(Qt.Orientation.Horizontal)
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
        self._cache_dir = None
        if project_path:
            cache_dir = os.path.splitext(project_path)[0] + '_magic_search_cache'
            size_mb, n_layers = _cache_usage(cache_dir)
            if n_layers:
                # Le dossier existe : le chemin devient un lien qui l'ouvre
                # dans l'explorateur de fichiers.
                self._cache_dir = cache_dir
                href = QUrl.fromLocalFile(cache_dir).toString()
                path_text = (
                    f'<a href="{html.escape(href, quote=True)}" '
                    f'style="color: #2563eb; text-decoration: none;">'
                    f'{html.escape(cache_dir)}</a>'
                    f'  ({size_mb:.1f} Mo, {n_layers} couches)'
                )
            else:
                path_text = html.escape(
                    f"{cache_dir}  {tr('cache_not_created', lang=self.lang)}")
        else:
            path_text = html.escape(tr('cache_no_project', lang=self.lang))
        self._lbl_cache_path = QLabel(path_text)
        self._lbl_cache_path.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_cache_path.setWordWrap(True)
        self._lbl_cache_path.setStyleSheet(
            'color: #64748b; font-size: 9px; background: #f8fafc; '
            'padding: 4px; border-radius: 3px; border: 1px solid #e2e8f0;'
        )
        self._lbl_cache_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._lbl_cache_path.setOpenExternalLinks(False)
        self._lbl_cache_path.linkActivated.connect(self._open_cache_dir)
        if self._cache_dir:
            self._lbl_cache_path.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._lbl_cache_path.setToolTip(self.tr_('cache_open_tip'))
        cache_layout.addWidget(self._lbl_cache_path)

        self._chk_all_types = QCheckBox(self.tr_('all_types'))
        self._chk_all_types.setChecked(self._config.get('index_all_types', False))
        self._chk_all_types.setToolTip(self.tr_('all_types_tip'))
        cache_layout.addWidget(self._chk_all_types)

        self._chk_all_layers = QCheckBox(self.tr_('all_layers'))
        self._chk_all_layers.setChecked(self._config.get('search_all_layers', False))
        self._chk_all_layers.setToolTip(self.tr_('all_layers_tip'))
        cache_layout.addWidget(self._chk_all_layers)

        # Echelle de zoom sur un resultat ponctuel
        zoom_row = QHBoxLayout()
        self._lbl_zoom = QLabel(self.tr_('zoom_scale'))
        self._lbl_zoom.setToolTip(self.tr_('zoom_scale_tip'))
        zoom_row.addWidget(self._lbl_zoom)
        self._combo_zoom = QComboBox()
        for scale in geo_actions.POINT_SCALE_CHOICES:
            self._combo_zoom.addItem('1:%d' % scale, scale)
        current_zoom = self._config.get('zoom_scale', geo_actions.DEFAULT_POINT_SCALE)
        zoom_idx = self._combo_zoom.findData(current_zoom)
        self._combo_zoom.setCurrentIndex(zoom_idx if zoom_idx >= 0 else 0)
        self._combo_zoom.setToolTip(self.tr_('zoom_scale_tip'))
        zoom_row.addWidget(self._combo_zoom)
        zoom_row.addStretch()
        cache_layout.addLayout(zoom_row)

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
        self._btn_reindex.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def _open_cache_dir(self, url):
        """Ouvre le dossier de cache dans l'explorateur de fichiers."""
        QDesktopServices.openUrl(QUrl(url))

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
        self._lbl_postcode.setText(self.tr_('ban_postcode'))
        self._lbl_radius.setText(self.tr_('reverse_radius'))
        self._layers_group.setTitle(self.tr_('layers_group'))
        self._cache_group.setTitle(self.tr_('cache_group'))
        self._lbl_cache.setText(self.tr_('cache_max'))
        self._chk_all_types.setText(self.tr_('all_types'))
        self._chk_all_types.setToolTip(self.tr_('all_types_tip'))
        self._chk_all_layers.setText(self.tr_('all_layers'))
        self._chk_all_layers.setToolTip(self.tr_('all_layers_tip'))
        self._lbl_zoom.setText(self.tr_('zoom_scale'))
        self._lbl_zoom.setToolTip(self.tr_('zoom_scale_tip'))
        self._combo_zoom.setToolTip(self.tr_('zoom_scale_tip'))
        if self._cache_dir:
            self._lbl_cache_path.setToolTip(self.tr_('cache_open_tip'))
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
            layer_item.setCheckState(0, Qt.CheckState.Unchecked if excluded else Qt.CheckState.Checked)
            layer_item.setData(0, Qt.ItemDataRole.UserRole, layer_id)

            field_items = []
            for field in layer.fields():
                field_item = QTreeWidgetItem([field.name()])
                is_excluded = field.name() in excluded_fields
                field_item.setCheckState(0, Qt.CheckState.Unchecked if is_excluded else Qt.CheckState.Checked)
                field_item.setData(0, Qt.ItemDataRole.UserRole, field.name())
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
            'index_all_types': self._chk_all_types.isChecked(),
            'search_all_layers': self._chk_all_layers.isChecked(),
            'zoom_scale': self._combo_zoom.currentData(),
            'opacity': self._slider_opacity.value(),
            'ban_postcode': self._input_postcode.text().strip(),
            'reverse_radius_m': self._spin_radius.value(),
            'lang': self.lang,
            'layers': {},
        }

        for layer_id, data in self._layer_items.items():
            layer_item = data['item']
            excluded = layer_item.checkState(0) == Qt.CheckState.Unchecked
            excluded_fields = []
            for field_item in data['fields']:
                if field_item.checkState(0) == Qt.CheckState.Unchecked:
                    excluded_fields.append(field_item.data(0, Qt.ItemDataRole.UserRole))

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
        dlg.exec()
