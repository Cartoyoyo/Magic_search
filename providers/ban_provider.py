"""
BAN Provider - Recherche d'adresses via l'API BAN.
Utilise QgsNetworkAccessManager (pas de fenetre parasite SSL/proxy).
"""

import json
import urllib.parse
from qgis.PyQt.QtCore import QObject, QUrl, QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsMessageLog, QgsNetworkAccessManager, Qgis


BAN_URL = 'https://api-adresse.data.gouv.fr/search/?q={query}&limit=3'
BAN_REVERSE_URL = 'https://api-adresse.data.gouv.fr/reverse/?lon={lon}&lat={lat}&limit=1'
DEBOUNCE_MS = 1000
TAG = 'Magic Search'


class BanProvider(QObject):
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
        self._postcode_filter = ''

    def set_enabled(self, enabled):
        self._enabled = enabled

    def set_postcode_filter(self, postcode):
        """Restreint les resultats BAN a un code postal (utile en zone a
        toponymie ambigue entre communes voisines). Vide = pas de filtre."""
        self._postcode_filter = (postcode or '').strip()

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
        # Annuler la requete precedente si elle tourne encore
        if self._reply and self._reply.isRunning():
            self._reply.abort()

        url_str = BAN_URL.format(query=urllib.parse.quote(self._pending_query, safe=''))
        if self._postcode_filter:
            url_str += '&postcode=' + urllib.parse.quote(self._postcode_filter, safe='')
        url = QUrl(url_str)
        request = QNetworkRequest(url)
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return

        if reply.error() != QNetworkReply.NetworkError.NoError:
            QgsMessageLog.logMessage(
                f"BAN error: {reply.error()} - {reply.errorString()}",
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
            for feat in data.get('features', []):
                props = feat.get('properties', {})
                coords = feat.get('geometry', {}).get('coordinates', [0, 0])
                results.append({
                    'label': props.get('label', ''),
                    'city': props.get('city', ''),
                    'postcode': props.get('postcode', ''),
                    'type': props.get('type', ''),
                    'score': props.get('score', 0),
                    'lon': coords[0],
                    'lat': coords[1],
                })

            self.results_ready.emit(results)

        except Exception as e:
            QgsMessageLog.logMessage(f"BAN parse error: {e}", TAG, Qgis.MessageLevel.Warning)
            self.results_ready.emit([])

        finally:
            reply.deleteLater()
            self._reply = None


class BanReverseProvider(QObject):
    """Geocodage inverse BAN : trouve l'adresse la plus proche d'un point (lon, lat).
    Utilise pour l'outil "?" de la barre d'outils (clic sur la carte)."""

    result_ready = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QgsNetworkAccessManager.instance()
        self._reply = None

    def reverse(self, lon, lat):
        if self._reply and self._reply.isRunning():
            self._reply.abort()

        url_str = BAN_REVERSE_URL.format(lon=lon, lat=lat)
        request = QNetworkRequest(QUrl(url_str))
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return

        if reply.error() != QNetworkReply.NetworkError.NoError:
            QgsMessageLog.logMessage(
                f"BAN reverse error: {reply.error()} - {reply.errorString()}",
                TAG, Qgis.MessageLevel.Warning
            )
            reply.deleteLater()
            self._reply = None
            self.result_ready.emit({})
            return

        try:
            raw = reply.readAll()
            text = raw.data().decode('utf-8')
            data = json.loads(text)
            features = data.get('features', [])

            if not features:
                self.result_ready.emit({})
            else:
                props = features[0].get('properties', {})
                coords = features[0].get('geometry', {}).get('coordinates', [0, 0])
                self.result_ready.emit({
                    'label': props.get('label', ''),
                    'city': props.get('city', ''),
                    'postcode': props.get('postcode', ''),
                    'distance': props.get('distance', 0),
                    'lon': coords[0],
                    'lat': coords[1],
                })

        except Exception as e:
            QgsMessageLog.logMessage(f"BAN reverse parse error: {e}", TAG, Qgis.MessageLevel.Warning)
            self.result_ready.emit({})

        finally:
            reply.deleteLater()
            self._reply = None
