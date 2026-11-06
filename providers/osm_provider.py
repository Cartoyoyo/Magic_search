"""
OSM Provider - Recherche de lieux via l'API Nominatim (OpenStreetMap).
Utilise QgsNetworkAccessManager (pas de fenetre parasite SSL/proxy).
Respecte la politique Nominatim : 1 requete/s max, User-Agent obligatoire.
"""

import os
import json
import urllib.parse
from qgis.PyQt.QtCore import QObject, QUrl, QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsMessageLog, QgsNetworkAccessManager, Qgis


NOMINATIM_URL = (
    'https://nominatim.openstreetmap.org/search'
    '?q={query}&format=json&addressdetails=1&limit=3'
)
DEBOUNCE_MS = 1200
TAG = 'Magic Search'


def _plugin_version():
    """Version lue dans metadata.txt : le User-Agent Nominatim ne peut pas
    se desynchroniser de la version publiee du plugin."""
    meta = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'metadata.txt')
    try:
        with open(meta, encoding='utf-8') as f:
            for line in f:
                if line.startswith('version='):
                    return line.split('=', 1)[1].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return '0.0.0'


# Politique Nominatim : User-Agent identifiant l'application + moyen de contact.
USER_AGENT = f'QGIS-MagicSearch/{_plugin_version()} (+https://github.com/Cartoyoyo/Magic_search)'


class OsmProvider(QObject):
    results_ready = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QgsNetworkAccessManager.instance()
        self._reply = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_request)
        self._pending_query = ''
        self._enabled = True

    def set_enabled(self, enabled):
        self._enabled = enabled

    def search(self, query):
        if not self._enabled or not query or len(query) < 3:
            return
        self._pending_query = query
        self._timer.start(DEBOUNCE_MS)

    def cancel(self):
        self._timer.stop()
        if self._reply and self._reply.isRunning():
            self._reply.abort()

    def _do_request(self):
        if self._reply and self._reply.isRunning():
            self._reply.abort()

        url_str = NOMINATIM_URL.format(
            query=urllib.parse.quote(self._pending_query, safe='')
        )
        url = QUrl(url_str)
        request = QNetworkRequest(url)
        request.setRawHeader(b'User-Agent', USER_AGENT.encode('utf-8'))
        request.setRawHeader(b'Accept-Language', b'fr,en')
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return

        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            # Requete abandonnee pour une saisie plus recente : normal.
            reply.deleteLater()
            self._reply = None
            return

        if reply.error() != QNetworkReply.NetworkError.NoError:
            QgsMessageLog.logMessage(
                f"OSM error: {reply.error()} - {reply.errorString()}",
                TAG, Qgis.MessageLevel.Warning
            )
            reply.deleteLater()
            self._reply = None
            self.results_ready.emit([])
            return

        try:
            raw = reply.readAll()
            text = raw.data().decode('utf-8')
            data = json.loads(text)

            results = []
            for item in data:
                results.append({
                    'label': item.get('display_name', ''),
                    'type': item.get('type', ''),
                    'osm_type': item.get('osm_type', ''),
                    'lon': float(item.get('lon', 0)),
                    'lat': float(item.get('lat', 0)),
                })

            self.results_ready.emit(results)

        except Exception as e:
            QgsMessageLog.logMessage(f"OSM parse error: {e}", TAG, Qgis.MessageLevel.Warning)
            self.results_ready.emit([])

        finally:
            reply.deleteLater()
            self._reply = None
