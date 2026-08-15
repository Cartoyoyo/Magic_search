"""
ReverseGeocodeTool - Outil carte active par le bouton "?" de la barre de recherche.
Un clic sur le canevas interroge le geocodage inverse BAN. Si l'adresse trouvee
est a moins du rayon configure (set_radius, 25 m par defaut), elle est emise
via address_found pour etre affichee directement dans la barre de recherche
(voir plugin_main). Le repere du dernier point clique reste visible sur la
carte tant qu'aucun nouveau clic n'est effectue (voir clear_marker pour un
nettoyage explicite, ex: fermeture du plugin).
"""
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.gui import QgsMapToolEmitPoint

from . import geo_actions
from ..i18n import tr

DEFAULT_RADIUS_M = 25


class ReverseGeocodeTool(QgsMapToolEmitPoint):
    address_found = pyqtSignal(str)
    address_not_found = pyqtSignal(str)  # message a afficher dans la barre

    def __init__(self, iface, ban_reverse_provider):
        canvas = iface.mapCanvas()
        super().__init__(canvas)
        self._iface = iface
        self._provider = ban_reverse_provider
        self._rubber_band = None
        self._radius_m = DEFAULT_RADIUS_M
        self._provider.result_ready.connect(self._on_result)

    def set_radius(self, radius_m):
        self._radius_m = radius_m if radius_m and radius_m > 0 else DEFAULT_RADIUS_M

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        canvas = self._iface.mapCanvas()
        crs_src = canvas.mapSettings().destinationCrs()
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        wgs84_point = transform.transform(point)

        self._rubber_band = geo_actions.clear_rubber(self._rubber_band)
        self._rubber_band = geo_actions.make_point_rubber(
            canvas, point, color=geo_actions.COLOR_HIGHLIGHT
        )

        self._provider.reverse(wgs84_point.x(), wgs84_point.y())

    def _on_result(self, data):
        if not data or data.get('distance', self._radius_m + 1) > self._radius_m:
            self.address_not_found.emit(tr('msg_reverse_none', max=self._radius_m))
            return

        self.address_found.emit(data['label'])

    def clear_marker(self):
        """Nettoyage explicite du repere (ex: a l'unload du plugin). Le repere
        n'est plus efface automatiquement a la desactivation de l'outil, pour
        garder une trace visuelle du dernier point interroge."""
        self._rubber_band = geo_actions.clear_rubber(self._rubber_band)
