"""
BAN Provider - Recherche d'adresses via l'API BAN.
Utilise QgsNetworkAccessManager (pas de fenetre parasite SSL/proxy).
"""

import json
import urllib.parse
from functools import partial
from qgis.PyQt.QtCore import QObject, QUrl, QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import QgsMessageLog, QgsNetworkAccessManager, Qgis

from . import net_errors


BAN_URL = 'https://api-adresse.data.gouv.fr/search/?q={query}&limit=3'
BAN_REVERSE_URL = 'https://api-adresse.data.gouv.fr/reverse/?lon={lon}&lat={lat}&limit=1'
DEBOUNCE_MS = 1000
TAG = 'Magic Search'


class BanProvider(QObject):
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
        self._postcode_filter = ''
        self._focus_provider = None

    def set_focus_provider(self, provider):
        """`provider()` rend (lon, lat) ou None : le point autour duquel le BAN
        doit privilegier ses reponses (le centre de la carte). Sans lui,
        "rue de Paris" tape depuis Vichy donnait Amiens, Rennes, Montreuil."""
        self._focus_provider = provider

    def set_enabled(self, enabled):
        self._enabled = enabled

    def set_postcode_filter(self, postcode):
        """Restreint les resultats BAN a un code postal (utile en zone a
        toponymie ambigue entre communes voisines). Vide = pas de filtre."""
        self._postcode_filter = (postcode or '').strip()

    def search(self, query):
        """Programme une requete ; False si le BAN ne sera pas interroge
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
        # Annuler la requete precedente si elle tourne encore
        net_errors.abort_superseded(self._reply)

        url_str = BAN_URL.format(query=urllib.parse.quote(self._pending_query, safe=''))
        if self._postcode_filter:
            url_str += '&postcode=' + urllib.parse.quote(self._postcode_filter, safe='')
        focus = self._focus_provider() if self._focus_provider else None
        if focus:
            # Priorite de proximite, pas un filtre : une adresse lointaine
            # reste trouvable si elle est seule a correspondre.
            url_str += '&lon=%.5f&lat=%.5f' % focus
        url = QUrl(url_str)
        request = QNetworkRequest(url)
        reply = self._nam.get(request)
        self._reply = reply
        net_errors.arm_timeout(reply)
        # La reponse est passee au gestionnaire : une reponse abandonnee qui
        # arrive apres la suivante ne doit pas etre confondue avec elle.
        reply.finished.connect(partial(self._on_finished, reply))

    def _on_finished(self, reply):
        if reply is self._reply:
            self._reply = None
        reply.deleteLater()

        reason = net_errors.classify(reply)
        if reason == net_errors.SUPERSEDED:
            # Requete abandonnee pour une saisie plus recente (ou un champ
            # efface) : c'est le fonctionnement normal, pas une erreur.
            return
        if reason:
            QgsMessageLog.logMessage(
                f"BAN error ({reason}): {reply.error()} - {reply.errorString()}",
                TAG, Qgis.MessageLevel.Warning
            )
            self.failed.emit(reason, net_errors.http_status(reply))
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
        except Exception as e:
            # Reponse illisible (page d'erreur d'un proxy, JSON tronque) :
            # le service est la, mais inutilisable.
            QgsMessageLog.logMessage(f"BAN parse error: {e}", TAG, Qgis.MessageLevel.Warning)
            self.failed.emit(net_errors.SERVICE, net_errors.http_status(reply))
            return

        self.results_ready.emit(results)


class BanReverseProvider(QObject):
    """Geocodage inverse BAN : trouve l'adresse la plus proche d'un point (lon, lat).
    Utilise pour l'outil "?" de la barre d'outils (clic sur la carte)."""

    result_ready = pyqtSignal(dict)
    failed = pyqtSignal(str, int)   # cause (net_errors), statut HTTP ou 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nam = QgsNetworkAccessManager.instance()
        self._reply = None

    def reverse(self, lon, lat):
        net_errors.abort_superseded(self._reply)

        url_str = BAN_REVERSE_URL.format(lon=lon, lat=lat)
        request = QNetworkRequest(QUrl(url_str))
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
            # Second clic avant la reponse du premier : seul le dernier compte.
            return
        if reason:
            QgsMessageLog.logMessage(
                f"BAN reverse error ({reason}): {reply.error()} - {reply.errorString()}",
                TAG, Qgis.MessageLevel.Warning
            )
            self.failed.emit(reason, net_errors.http_status(reply))
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
            self.failed.emit(net_errors.SERVICE, net_errors.http_status(reply))
