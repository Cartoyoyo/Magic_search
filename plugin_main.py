"""
Magic Search - Plugin principal.
Barre de recherche flottante style Google Maps sur le canevas QGIS.
"""

import os
import json
try:  # Qt6 : QAction et QShortcut ont quitte QtWidgets pour QtGui
    from qgis.PyQt.QtGui import QAction, QShortcut
except ImportError:  # Qt5
    from qgis.PyQt.QtWidgets import QAction, QShortcut
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtCore import Qt, QSettings, QTimer
from qgis.core import QgsProject, QgsVectorLayer, QgsApplication, Qgis

from . import i18n
from .i18n import tr
from .core import geo_actions

CONFIG_KEY = 'MagicSearch'
SETTINGS_GROUP = 'MagicSearch'
SUPPORTED_LANGS = i18n.LANGS

# Preferences applicatives : memorisees globalement (QSettings), donc conservees
# d'un projet a l'autre et d'une session QGIS a l'autre.
# Les autres cles (layers, favorites) restent propres au projet.
GLOBAL_KEYS = ('ui_style', 'lang', 'geocoder', 'ban_postcode',
               'reverse_radius_m', 'opacity', 'max_cache_mb',
               'index_all_types', 'search_all_layers', 'zoom_scale')
INT_KEYS = ('reverse_radius_m', 'opacity', 'max_cache_mb', 'zoom_scale')
BOOL_KEYS = ('index_all_types', 'search_all_layers')


class MagicSearch:
    def __init__(self, iface):
        self.iface = iface
        self.search_widget = None
        self.dock_widget = None
        self.action_config = None
        self.action_toggle = None
        self.shortcut = None
        self.index_manager = None
        self.ban_provider = None
        self.osm_provider = None
        self.layer_provider = None
        self.ban_reverse_provider = None
        self.reverse_tool = None
        self.street_view_tool = None
        self.favorite_tool = None
        self._config = {}
        self._visible = False
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        self._load_config()

        from .core.index_manager import IndexManager
        from .core.reverse_geocode_tool import ReverseGeocodeTool
        from .core.street_view_tool import StreetViewTool
        from .core.favorite_tool import FavoriteTool
        from .providers.ban_provider import BanProvider, BanReverseProvider
        from .providers.osm_provider import OsmProvider
        from .providers.layer_provider import LayerProvider

        self.index_manager = IndexManager()
        self.ban_provider = BanProvider()
        self.osm_provider = OsmProvider()
        self.layer_provider = LayerProvider(self.index_manager)
        self.ban_reverse_provider = BanReverseProvider()
        self.reverse_tool = ReverseGeocodeTool(self.iface, self.ban_reverse_provider)
        self.reverse_tool.address_found.connect(self._on_reverse_address_found)
        self.reverse_tool.address_not_found.connect(self._on_reverse_address_not_found)
        self.street_view_tool = StreetViewTool(self.iface)
        self.favorite_tool = FavoriteTool(self.iface)
        self.favorite_tool.point_picked.connect(self._on_favorite_point_picked)

        self._apply_config()
        # L'indexation ne demarre plus toute seule : elle est declenchee par
        # l'utilisateur via le bouton de synchronisation de la barre de
        # recherche (ou "Reindexer maintenant" dans la configuration). Au
        # demarrage on se contente de dire ou en est l'index (jamais/partiel).
        QTimer.singleShot(0, self.index_manager.refresh_sync_state)

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action_toggle = QAction(icon, 'Magic Search', self.iface.mainWindow())
        self.action_toggle.setCheckable(True)
        self.action_toggle.setChecked(False)
        self.action_toggle.setToolTip(tr('tip_toggle'))
        self.action_toggle.triggered.connect(self._toggle_visibility)
        self.iface.addToolBarIcon(self.action_toggle)
        self.iface.addPluginToMenu('&Magic Search', self.action_toggle)

        self.action_config = QAction(tr('menu_config'), self.iface.mainWindow())
        self.action_config.triggered.connect(self._open_config)
        self.iface.addPluginToMenu('&Magic Search', self.action_config)

        self.iface.mapCanvas().mapToolSet.connect(self._on_map_tool_set)

        self.shortcut = QShortcut(
            QKeySequence('Ctrl+Shift+F'),
            self.iface.mainWindow()
        )
        self.shortcut.activated.connect(self._focus_search)

        QgsProject.instance().layersAdded.connect(self._on_layers_added)
        QgsProject.instance().layersRemoved.connect(self._on_layers_removed)
        QgsProject.instance().readProject.connect(self._on_project_loaded)
        QgsProject.instance().cleared.connect(self._on_project_closed)
        self.iface.newProjectCreated.connect(self._on_project_loaded)

        # Toujours construire l'UI au demarrage (meme pour un projet sans titre),
        # mais sans l'afficher : self._visible pilote seul la visibilite, y compris
        # lors des reconstructions declenchees par l'ouverture/creation d'un projet.
        self._build_ui()

    def _toggle_reverse_tool(self, checked):
        canvas = self.iface.mapCanvas()
        if checked:
            canvas.setMapTool(self.reverse_tool)
        else:
            canvas.unsetMapTool(self.reverse_tool)

    def _on_map_tool_set(self, new_tool, old_tool):
        """Garde le bouton "?" des widgets synchronise avec l'outil de carte actif
        (ex: decocher si l'utilisateur bascule vers un autre outil QGIS)."""
        active = new_tool is self.reverse_tool
        if self.search_widget:
            self.search_widget.set_reverse_active(active)
        if self.dock_widget:
            self.dock_widget.set_reverse_active(active)

    def _activate_street_view(self, service):
        """Active l'outil de vue de rue (ou de copie de coordonnees) pour le
        choix fait dans le menu deroulant. Usage unique : l'outil se
        desactive apres le clic."""
        from .core.street_view_tool import SERVICE_LABELS, COPY_COORDS
        self.street_view_tool.set_service(service)
        self.iface.mapCanvas().setMapTool(self.street_view_tool)
        if service == COPY_COORDS:
            message = tr('msg_copy_coords_prompt')
        else:
            message = tr('msg_street_view_prompt', service=SERVICE_LABELS.get(service, service))
        self.iface.messageBar().pushMessage('Magic Search', message, level=Qgis.MessageLevel.Info, duration=4)

    def _activate_add_favorite(self):
        """Active l'outil "ajouter un favori" : le prochain clic sur la carte
        declenche _on_favorite_point_picked."""
        self.iface.mapCanvas().setMapTool(self.favorite_tool)
        self.iface.messageBar().pushMessage(
            'Magic Search', tr('msg_favorite_prompt'), level=Qgis.MessageLevel.Info, duration=4
        )

    def _on_favorite_point_picked(self, lon, lat):
        from qgis.PyQt.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(
            self.iface.mainWindow(), tr('favorite_dialog_title'), tr('favorite_dialog_label')
        )
        label = (label or '').strip()
        if not ok or not label:
            return
        favorites = self._config.get('favorites', [])
        favorites.append({'label': label, 'lon': lon, 'lat': lat})
        self._config['favorites'] = favorites
        self._save_config()
        self._push_favorites()
        self.iface.messageBar().pushMessage(
            'Magic Search', tr('msg_favorite_saved', label=label), level=Qgis.MessageLevel.Success, duration=4
        )

    def _remove_favorite(self, index):
        favorites = self._config.get('favorites', [])
        if 0 <= index < len(favorites):
            del favorites[index]
            self._config['favorites'] = favorites
            self._save_config()
            self._push_favorites()

    def _push_favorites(self):
        favorites = self._config.get('favorites', [])
        if self.search_widget:
            self.search_widget.set_favorites(favorites)
        if self.dock_widget:
            self.dock_widget.set_favorites(favorites)

    def _on_reverse_address_found(self, label):
        """Affiche l'adresse trouvee par l'outil "?" directement dans la barre
        de recherche du style d'UI actif."""
        if self.search_widget:
            self.search_widget.show_reverse_address(label)
        if self.dock_widget:
            self.dock_widget.show_reverse_address(label)

    def _on_reverse_address_not_found(self, message):
        """Affiche le message "aucune adresse trouvee" directement dans la
        barre de recherche du style d'UI actif."""
        if self.search_widget:
            self.search_widget.show_reverse_not_found(message)
        if self.dock_widget:
            self.dock_widget.show_reverse_not_found(message)

    def _build_ui(self):
        ui_style = self._config.get('ui_style', 'maps')

        canvas = self.iface.mapCanvas()
        if self.reverse_tool and canvas.mapTool() is self.reverse_tool:
            canvas.unsetMapTool(self.reverse_tool)
        if self.street_view_tool and canvas.mapTool() is self.street_view_tool:
            canvas.unsetMapTool(self.street_view_tool)
        if self.favorite_tool and canvas.mapTool() is self.favorite_tool:
            canvas.unsetMapTool(self.favorite_tool)

        if ui_style != 'maps' and self.search_widget:
            self.search_widget.cleanup()
            self.search_widget.deleteLater()
            self.search_widget = None
        if ui_style != 'qt5' and self.dock_widget:
            self.dock_widget.cleanup()
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

        if ui_style == 'maps':
            from .ui.search_widget import MagicSearchWidget
            if not self.search_widget:
                self.search_widget = MagicSearchWidget(
                    self.iface,
                    self.index_manager,
                    self.ban_provider,
                    self.osm_provider,
                    self.layer_provider,
                    opacity=self._config.get('opacity', 100)
                )
                self.search_widget.config_requested.connect(self._open_config)
                self.search_widget.sync_requested.connect(self._sync_now)
                self.search_widget.reverse_toggled.connect(self._toggle_reverse_tool)
                self.search_widget.street_view_requested.connect(self._activate_street_view)
                self.search_widget.add_favorite_requested.connect(self._activate_add_favorite)
                self.search_widget.remove_favorite_requested.connect(self._remove_favorite)
                self.search_widget.set_favorites(self._config.get('favorites', []))
            self.search_widget.setVisible(self._visible)

        else:  # qt5
            from .ui.dock_widget import MagicSearchDockWidget
            is_new = self.dock_widget is None
            if is_new:
                self.dock_widget = MagicSearchDockWidget(
                    self.iface,
                    self.index_manager,
                    self.ban_provider,
                    self.osm_provider,
                    self.layer_provider,
                    self.iface.mainWindow()
                )
                self.dock_widget.config_requested.connect(self._open_config)
                self.dock_widget.sync_requested.connect(self._sync_now)
                self.dock_widget.reverse_toggled.connect(self._toggle_reverse_tool)
                self.dock_widget.street_view_requested.connect(self._activate_street_view)
                self.dock_widget.add_favorite_requested.connect(self._activate_add_favorite)
                self.dock_widget.remove_favorite_requested.connect(self._remove_favorite)
                self.dock_widget.set_favorites(self._config.get('favorites', []))

            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.set_opacity(self._config.get('opacity', 100))

            if is_new:
                self.dock_widget.setFloating(True)
                canvas = self.iface.mapCanvas()
                canvas_pos = canvas.mapToGlobal(canvas.rect().topLeft())
                cx = canvas_pos.x() + canvas.width() // 2 - 200
                cy = canvas_pos.y() + 60
                self.dock_widget.move(cx, cy)
                self.dock_widget.resize(400, 70)

            self.dock_widget.setVisible(self._visible)

    def unload(self):
        if self.index_manager:
            self.index_manager.stop()

        try:
            QgsProject.instance().layersAdded.disconnect(self._on_layers_added)
            QgsProject.instance().layersRemoved.disconnect(self._on_layers_removed)
            QgsProject.instance().readProject.disconnect(self._on_project_loaded)
            QgsProject.instance().cleared.disconnect(self._on_project_closed)
            self.iface.newProjectCreated.disconnect(self._on_project_loaded)
            self.iface.mapCanvas().mapToolSet.disconnect(self._on_map_tool_set)
        except Exception:
            pass

        if self.reverse_tool:
            canvas = self.iface.mapCanvas()
            if canvas.mapTool() is self.reverse_tool:
                canvas.unsetMapTool(self.reverse_tool)
            self.reverse_tool.clear_marker()
            self.reverse_tool = None
        if self.street_view_tool:
            canvas = self.iface.mapCanvas()
            if canvas.mapTool() is self.street_view_tool:
                canvas.unsetMapTool(self.street_view_tool)
            self.street_view_tool = None
        if self.favorite_tool:
            canvas = self.iface.mapCanvas()
            if canvas.mapTool() is self.favorite_tool:
                canvas.unsetMapTool(self.favorite_tool)
            self.favorite_tool = None

        if self.action_toggle:
            self.iface.removeToolBarIcon(self.action_toggle)
            self.iface.removePluginMenu('&Magic Search', self.action_toggle)
        if self.action_config:
            self.iface.removePluginMenu('&Magic Search', self.action_config)

        if self.shortcut:
            self.shortcut.setEnabled(False)
            self.shortcut = None

        if self.search_widget:
            self.search_widget.cleanup()
            self.search_widget = None
        if self.dock_widget:
            self.dock_widget.cleanup()
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None

    def _toggle_visibility(self, checked):
        self._visible = checked
        if self.search_widget:
            self.search_widget.setVisible(checked)
            if checked:
                self.search_widget.raise_()
        if self.dock_widget:
            self.dock_widget.setVisible(checked)

    def _focus_search(self):
        self._visible = True
        if self.search_widget:
            self.search_widget.setVisible(True)
            self.search_widget.set_focus()
            if self.action_toggle:
                self.action_toggle.setChecked(True)
        if self.dock_widget:
            self.dock_widget.setVisible(True)
            self.dock_widget.set_focus()
            if self.action_toggle:
                self.action_toggle.setChecked(True)

    def _open_config(self):
        from .ui.config_dialog import ConfigDialog
        dlg = ConfigDialog(self._config, lang=i18n.current_lang(),
                           parent=self.iface.mainWindow())
        dlg.config_changed.connect(self._on_config_changed)
        dlg.reindex_requested.connect(self._force_reindex)
        dlg.exec()

    def _detect_qgis_lang(self):
        """Deduit une langue supportee a partir de la locale QGIS (sinon 'en')."""
        try:
            locale = QgsApplication.instance().locale()
        except Exception:
            locale = ''
        code = (locale or '')[:2].lower()
        return code if code in SUPPORTED_LANGS else 'en'

    def _on_config_changed(self, config):
        old_ui = self._config.get('ui_style', 'maps')
        self._config = config
        self._save_config()
        self._apply_config()
        # Les exclusions viennent peut-etre de changer : l'index peut etre
        # devenu incomplet (couche reintegree) sans qu'on ait rien indexe.
        if self.index_manager:
            self.index_manager.refresh_sync_state()
        if old_ui != self._config.get('ui_style', 'maps'):
            self._build_ui()

    def _apply_config(self):
        # La langue est appliquee en premier : les libelles construits juste
        # apres (actions, widgets) doivent deja etre dans la bonne langue.
        i18n.set_lang(self._config.get('lang') or self._detect_qgis_lang())
        self._retranslate()

        geocoder = self._config.get('geocoder', 'ban')
        if self.ban_provider:
            self.ban_provider.set_enabled(geocoder == 'ban')
            self.ban_provider.set_postcode_filter(self._config.get('ban_postcode', ''))
        if self.osm_provider:
            self.osm_provider.set_enabled(geocoder == 'osm')
        if self.reverse_tool:
            self.reverse_tool.set_radius(self._config.get('reverse_radius_m', 25))

        if self.index_manager:
            self.index_manager.set_config(
                self._config.get('layers', {}),
                self._config.get('max_cache_mb', 50),
                self._config.get('index_all_types', False),
                self._config.get('search_all_layers', False)
            )

        geo_actions.set_point_scale(
            self._config.get('zoom_scale', geo_actions.DEFAULT_POINT_SCALE)
        )

        opacity = self._config.get('opacity', 100)
        if self.search_widget:
            self.search_widget.set_opacity(opacity)
        if self.dock_widget:
            self.dock_widget.set_opacity(opacity)

    def _retranslate(self):
        """Applique la langue courante aux actions QGIS et aux widgets existants."""
        if self.action_toggle:
            self.action_toggle.setToolTip(tr('tip_toggle'))
        if self.action_config:
            self.action_config.setText(tr('menu_config'))
        if self.search_widget:
            self.search_widget.retranslate()
        if self.dock_widget:
            self.dock_widget.retranslate()

    def _sync_now(self):
        """Bouton de synchronisation de la barre : lance (ou relance) une passe
        d'indexation a la demande.

        C'est desormais le seul point d'entree automatique : rien n'est indexe
        tant que l'utilisateur n'a pas clique. Le cache disque est conserve,
        donc une couche deja indexee et inchangee est simplement relue.
        """
        if not self.index_manager:
            return
        if self.index_manager.is_running():
            # Deja en cours : un second clic ne doit pas tout reprendre a zero.
            return
        self.index_manager.start_indexing(force=True)

    def _force_reindex(self):
        """Bouton "Reindexer maintenant" : purge du cache puis rescan complet."""
        if self.index_manager:
            self.index_manager.stop()
            self.index_manager.start_indexing(force=True, purge=True)

    def _on_layers_added(self, layers):
        """Une couche ajoutee rend l'index incomplet : le bouton passe en
        orange, mais rien n'est indexe sans clic de l'utilisateur."""
        if self.index_manager:
            self.index_manager.refresh_sync_state()

    def _on_layers_removed(self, layer_ids):
        if self.index_manager:
            for lid in layer_ids:
                self.index_manager.remove_layer(lid)
            self.index_manager.refresh_sync_state()

    def _on_project_loaded(self, doc=None):
        """Nouveau projet ouvert : recharger la config et reconstruire l'UI.
        La visibilite courante (self._visible) est preservee, jamais forcee."""
        if self.index_manager:
            self.index_manager.stop()
        self._load_config()
        self._apply_config()
        if self.index_manager:
            # Nouveau projet = index a refaire, mais a la demande seulement :
            # le bouton de synchronisation passe au rouge et attend le clic.
            self.index_manager.clear_index()
            self.index_manager.refresh_sync_state()
        self._build_ui()
        self._push_favorites()
        if self.action_toggle:
            self.action_toggle.setChecked(self._visible)

    def _on_project_closed(self):
        """Projet fermé : masquer l'UI et vider l'index."""
        if self.index_manager:
            self.index_manager.clear_index()
            self.index_manager.refresh_sync_state()
        self._visible = False
        if self.search_widget:
            self.search_widget.hide()
        if self.dock_widget:
            self.dock_widget.hide()
        if self.action_toggle:
            self.action_toggle.setChecked(False)

    def _save_config(self):
        # Partie projet : couches exclues, favoris...
        project = QgsProject.instance()
        project_config = {k: v for k, v in self._config.items()
                          if k not in GLOBAL_KEYS}
        config_json = json.dumps(project_config, ensure_ascii=False)
        project.writeEntry(CONFIG_KEY, 'config', config_json)

        # Partie globale : preferences memorisees hors projet.
        settings = QSettings()
        settings.beginGroup(SETTINGS_GROUP)
        for key in GLOBAL_KEYS:
            if key in self._config:
                settings.setValue(key, self._config[key])
        settings.endGroup()

    def _load_config(self):
        project = QgsProject.instance()
        config_json, ok = project.readEntry(CONFIG_KEY, 'config', '{}')
        config = {}
        if ok and config_json:
            try:
                config = json.loads(config_json)
            except Exception:
                config = {}
        if not isinstance(config, dict):
            config = {}

        # Les preferences globales priment sur les valeurs heritees d'anciens
        # projets (ou elles etaient stockees dans le .qgz).
        settings = QSettings()
        settings.beginGroup(SETTINGS_GROUP)
        for key in GLOBAL_KEYS:
            value = settings.value(key, None)
            if value is None:
                continue
            if key in INT_KEYS:
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            elif key in BOOL_KEYS:
                # QSettings rend les booleens sous forme de chaine sur Windows
                value = str(value).lower() in ('true', '1')
            else:
                value = str(value)
            config[key] = value
        settings.endGroup()

        self._config = config
