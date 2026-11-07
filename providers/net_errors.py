"""
Diagnostic commun des echecs reseau des geocodeurs (BAN, OSM).

Un geocodeur injoignable doit se voir dans la liste ("BAN indisponible")
au lieu de ressembler a une recherche sans reponse. Trois causes sont
distinguees, emises par le signal `failed(raison, statut_http)` des
fournisseurs : pas de reseau, pas de reponse a temps, erreur du service.

Les abandons voulus (saisie plus recente, champ efface) sont marques sur la
reponse avant `abort()` : seuls ceux-la restent silencieux. Un abandon non
marque vient d'un delai depasse (le notre ou celui de QGIS).
"""

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from ..i18n import tr

# Le BAN repond d'ordinaire en moins d'une seconde ; sans ce delai, une
# panne silencieuse (proxy, pare-feu) ne se signale qu'au bout du delai
# reseau de QGIS (60 s par defaut).
REQUEST_TIMEOUT_MS = 10000

SUPERSEDED = 'superseded'
OFFLINE = 'offline'
TIMEOUT = 'timeout'
SERVICE = 'service'

_PROP_SUPERSEDED = 'magic_search_superseded'
_Err = QNetworkReply.NetworkError


def _code(value):
    """Valeur entiere d'une enum Qt (PyQt5 : int ; PyQt6 : enum Python)."""
    return int(getattr(value, 'value', value))


_TIMEOUT_CODES = {_code(_Err.TimeoutError), _code(_Err.ProxyTimeoutError)}


def abort_superseded(reply):
    """Abandonne une requete devenue inutile, sans la compter comme panne."""
    if reply is not None and reply.isRunning():
        reply.setProperty(_PROP_SUPERSEDED, True)
        reply.abort()


def arm_timeout(reply, ms=REQUEST_TIMEOUT_MS):
    """Abandonne la requete si elle n'a pas abouti au bout de `ms`. Le minuteur
    est enfant de la reponse : il disparait avec elle."""
    timer = QTimer(reply)
    timer.setSingleShot(True)
    timer.timeout.connect(reply.abort)
    timer.start(ms)


def classify(reply):
    """'' si la reponse est exploitable, SUPERSEDED si elle a ete abandonnee
    volontairement, sinon la cause de l'echec (OFFLINE, TIMEOUT, SERVICE)."""
    err = reply.error()
    if err == _Err.NoError:
        return ''
    if err == _Err.OperationCanceledError:
        return SUPERSEDED if reply.property(_PROP_SUPERSEDED) else TIMEOUT
    code = _code(err)
    if code in _TIMEOUT_CODES:
        return TIMEOUT
    # 1-99 : couche reseau (hote introuvable, connexion refusee, SSL...) ;
    # 101-199 : proxy. Au-dela : le service a repondu, mais par une erreur.
    if code < 200:
        return OFFLINE
    return SERVICE


def http_status(reply):
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    try:
        return int(status or 0)
    except (TypeError, ValueError):
        return 0


def describe(source, reason, status=0):
    """(titre, detail) affiches a la place des reponses du geocodeur."""
    detail = tr('geo_err_' + reason) if reason in (OFFLINE, TIMEOUT, SERVICE)         else tr('geo_err_service')
    if reason == SERVICE and status:
        detail += ' (HTTP %d)' % status
    return tr('geo_unavailable', source=source), detail


def describe_inline(source, reason, status=0):
    """Version sur une ligne, pour le champ de saisie (adresse au clic)."""
    title, detail = describe(source, reason, status)
    return '%s (%s)' % (title, detail)
