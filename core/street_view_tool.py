"""
StreetViewTool - Outil carte active depuis le menu deroulant de la barre de
recherche (bouton a cote du "?"). Un clic sur le canevas ouvre, dans le
navigateur par defaut, la vue de rue du point clique sur le service choisi
(Google Street View, Mapillary ou Panoramax). Usage unique : l'outil se
desactive automatiquement apres chaque clic.
"""
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
from qgis.gui import QgsMapToolEmitPoint

SERVICE_LABELS = {
    'google': 'Google Street View',
    'mapillary': 'Mapillary',
    'panoramax': 'Panoramax',
    'bing': 'Bing Streetside',
}

# {lat}/{lon} injectes au clic (voir canvasReleaseEvent). Ces URLs centrent
# la vue au plus pres du point clique ; la couverture reelle depend du service.
# Bing Streetside necessite un identifiant de panorama pour un lancement direct
# (non disponible sans requete a l'API Bing) : le lien centre la carte Bing au
# plus proche, a l'utilisateur d'activer Streetside si la couverture existe.
SERVICE_URLS = {
    'google': 'https://www.google.com/maps?layer=c&cbll={lat},{lon}&cbp=11,0,0,0,0',
    'mapillary': 'https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=17&focus=map',
    'panoramax': 'https://panoramax.openstreetmap.fr/#focus=map&map=17/{lat}/{lon}',
    'bing': 'https://www.bing.com/maps?cp={lat}~{lon}&lvl=19&style=r',
}


class StreetViewTool(QgsMapToolEmitPoint):
    def __init__(self, iface):
        canvas = iface.mapCanvas()
        super().__init__(canvas)
        self._iface = iface
        self._service = 'google'

    def set_service(self, service):
        self._service = service

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        canvas = self._iface.mapCanvas()
        crs_src = canvas.mapSettings().destinationCrs()
        crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        wgs84_point = transform.transform(point)

        url_template = SERVICE_URLS.get(self._service, SERVICE_URLS['google'])
        url = url_template.format(lat=wgs84_point.y(), lon=wgs84_point.x())
        QDesktopServices.openUrl(QUrl(url))

        canvas.unsetMapTool(self)
