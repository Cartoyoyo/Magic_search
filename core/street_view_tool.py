"""
StreetViewTool - Outil carte active depuis le menu deroulant de la barre de
recherche (bouton a cote du "?"). Un clic sur le canevas ouvre, dans le
navigateur par defaut, la vue de rue du point clique sur le service choisi
(Google Street View, Mapillary, Panoramax ou Bing Streetside), ou copie ses
coordonnees dans le presse-papiers (service 'copy_coords'). Usage unique :
l'outil se desactive automatiquement apres chaque clic.
"""
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, Qgis
from qgis.gui import QgsMapToolEmitPoint

from .qt_compat import event_pos

from ..i18n import tr

COPY_COORDS = 'copy_coords'

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
        point = self.toMapCoordinates(event_pos(event))
        canvas = self._iface.mapCanvas()
        crs_src = canvas.mapSettings().destinationCrs()
        project = QgsProject.instance()

        wgs84 = QgsCoordinateTransform(
            crs_src, QgsCoordinateReferenceSystem('EPSG:4326'), project
        ).transform(point)

        if self._service == COPY_COORDS:
            lambert93 = QgsCoordinateTransform(
                crs_src, QgsCoordinateReferenceSystem('EPSG:2154'), project
            ).transform(point)
            text = (
                f"WGS84 : {wgs84.y():.6f}, {wgs84.x():.6f}\n"
                f"Lambert93 : {lambert93.x():.1f}, {lambert93.y():.1f}"
            )
            QApplication.clipboard().setText(text)
            self._iface.messageBar().pushMessage(
                'Magic Search', tr('msg_coords_copied'), level=Qgis.MessageLevel.Success, duration=4
            )
        else:
            url_template = SERVICE_URLS.get(self._service, SERVICE_URLS['google'])
            url = url_template.format(lat=wgs84.y(), lon=wgs84.x())
            QDesktopServices.openUrl(QUrl(url))

        canvas.unsetMapTool(self)
