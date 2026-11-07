"""
OSM Provider - Recherche de lieux via l'API Nominatim (OpenStreetMap).
Utilise QgsNetworkAccessManager (pas de fenetre parasite SSL/proxy).
Respecte la politique Nominatim : 1 requete/s max, User-Agent obligatoire.
"""

import os
import json
import urllib.parse
from functools import partial
from qgis.PyQt.QtCore import QObject, QUrl, QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import QgsMessageLog, QgsNetworkAccessManager, Qgis

from . import net_errors


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
    failed = pyqtSignal(str, int)   # cause (net_errors), statut HTTP ou 0

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
        """Programme une requete ; False si Nominatim ne sera pas interroge
        (desactive ou saisie trop courte)."""
        if not self._enabled or not query or len(query) < 3:
            return False
        self._pending_query = query
        self._timer.start(DEBOUNCE_MS)
        return True

    def cancel(self):
        self._timer.stop()
        net_errors.abort_superseded(self._reply)

    def _do_request(self):
        net_errors.abort_superseded(self._reply)

        url_str = NOMINATIM_URL.format(
            query=urllib.parse.quote(self._pending_query, safe='')
        )
        url = QUrl(url_str)
        request = QNetworkRequest(url)
        request.setRawHeader(b'User-Agent', USER_AGENT.encode('utf-8'))
        request.setRawHeader(b'Accept-Language', b'fr,en')
        reply = self._nam.get(request)
        self._reply = reply
        net_errors.arm_timeout(reply)
        reply.finished.connect(partial(self._on_finished, reply))

    def _on_finished(self, reply):
        if reply is self._reply:
            self._reply = None
        reply.deleteLater()

        reason = net_errors.classify(reply)
        if reason == net_errors.SUPERSEDED:
            # Requete abandonnee pour une saisie plus recente : normal.
            return
        if reason:
            QgsMessageLog.logMessage(
                f"OSM error ({reason}): {reply.error()} - {reply.errorString()}",
                TAG, Qgis.MessageLevel.Warning
            )
            self.failed.emit(reason, net_errors.http_status(reply))
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
        except Exception as e:
            QgsMessageLog.logMessage(f"OSM parse error: {e}", TAG, Qgis.MessageLevel.Warning)
            self.failed.emit(net_errors.SERVICE, net_errors.http_status(reply))
            return

        self.results_ready.emit(results)
