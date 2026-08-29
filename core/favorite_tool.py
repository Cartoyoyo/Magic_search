"""
FavoriteTool - Outil carte active depuis le menu "etoile" de la barre de
recherche : un clic sur la carte enregistre un point favori (regard, vanne,
point recurrent...). Usage unique : emet le point en WGS84 puis se desactive ;
plugin_main.py demande ensuite un libelle avant de le persister dans le projet.
"""
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.gui import QgsMapToolEmitPoint

from .qt_compat import event_pos


class FavoriteTool(QgsMapToolEmitPoint):
    point_picked = pyqtSignal(float, float)  # lon, lat (WGS84)

    def __init__(self, iface):
        canvas = iface.mapCanvas()
        super().__init__(canvas)
        self._iface = iface

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event_pos(event))
        canvas = self._iface.mapCanvas()
        crs_src = canvas.mapSettings().destinationCrs()
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        wgs84_point = transform.transform(point)
        self.point_picked.emit(wgs84_point.x(), wgs84_point.y())
        canvas.unsetMapTool(self)
