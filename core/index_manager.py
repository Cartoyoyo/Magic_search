"""
Index Manager - Indexation incrementale des couches QGIS sur le thread principal.
Traitement par morceaux via QTimer (un champ par tick) pour ne jamais bloquer l'UI.
Cache compresse MessagePack + gzip stocke a cote du fichier projet.
"""

import os
import gzip
import json
import hashlib
import unicodedata
from qgis.PyQt.QtCore import QTimer, pyqtSignal, QObject
from qgis.core import QgsProject, QgsVectorLayer, QgsMessageLog, Qgis

from ..i18n import tr

try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False

DEFAULT_MAX_CACHE_MB = 50
TAG = 'Magic Search'
TICK_MS = 10  # delai entre chaque lot d'entites
BATCH_SIZE = 2000 # entites par tick


def normalize_text(text):
    """Supprime accents et passe en minuscules pour recherche insensible."""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.lower()


def _layer_name_score(layer_name, q):
    """Score de pertinence entre la requete et le nom de la couche (plus bas = mieux).
    Permet de faire remonter une couche dont le nom correspond, ex: taper
    'parcelle' fait remonter la couche 'Parcelle agglo' en priorite."""
    norm_name = normalize_text(layer_name)
    if norm_name == q:
        return 0
    if norm_name.startswith(q):
        return 1
    tokens = norm_name.replace('-', ' ').replace('_', ' ').split()
    if any(t == q for t in tokens):
        return 2
    if any(t.startswith(q) for t in tokens):
        return 3
    if q in norm_name:
        return 4
    return 5


def _layer_fingerprint(layer):
    """Hash rapide pour detecter les changements sur une couche."""
    source = layer.source()
    feat_count = layer.featureCount()
    fields = [f.name() for f in layer.fields()]
    raw = f"{source}|{feat_count}|{'|'.join(fields)}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _get_cache_path(project_path):
    """Chemin du fichier cache a cote du .qgz/.qgs."""
    if not project_path:
        return None
    base = os.path.splitext(project_path)[0]
    return base + '_magic_search_cache.gz'


def _index_feature(feat, field_names, layer_index):
    """Indexe plusieurs champs d'une seule entité."""
    for fname in field_names:
        try:
            val = feat[fname]
        except Exception:
            continue
        if val is None or val == '':
            continue
        original = str(val)
        normalized = normalize_text(original)

        if fname not in layer_index['fields']:
            layer_index['fields'][fname] = {}

        field_values = layer_index['fields'][fname]
        if normalized not in field_values:
            field_values[normalized] = {
                'original': original,
                'fids': []
            }
        field_values[normalized]['fids'].append(feat.id())


class IndexManager(QObject):
    """Gestionnaire principal de l'index avec traitement incremental par champ."""

    SYNC_NEVER = 'never'
    SYNC_SYNCING = 'syncing'
    SYNC_COMPLETE = 'complete'

    indexing_started = pyqtSignal()
    indexing_progress = pyqtSignal(str)
    indexing_finished = pyqtSignal()
    layer_ready = pyqtSignal(str)
    sync_state_changed = pyqtSignal(str)  # 'never', 'syncing', 'complete'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._index = {}           # layer_id -> index data
        self._layers_config = {}   # config exclusions
        self._max_cache_mb = DEFAULT_MAX_CACHE_MB
        self._is_ready = False
        self._sync_state = self.SYNC_NEVER

        # File d'attente : liste de layer_id
        self._queue = []
        # Etat actuel de l'indexation
        self._current_layer_id = None
        self._current_iterator = None
        self._current_fields = []
        self._current_layer_data = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_next)

    @property
    def is_ready(self):
        return self._is_ready

    @property
    def sync_state(self):
        return self._sync_state

    def _set_sync_state(self, state):
        if self._sync_state != state:
            self._sync_state = state
            self.sync_state_changed.emit(state)

    def set_config(self, layers_config, max_cache_mb=None):
        self._layers_config = layers_config
        if max_cache_mb is not None:
            self._max_cache_mb = max_cache_mb

    def start_indexing(self):
        """Lance l'indexation. Charge le cache d'abord si disponible."""
        self.stop()
        self._is_ready = False

        project_path = QgsProject.instance().fileName()
        cache_path = _get_cache_path(project_path)

        # Tenter de charger le cache
        cached_index = self._load_cache(cache_path)

        project = QgsProject.instance()
        all_layers = project.mapLayers()
        self._queue = []

        for layer_id, layer in all_layers.items():
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                continue

            config = self._layers_config.get(layer_id, {})
            if config.get('excluded', False):
                continue

            if layer_id in cached_index:
                try:
                    current_fp = _layer_fingerprint(layer)
                    if cached_index[layer_id].get('fingerprint') == current_fp:
                        self._index[layer_id] = cached_index[layer_id]
                        self.layer_ready.emit(layer_id)
                        continue
                except Exception:
                    pass

            # A indexer
            self._queue.append(layer_id)

        # Nettoyer les couches supprimees du cache
        for lid in list(self._index.keys()):
            if lid not in all_layers:
                del self._index[lid]

        if not self._queue:
            self._is_ready = True
            self._set_sync_state(self.SYNC_COMPLETE)
            self.indexing_finished.emit()
            return

        self._set_sync_state(self.SYNC_SYNCING)
        self.indexing_started.emit()
        self._timer.start(TICK_MS)

    def _process_next(self):
        """Traite un lot d'entites de la couche actuelle."""
        if not self._current_iterator:
            if not self._queue:
                self._finalize()
                return

            # Nouvelle couche a traiter
            layer_id = self._queue.pop(0)
            project = QgsProject.instance()
            layer = project.mapLayer(layer_id)

            if not layer or not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                self._timer.start(TICK_MS)
                return

            config = self._layers_config.get(layer_id, {})
            excluded_fields = config.get('excluded_fields', [])
            self._current_fields = [
                f.name() for f in layer.fields()
                if f.name() not in excluded_fields
            ]

            if not self._current_fields:
                self._timer.start(TICK_MS)
                return

            self._current_layer_id = layer_id
            self._current_iterator = layer.getFeatures()
            self._current_layer_data = {
                'name': layer.name(),
                'fingerprint': _layer_fingerprint(layer),
                'fields': {}
            }
            QgsMessageLog.logMessage(f"Magic Search: Debut indexation {layer.name()}", TAG, Qgis.Info)

        # Process BATCH
        done = False
        count = 0
        while count < BATCH_SIZE:
            try:
                feat = next(self._current_iterator)
                _index_feature(feat, self._current_fields, self._current_layer_data)
                count += 1
            except StopIteration:
                done = True
                break
            except Exception as e:
                QgsMessageLog.logMessage(f"Erreur entité: {e}", TAG, Qgis.Warning)
                count += 1

        if done:
            self._index[self._current_layer_id] = self._current_layer_data
            self.layer_ready.emit(self._current_layer_id)
            QgsMessageLog.logMessage(f"Magic Search: Fin indexation {self._current_layer_data['name']}", TAG, Qgis.Info)
            self._current_iterator = None
            self._current_layer_id = None
            self._current_layer_data = None
        else:
            self.indexing_progress.emit(
                tr('status_progress', layer=self._current_layer_data['name'], count=count)
            )

        self._timer.start(TICK_MS)

    def _finalize(self):
        """Termine l'indexation et sauvegarde."""
        self._is_ready = True
        self._save_cache()
        self._set_sync_state(self.SYNC_COMPLETE)
        self.indexing_finished.emit()

    def stop(self):
        """Arrete le traitement en cours."""
        self._timer.stop()
        self._queue = []
        self._current_iterator = None
        self._current_layer_id = None
        self._current_layer_data = None
        # Si on stoppe sans index, on repasse en 'never'
        if not self._index:
            self._set_sync_state(self.SYNC_NEVER)

    def search(self, query, max_per_field=5):
        """Recherche dans l'index. Retourne les resultats groupes,
        tries par pertinence (nom de couche pertinent + qualite du match en premier)."""
        if not query or len(query) < 2:
            return []

        q = normalize_text(query).strip()
        results = []

        for layer_id, layer_data in self._index.items():
            layer_name = layer_data['name']
            layer_score = _layer_name_score(layer_name, q)
            for field_name, values in layer_data['fields'].items():
                matches = []
                for norm_val, val_data in values.items():
                    if q in norm_val:
                        matches.append({
                            'original': val_data['original'],
                            'normalized': norm_val,
                            'fids': val_data['fids'],
                            'layer_id': layer_id,
                            'layer_name': layer_name,
                            'field_name': field_name,
                        })
                if matches:
                    def sort_key(m):
                        nv = m['normalized']
                        if nv == q:
                            return 0
                        if nv.startswith(q):
                            return 1
                        return 2
                    matches.sort(key=sort_key)
                    results.append({
                        'layer_id': layer_id,
                        'layer_name': layer_name,
                        'field_name': field_name,
                        'matches': matches[:max_per_field],
                        'total_matches': len(matches),
                        'layer_score': layer_score,
                        'best_match_score': sort_key(matches[0]),
                    })

        results.sort(key=lambda r: (r['layer_score'], r['best_match_score'], -r['total_matches']))
        return results

    def reindex_layer(self, layer_id):
        """Reindexe une seule couche (apres ajout), via le meme traitement
        incremental par lots que l'indexation initiale (ne bloque pas l'UI)."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return

        config = self._layers_config.get(layer_id, {})
        if config.get('excluded', False):
            if layer_id in self._index:
                del self._index[layer_id]
            return

        if layer_id not in self._queue:
            self._queue.append(layer_id)

        if self._current_iterator is None and not self._timer.isActive():
            self._set_sync_state(self.SYNC_SYNCING)
            self.indexing_started.emit()
            self._timer.start(TICK_MS)

    def remove_layer(self, layer_id):
        if layer_id in self._index:
            del self._index[layer_id]
        if layer_id in self._queue:
            self._queue.remove(layer_id)
        if layer_id == self._current_layer_id:
            # La couche en cours d'indexation vient d'etre supprimee :
            # abandonner son iterateur pour ne pas boucler indefiniment
            # (next() sur un iterateur invalide ne leve pas forcement StopIteration).
            self._current_iterator = None
            self._current_layer_id = None
            self._current_layer_data = None
            self._current_fields = []

    # ---- Cache persistence ----

    def _save_cache(self):
        project_path = QgsProject.instance().fileName()
        cache_path = _get_cache_path(project_path)
        if not cache_path:
            return

        try:
            if HAS_MSGPACK:
                data = msgpack.packb(self._index, use_bin_type=True)
            else:
                data = json.dumps(self._index, ensure_ascii=False).encode('utf-8')

            compressed = gzip.compress(data, compresslevel=6)

            size_mb = len(compressed) / (1024 * 1024)
            if size_mb > self._max_cache_mb:
                QgsMessageLog.logMessage(
                    f"{TAG}: cache trop volumineux ({size_mb:.1f} Mo > {self._max_cache_mb} Mo), non sauvegarde.",
                    TAG, Qgis.Warning
                )
                return

            with open(cache_path, 'wb') as f:
                f.write(compressed)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur sauvegarde cache: {e}",
                TAG, Qgis.Warning
            )

    def _load_cache(self, cache_path):
        if not cache_path or not os.path.exists(cache_path):
            return {}
        try:
            with open(cache_path, 'rb') as f:
                compressed = f.read()
            data = gzip.decompress(compressed)

            if HAS_MSGPACK:
                try:
                    # raw=False permet d'obtenir des strings directement si possible
                    index = msgpack.unpackb(data, raw=False)
                except Exception:
                    index = json.loads(data.decode('utf-8'))
            else:
                index = json.loads(data.decode('utf-8'))

            # Si c'est du JSON ou msgpack avec raw=False, les clefs sont deja des str.
            # On ne sanitize que si on detecte des bytes dans les clefs du premier niveau.
            if index and isinstance(index, dict):
                first_key = next(iter(index.keys()), None)
                if isinstance(first_key, bytes):
                    return self._sanitize_keys(index)
            return index

        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur chargement cache: {e}",
                TAG, Qgis.Warning
            )
            return {}

    def _sanitize_keys(self, obj):
        """Convertit les clefs bytes en str (cas msgpack avec raw=True)."""
        if isinstance(obj, dict):
            return {
                (k.decode('utf-8') if isinstance(k, bytes) else k):
                self._sanitize_keys(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._sanitize_keys(i) for i in obj]
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        return obj
