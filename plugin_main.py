"""
Magic Search - Plugin principal.
Barre de recherche flottante style Google Maps sur le canevas QGIS.
"""

import os
import json
from qgis.PyQt.QtWidgets import QAction, QShortcut
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsVectorLayer

CONFIG_KEY = 'MagicSearch'


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
        self._config = {}
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        self._load_config()

        from .core.index_manager import IndexManager
        from .providers.ban_provider import BanProvider
        from .providers.osm_provider import OsmProvider
        from .providers.layer_provider import LayerProvider

        self.index_manager = IndexManager()
        self.ban_provider = BanProvider()
        self.osm_provider = OsmProvider()
        self.layer_provider = LayerProvider(self.index_manager)

        self._apply_config()

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action_toggle = QAction(icon, 'Magic Search', self.iface.mainWindow())
        self.action_toggle.setCheckable(True)
        self.action_toggle.setChecked(False)
        self.action_toggle.setToolTip('Afficher / Masquer Magic Search')
        self.action_toggle.triggered.connect(self._toggle_visibility)
        self.iface.addToolBarIcon(self.action_toggle)
        self.iface.addPluginToMenu('&Magic Search', self.action_toggle)

        self.action_config = QAction('Magic Search - Config', self.iface.mainWindow())
        self.action_config.triggered.connect(self._open_config)
        self.iface.addPluginToMenu('&Magic Search', self.action_config)

        self.shortcut = QShortcut(
            QKeySequence('Ctrl+Shift+F'),
            self.iface.mainWindow()
        )
        self.shortcut.activated.connect(self._focus_search)

        QgsProject.instance().layersRemoved.connect(self._on_layers_removed)
        QgsProject.instance().readProject.connect(self._on_project_loaded)
        QgsProject.instance().cleared.connect(self._on_project_closed)

        # Affichage uniquement si un projet est déjà ouvert
        if QgsProject.instance().fileName():
            self._build_ui()
            if self.action_toggle:
                self.action_toggle.setChecked(True)

    def _build_ui(self):
        ui_style = self._config.get('ui_style', 'maps')

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
            from .search_widget import MagicSearchWidget
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
                self.search_widget.sync_requested.connect(self._force_reindex)
            self.search_widget.show()

        else:  # qt5
            from .dock_widget import MagicSearchDockWidget
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
                self.dock_widget.sync_requested.connect(self._force_reindex)

            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.set_opacity(self._config.get('opacity', 100))

            if is_new:
                self.dock_widget.setFloating(True)
                canvas = self.iface.mapCanvas()
                canvas_pos = canvas.mapToGlobal(canvas.rect().topLeft())
                cx = canvas_pos.x() + canvas.width() // 2 - 200
                cy = canvas_pos.y() + 60
                self.dock_widget.move(cx, cy)
                self.dock_widget.resize(400, 70)

            self.dock_widget.show()

    def unload(self):
        if self.index_manager:
            self.index_manager.stop()

        try:
            QgsProject.instance().layersRemoved.disconnect(self._on_layers_removed)
            QgsProject.instance().readProject.disconnect(self._on_project_loaded)
            QgsProject.instance().cleared.disconnect(self._on_project_closed)
        except Exception:
            pass

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
        if self.search_widget:
            self.search_widget.setVisible(checked)
            if checked:
                self.search_widget.raise_()
        if self.dock_widget:
            self.dock_widget.setVisible(checked)

    def _focus_search(self):
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
        from .config_dialog import ConfigDialog
        dlg = ConfigDialog(self._config, parent=self.iface.mainWindow())
        dlg.config_changed.connect(self._on_config_changed)
        dlg.reindex_requested.connect(self._force_reindex)
        dlg.exec_()

    def _on_config_changed(self, config):
        old_ui = self._config.get('ui_style', 'maps')
        self._config = config
        self._save_config()
        self._apply_config()
        if old_ui != self._config.get('ui_style', 'maps'):
            self._build_ui()

    def _apply_config(self):
        geocoder = self._config.get('geocoder', 'ban')
        if self.ban_provider:
            self.ban_provider.set_enabled(geocoder == 'ban')
        if self.osm_provider:
            self.osm_provider.set_enabled(geocoder == 'osm')

        if self.index_manager:
            self.index_manager.set_config(
                self._config.get('layers', {}),
                self._config.get('max_cache_mb', 50)
            )

        opacity = self._config.get('opacity', 100)
        if self.search_widget:
            self.search_widget.set_opacity(opacity)
        if self.dock_widget:
            self.dock_widget.set_opacity(opacity)

    def _force_reindex(self):
        if self.index_manager:
            self.index_manager.stop()
            self.index_manager.start_indexing()

    def _on_layers_removed(self, layer_ids):
        if self.index_manager:
            for lid in layer_ids:
                self.index_manager.remove_layer(lid)

    def _on_project_loaded(self, doc):
        """Nouveau projet ouvert : recharger la config et reconstruire l'UI."""
        if self.index_manager:
            self.index_manager.stop()
        self._load_config()
        self._apply_config()
        self._build_ui()
        if self.action_toggle:
            self.action_toggle.setChecked(True)

    def _on_project_closed(self):
        """Projet fermé : masquer l'UI et vider l'index."""
        if self.index_manager:
            self.index_manager.stop()
        if self.search_widget:
            self.search_widget.hide()
        if self.dock_widget:
            self.dock_widget.hide()
        if self.action_toggle:
            self.action_toggle.setChecked(False)

    def _save_config(self):
        project = QgsProject.instance()
        config_json = json.dumps(self._config, ensure_ascii=False)
        project.writeEntry(CONFIG_KEY, 'config', config_json)

    def _load_config(self):
        project = QgsProject.instance()
        config_json, ok = project.readEntry(CONFIG_KEY, 'config', '{}')
        if ok and config_json:
            try:
                self._config = json.loads(config_json)
            except Exception:
                self._config = {}
        else:
            self._config = {}
