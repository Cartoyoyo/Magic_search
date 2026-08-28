"""
Index Manager - Indexation incrementale des couches QGIS sur le thread principal.
Traitement par morceaux via QTimer (un champ par tick) pour ne jamais bloquer l'UI.
Cache : un conteneur binaire compresse par index, a cote du fichier projet.
"""

import io
import os
import sys
import lzma
import json
import time
import array
import struct
import hashlib
import unicodedata
from qgis.PyQt.QtCore import QTimer, pyqtSignal, QObject, QVariant
from qgis.core import QgsProject, QgsVectorLayer, QgsMessageLog, Qgis

from bisect import bisect_right as _bisect_right

from ..i18n import tr

DEFAULT_MAX_CACHE_MB = 50
CACHE_VERSION = 4

# Codec du cache. LZMA preset 3 : ~2,8x plus petit que gzip pour 0,3 s de
# chargement en plus sur un projet de 20 couches. Les presets plus bas sont
# a la fois plus gros ET plus lents a relire (moins d'octets a decompresser
# l'emporte sur le cout par octet) ; le preset 6 gagne encore 2 Mo mais gele
# l'interface ~10 s sur une grosse couche a la reindexation.
LZMA_PRESET = 3


def _compress(data):
    return lzma.compress(data, preset=LZMA_PRESET)


def _decompress(data):
    return lzma.decompress(data)
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


def _get_cache_dir(project_path):
    """Dossier de cache a cote du .qgz/.qgs : un fichier par couche.

    Le cache est eclate par couche pour que son chargement puisse etre
    incremental (une couche par tick). Un cache monolithique de plusieurs
    dizaines de Mo compresses represente des centaines de Mo a deserialiser
    d'un bloc, ce qui gele l'interface pendant plusieurs secondes.
    """
    if not project_path:
        return None
    return os.path.splitext(project_path)[0] + '_magic_search_cache'


def _get_legacy_cache_path(project_path):
    """Ancien cache monolithique, migre au premier chargement."""
    if not project_path:
        return None
    return os.path.splitext(project_path)[0] + '_magic_search_cache.gz'


def _index_key(fingerprint, excluded_fields, index_all_types=False):
    """Identifie un CONTENU d'index, pas une couche.

    Deux couches qui pointent la meme source, avec le meme nombre d'entites,
    les memes champs et les memes exclusions produisent exactement le meme
    index : elles partagent donc cette cle, et ne sont indexees, stockees et
    gardees en memoire qu'une seule fois. Les projets qui chargent plusieurs
    fois la meme table (copies, couches d'etiquettes) y gagnent directement.

    Inclure la configuration dans la cle a un second effet : changer les champs
    exclus ou l'option d'indexation des dates/decimales invalide le cache, ce
    que l'empreinte seule ne faisait pas.
    """
    raw = '%s|%s|%s' % (fingerprint, '|'.join(sorted(excluded_fields)),
                        int(bool(index_all_types)))
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _key_file(key):
    return key + '.idx'


# Types QGIS sans interet pour une recherche textuelle. Les dates sont
# exclues d'office ; les reels sont mis "en observation" (cf. _index_feature).
DATE_TYPES = (QVariant.Date, QVariant.DateTime, QVariant.Time)
REAL_TYPES = (QVariant.Double,)


def _classify_fields(layer, excluded_fields, index_all):
    """Retourne (champs a indexer, champs reels en observation).

    Un champ reel n'est pas exclu d'emblee : beaucoup de sources (shapefile,
    exports) typent en double des colonnes qui ne contiennent que des entiers,
    et ce sont souvent des champs metier qu'on cherche vraiment. On les indexe
    donc, quitte a les abandonner des qu'une vraie decimale apparait.
    """
    fields, watched = [], set()
    for f in layer.fields():
        name = f.name()
        if name in excluded_fields:
            continue
        try:
            ftype = f.type()
        except Exception:
            ftype = None
        if not index_all and ftype in DATE_TYPES:
            continue
        if not index_all and ftype in REAL_TYPES:
            watched.add(name)
        fields.append(name)
    return fields, watched


def _is_integral(val):
    """True si la valeur reelle ne porte pas de decimale (12.0 -> True)."""
    try:
        return float(val).is_integer()
    except (TypeError, ValueError, OverflowError):
        return False


SEP = '\x00'      # impossible a saisir au clavier : aucun faux positif
OFF = 'i'         # offsets 32 bits (les chaines restent bien sous 2 Go)
FID = 'q'         # les fid QGIS sont des entiers 64 bits


ARRAY_KEYS = ('starts', 'fids', 'fid_starts', 'orig_starts')


def _pack_index(name, columns):
    """Serialise un index : entete JSON, puis les tableaux bruts bout a bout.

    Les tableaux pesent l'essentiel de l'index (66 Mo contre 14 Mo de texte
    sur un projet reel). Les faire transiter par du base64 dans du JSON les
    gonflait d'un tiers et les rendait bien plus lents a relire, alors qu'ici
    array.frombytes() les reprend d'un seul bloc.

    Les entiers sont toujours ecrits en petit-boutiste, pour qu'un cache reste
    lisible si le projet change de machine.
    """
    blobs, meta, offset = [], {}, 0
    for field, col in columns.items():
        entry = {'hay': col['hay'], 'orig': col['orig'], 'arrays': {}}
        for k in ARRAY_KEYS:
            a = col[k]
            if a is None:
                entry['arrays'][k] = None
                continue
            if sys.byteorder == 'big':
                a = array.array(a.typecode, a)
                a.byteswap()
            raw = a.tobytes()
            blobs.append(raw)
            entry['arrays'][k] = [offset, len(raw), a.typecode]
            offset += len(raw)
        meta[field] = entry

    head = json.dumps({'name': name, 'fields': meta},
                      ensure_ascii=False).encode('utf-8')
    return b''.join([struct.pack('<I', len(head)), head] + blobs)


def _unpack_index(buf):
    """Inverse de _pack_index. Retourne (nom, colonnes)."""
    (head_len,) = struct.unpack('<I', buf[:4])
    head = json.loads(buf[4:4 + head_len].decode('utf-8'))
    body = memoryview(buf)[4 + head_len:]

    columns = {}
    for field, entry in head['fields'].items():
        col = {'hay': entry['hay'], 'orig': entry['orig']}
        for k in ARRAY_KEYS:
            spec = entry['arrays'].get(k)
            if spec is None:
                col[k] = None
                continue
            offset, length, typecode = spec
            a = array.array(typecode)
            a.frombytes(body[offset:offset + length])
            if sys.byteorder == 'big':
                a.byteswap()
            col[k] = a
        columns[field] = col
    return head.get('name'), columns


def _to_columnar(fields):
    """Fige le dict d'indexation en colonnes compactes.

    Le dict reste indispensable PENDANT le parcours (c'est lui qui dedoublonne
    les valeurs) ; on le convertit une fois la couche terminee, puis on le
    laisse partir. Les millions de petits objets Python (dicts, listes, int)
    deviennent deux chaines et trois tableaux C par champ.
    """
    columns = {}
    for field, values in fields.items():
        norms = list(values.keys())
        if not norms:
            continue

        starts, pos = [], 0
        for n in norms:
            starts.append(pos)
            pos += len(n) + 1
        starts.append(pos)          # sentinelle : fin de la derniere valeur

        originals = [values[n]['original'] for n in norms]
        same = all(o == n for o, n in zip(originals, norms))

        fids, fid_starts = [], []
        for n in norms:
            fid_starts.append(len(fids))
            fids.extend(values[n]['fids'])
        fid_starts.append(len(fids))

        col = {
            'hay': SEP.join(norms),
            'starts': array.array(OFF, starts),
            'fids': array.array(FID, fids),
            'fid_starts': array.array(OFF, fid_starts),
            'orig': None if same else SEP.join(originals),
            'orig_starts': None,
        }
        if not same:
            o_starts, pos = [], 0
            for o in originals:
                o_starts.append(pos)
                pos += len(o) + 1
            o_starts.append(pos)
            col['orig_starts'] = array.array(OFF, o_starts)
        columns[field] = col
    return columns


def _column_value(hay, starts, idx):
    return hay[starts[idx]:starts[idx + 1] - 1]


def _search_column(col, q, max_per_field):
    """Balaye une colonne. Retourne (meilleurs resultats, total)."""
    hay, starts = col['hay'], col['starts']
    hits, pos, last = [], 0, -1
    find = hay.find
    bisect = _bisect_right
    while True:
        i = find(q, pos)
        if i < 0:
            break
        idx = bisect(starts, i) - 1
        if idx != last and idx >= 0:
            # 0 = valeur exacte, 1 = commence par, 2 = contient
            if i == starts[idx]:
                score = 0 if starts[idx + 1] - 1 - i == len(q) else 1
            else:
                score = 2
            hits.append((score, idx))
            last = idx
        pos = i + 1

    if not hits:
        return [], 0

    total = len(hits)
    hits.sort()          # (score, idx) : exact, puis prefixe, puis contenu
    best = hits[:max_per_field]

    orig, orig_starts = col['orig'], col['orig_starts']
    fids, fid_starts = col['fids'], col['fid_starts']
    out = []
    for score, idx in best:
        norm = _column_value(hay, starts, idx)
        out.append((
            score,
            norm,
            norm if orig is None else _column_value(orig, orig_starts, idx),
            fids[fid_starts[idx]:fid_starts[idx + 1]].tolist(),
        ))
    return out, total


def _index_feature(feat, field_names, layer_index, watched=None):
    """Indexe plusieurs champs d'une seule entité.

    `watched` contient les champs reels encore en observation. Des qu'une
    valeur porte une decimale non nulle, le champ est abandonne et tout ce qui
    avait ete accumule pour lui est jete : on ne garde que les colonnes typees
    en double qui se revelent entieres de bout en bout.
    """
    # Un champ abandonne en cours de lot doit le rester jusqu'a ce que
    # l'appelant l'ote de field_names, sinon les entites suivantes du meme
    # lot le reindexeraient comme du texte.
    dropped = layer_index.setdefault('dropped', set())
    for fname in field_names:
        if fname in dropped:
            continue
        try:
            val = feat[fname]
        except Exception:
            continue
        if val is None or val == '':
            continue

        if watched and fname in watched:
            if not _is_integral(val):
                watched.discard(fname)
                layer_index['fields'].pop(fname, None)
                dropped.add(fname)
                continue
            # 12.0 se cherche en tapant "12", pas "12.0"
            original = str(int(float(val)))
        else:
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
        # Triage incremental (chargement cache + empreintes)
        self._pending = []
        self._manifest = None      # layer_id -> {'file', 'key', 'name'}
        self._cache_bytes = 0      # taille courante du dossier de cache
        self._keys = {}            # layer_id -> cle d'index
        self._by_key = {}          # cle d'index -> dict 'fields' partage
        self._t0 = None
        # Etat actuel de l'indexation
        self._current_layer_id = None
        self._current_iterator = None
        self._current_fields = []
        self._watched_fields = set()
        self._index_all_types = False
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

    def set_config(self, layers_config, max_cache_mb=None, index_all_types=None):
        self._layers_config = layers_config
        if max_cache_mb is not None:
            self._max_cache_mb = max_cache_mb
        if index_all_types is not None:
            self._index_all_types = bool(index_all_types)

    def is_running(self):
        """Une passe d'indexation est-elle en cours ?"""
        return bool(self._pending or self._queue or self._current_iterator)

    def start_indexing(self, force=False):
        """Lance l'indexation.

        Le chargement du cache et la verification des empreintes se font eux
        aussi de maniere incrementale : start_indexing() rend la main
        immediatement. C'est essentiel au demarrage et au rechargement du
        plugin, ou la lecture du cache (gunzip + deserialisation) et
        _layer_fingerprint() (featureCount() = un SELECT count(*) par couche
        PostGIS) coutent chacun plusieurs secondes.
        """
        if self.is_running() and not force:
            # Un second appel pendant une passe (rechargement du plugin,
            # signal de projet redondant) faisait repartir de zero et jetait
            # la couche en cours de parcours.
            QgsMessageLog.logMessage(
                f"{TAG}: indexation deja en cours, demande ignoree.", TAG, Qgis.Info
            )
            return

        self.stop()
        self._is_ready = False
        self._manifest = None
        self._keys = {}
        # _by_key est volontairement CONSERVE : une cle identifie un contenu
        # (source + entites + champs + config), jamais une couche. Ce qui est
        # deja en memoire reste donc valide apres un redemarrage force, et
        # n'est ni relu sur disque ni reconstruit.
        self._t0 = time.perf_counter()

        project = QgsProject.instance()
        all_layers = project.mapLayers()

        # Nettoyer les couches supprimees de l'index en memoire
        for lid in list(self._index.keys()):
            if lid not in all_layers:
                del self._index[lid]

        self._pending = [
            layer_id for layer_id, layer in all_layers.items()
            if isinstance(layer, QgsVectorLayer) and layer.isValid()
            and not self._layers_config.get(layer_id, {}).get('excluded', False)
        ]

        if not self._pending:
            self._is_ready = True
            self._set_sync_state(self.SYNC_COMPLETE)
            self.indexing_finished.emit()
            return

        self._set_sync_state(self.SYNC_SYNCING)
        self.indexing_started.emit()
        self._timer.start(0)

    def _triage_next(self):
        """Une etape de triage par tick : d'abord le manifeste, puis une couche.

        Chaque couche encore valide est rechargee depuis son propre fichier de
        cache, un fichier par tick : la deserialisation est ainsi etalee sur la
        boucle d'evenements au lieu de bloquer l'interface d'un seul coup.
        Retourne True tant que la phase de triage n'est pas terminee.
        """
        if not self._pending:
            return False

        # Etape 0 : manifeste (quelques Ko) + migration de l'ancien cache.
        if self._manifest is None:
            self._manifest = self._load_manifest()
            return True

        layer_id = self._pending.pop(0)
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is not None:
            key = self._compute_key(layer_id, layer)
            fields = self._by_key.get(key)

            # Deja chargee sous une autre couche du projet : rien a relire.
            if fields is None:
                entry = self._manifest.get(layer_id) or {}
                if key is not None and entry.get('key') == key:
                    cached = self._load_key_cache(key)
                    if cached:
                        fields = cached.get('fields')
                        if fields is not None:
                            self._by_key[key] = fields

            if fields is not None:
                self._attach(layer_id, layer.name(), key, fields)
            else:
                self._queue.append(layer_id)

        return bool(self._pending)

    def _compute_key(self, layer_id, layer):
        """Empreinte + exclusions configurees, memorisee pour la couche."""
        try:
            fingerprint = _layer_fingerprint(layer)
        except Exception:
            self._keys[layer_id] = None
            return None
        excluded = self._layers_config.get(layer_id, {}).get('excluded_fields', [])
        key = _index_key(fingerprint, excluded, self._index_all_types)
        self._keys[layer_id] = key
        return key

    def _attach(self, layer_id, layer_name, key, fields):
        """Rattache une couche a un index deja construit.

        Le dict 'fields' est PARTAGE, pas copie : c'est tout l'interet de la
        deduplication cote memoire. Seul le nom differe d'une couche a l'autre.
        """
        self._index[layer_id] = {
            'name': layer_name,
            'key': key,
            'fields': fields,
        }
        if self._manifest is not None and key is not None:
            self._manifest[layer_id] = {
                'file': _key_file(key),
                'key': key,
                'name': layer_name,
            }
        self.layer_ready.emit(layer_id)

    def _process_next(self):
        """Traite une etape de triage, ou un lot d'entites de la couche actuelle."""
        if self._triage_next():
            self._timer.start(0)
            return

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

            # Une couche jumelle a pu etre indexee entre-temps : on se
            # rattache a son index au lieu de tout reparcourir.
            key = self._keys.get(layer_id) or self._compute_key(layer_id, layer)
            fields = self._by_key.get(key)
            if fields is not None:
                self._attach(layer_id, layer.name(), key, fields)
                self._timer.start(0)
                return

            config = self._layers_config.get(layer_id, {})
            excluded_fields = config.get('excluded_fields', [])
            self._current_fields, self._watched_fields = _classify_fields(
                layer, excluded_fields, self._index_all_types)

            if not self._current_fields:
                self._timer.start(TICK_MS)
                return

            self._current_layer_id = layer_id
            self._current_iterator = layer.getFeatures()
            self._current_layer_data = {
                'name': layer.name(),
                'key': key,
                'fields': {}
            }
            QgsMessageLog.logMessage(f"Magic Search: Debut indexation {layer.name()}", TAG, Qgis.Info)

        # Process BATCH
        done = False
        count = 0
        while count < BATCH_SIZE:
            try:
                feat = next(self._current_iterator)
                _index_feature(feat, self._current_fields,
                               self._current_layer_data, self._watched_fields)
                count += 1
            except StopIteration:
                done = True
                break
            except Exception as e:
                QgsMessageLog.logMessage(f"Erreur entité: {e}", TAG, Qgis.Warning)
                count += 1

        # Champs reels demasques pendant ce lot : on cesse de les parcourir.
        dropped = self._current_layer_data.get('dropped')
        if dropped:
            self._current_fields = [f for f in self._current_fields
                                    if f not in dropped]
            QgsMessageLog.logMessage(
                f"{TAG}: champs decimaux ignores dans "
                f"{self._current_layer_data['name']}: {', '.join(sorted(dropped))}",
                TAG, Qgis.Info
            )
            dropped.clear()

        if done:
            layer_id = self._current_layer_id
            data = self._current_layer_data
            # Le dict d'indexation a fait son office (dedoublonnage) : on le
            # fige en colonnes et on laisse le ramasse-miettes reprendre la
            # centaine de Mo de petits objets qu'il occupait.
            data['fields'] = _to_columnar(data['fields'])
            data.pop('dropped', None)
            key = data.get('key')
            if key is not None:
                self._by_key[key] = data['fields']
            self._index[layer_id] = data
            self._save_key_cache(key, data)
            if self._manifest is not None and key is not None:
                self._manifest[layer_id] = {
                    'file': _key_file(key),
                    'key': key,
                    'name': data['name'],
                }
                self._write_manifest()
            self.layer_ready.emit(layer_id)
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
        # Ne garder en memoire que les index encore references par une couche.
        live = {d.get('key') for d in self._index.values()}
        self._by_key = {k: v for k, v in self._by_key.items() if k in live}
        self._prune_cache()
        if self._t0 is not None:
            QgsMessageLog.logMessage(
                f"{TAG}: indexation terminee en {time.perf_counter() - self._t0:.2f}s",
                TAG, Qgis.Info
            )
            self._t0 = None
        self._set_sync_state(self.SYNC_COMPLETE)
        self.indexing_finished.emit()

    def stop(self):
        """Arrete le traitement en cours."""
        self._timer.stop()
        self._queue = []
        self._pending = []
        self._manifest = None
        self._current_iterator = None
        self._current_layer_id = None
        self._current_layer_data = None
        # Si on stoppe sans index, on repasse en 'never'
        if not self._index:
            self._set_sync_state(self.SYNC_NEVER)

    def search(self, query, max_per_field=5):
        """Recherche dans l'index. Retourne les resultats groupes,
        tries par pertinence (nom de couche pertinent + qualite du match en premier).

        Le balayage est delegue a str.find sur les colonnes : c'est du code C,
        la ou l'ancienne version testait chaque valeur une par une en Python.
        La forme du resultat, elle, est inchangee.
        """
        if not query or len(query) < 2:
            return []

        q = normalize_text(query).strip()
        if not q:
            return []
        results = []

        for layer_id, layer_data in self._index.items():
            layer_name = layer_data['name']
            layer_score = _layer_name_score(layer_name, q)
            for field_name, col in layer_data['fields'].items():
                hits, total = _search_column(col, q, max_per_field)
                if not hits:
                    continue
                results.append({
                    'layer_id': layer_id,
                    'layer_name': layer_name,
                    'field_name': field_name,
                    'matches': [{
                        'original': original,
                        'normalized': norm,
                        'fids': fids,
                        'layer_id': layer_id,
                        'layer_name': layer_name,
                        'field_name': field_name,
                    } for _score, norm, original, fids in hits],
                    'total_matches': total,
                    'layer_score': layer_score,
                    'best_match_score': hits[0][0],
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
        if layer_id in self._pending:
            self._pending.remove(layer_id)
        if layer_id == self._current_layer_id:
            # La couche en cours d'indexation vient d'etre supprimee :
            # abandonner son iterateur pour ne pas boucler indefiniment
            # (next() sur un iterateur invalide ne leve pas forcement StopIteration).
            self._current_iterator = None
            self._current_layer_id = None
            self._current_layer_data = None
            self._current_fields = []

    # ---- Cache persistence ----
    # Un dossier "<projet>_magic_search_cache/" contenant :
    #   - manifest.json : {version, layers: {layer_id -> {file, key, name}}}
    #   - <cle>.gz : un index, partage par toutes les couches de meme cle
    # Les fichiers sont nommes d'apres le CONTENU (cf. _index_key) et non
    # d'apres la couche : trois couches identiques ecrivent un seul fichier.

    def _cache_dir(self):
        return _get_cache_dir(QgsProject.instance().fileName())

    def _load_manifest(self):
        """Charge le manifeste. Un manifeste d'une autre version est ignore et
        son dossier repart de zero : plus simple et plus sur que d'essayer de
        convertir un format d'index qui a change."""
        cache_dir = self._cache_dir()
        if not cache_dir:
            self._cache_bytes = 0
            return {}

        self._drop_legacy_cache()

        manifest_path = os.path.join(cache_dir, 'manifest.json')
        if not os.path.exists(manifest_path):
            self._cache_bytes = self._dir_size(cache_dir)
            return {}

        layers = {}
        try:
            with io.open(manifest_path, encoding='utf-8') as f:
                manifest = json.load(f)
            if isinstance(manifest, dict) and manifest.get('version') == CACHE_VERSION:
                layers = manifest.get('layers') or {}
                if not isinstance(layers, dict):
                    layers = {}
            else:
                QgsMessageLog.logMessage(
                    f"{TAG}: cache d'une version anterieure, reconstruction.",
                    TAG, Qgis.Info
                )
                self._clear_cache_dir(cache_dir)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: manifeste de cache illisible ({e}), reconstruction.",
                TAG, Qgis.Warning
            )
            self._clear_cache_dir(cache_dir)

        self._cache_bytes = self._dir_size(cache_dir)
        return layers

    def _load_key_cache(self, key):
        """Lit un index par sa cle de contenu. None si absent/illisible."""
        cache_dir = self._cache_dir()
        if not cache_dir or not key:
            return None
        path = os.path.join(cache_dir, _key_file(key))
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'rb') as f:
                name, columns = _unpack_index(_decompress(f.read()))
            return {'name': name, 'fields': columns}
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur chargement cache: {e}", TAG, Qgis.Warning
            )
            return None

    def _save_key_cache(self, key, layer_data):
        """Ecrit un index des qu'il est construit. Si une couche jumelle l'a
        deja ecrit, il n'y a rien a refaire."""
        cache_dir = self._cache_dir()
        if not cache_dir or not key:
            return
        if self._manifest is None:
            self._manifest = self._load_manifest()

        path = os.path.join(cache_dir, _key_file(key))
        if os.path.exists(path):
            return

        try:
            if not os.path.isdir(cache_dir):
                os.makedirs(cache_dir)

            compressed = _compress(_pack_index(layer_data.get('name'),
                                                layer_data['fields']))

            projected = self._cache_bytes + len(compressed)
            if projected > self._max_cache_mb * 1024 * 1024:
                QgsMessageLog.logMessage(
                    f"{TAG}: plafond de cache atteint "
                    f"({projected / 1048576:.1f} Mo > {self._max_cache_mb} Mo), "
                    f"index non mis en cache: {layer_data.get('name')}",
                    TAG, Qgis.Warning
                )
                return

            with open(path, 'wb') as f:
                f.write(compressed)
            self._cache_bytes = projected

        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur sauvegarde cache: {e}", TAG, Qgis.Warning
            )

    def _write_manifest(self):
        cache_dir = self._cache_dir()
        if not cache_dir or self._manifest is None:
            return
        try:
            if not os.path.isdir(cache_dir):
                os.makedirs(cache_dir)
            with io.open(os.path.join(cache_dir, 'manifest.json'),
                         'w', encoding='utf-8') as f:
                json.dump({'version': CACHE_VERSION, 'layers': self._manifest},
                          f, ensure_ascii=False)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur ecriture manifeste: {e}", TAG, Qgis.Warning
            )

    def _prune_cache(self):
        """Supprime les index qu'aucune couche du projet ne reference plus."""
        cache_dir = self._cache_dir()
        if not cache_dir or not os.path.isdir(cache_dir) or self._manifest is None:
            return
        try:
            for layer_id in list(self._manifest.keys()):
                if layer_id not in self._index:
                    del self._manifest[layer_id]

            # Un fichier reste tant qu'AU MOINS une couche le reference.
            keep = {'manifest.json'}
            for entry in self._manifest.values():
                if isinstance(entry, dict) and entry.get('file'):
                    keep.add(entry['file'])
            for name in os.listdir(cache_dir):
                if name not in keep:
                    orphan = os.path.join(cache_dir, name)
                    if os.path.isfile(orphan):
                        self._cache_bytes -= os.path.getsize(orphan)
                        os.remove(orphan)

            self._write_manifest()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur nettoyage cache: {e}", TAG, Qgis.Warning
            )

    @staticmethod
    def _drop_legacy_cache():
        """Supprime le cache monolithique des versions precedentes."""
        legacy = _get_legacy_cache_path(QgsProject.instance().fileName())
        if not legacy or not os.path.exists(legacy):
            return
        try:
            os.remove(legacy)
            QgsMessageLog.logMessage(
                f"{TAG}: ancien cache monolithique supprime.", TAG, Qgis.Info
            )
        except Exception:
            pass

    @staticmethod
    def _clear_cache_dir(cache_dir):
        try:
            for name in os.listdir(cache_dir):
                full = os.path.join(cache_dir, name)
                if os.path.isfile(full):
                    os.remove(full)
        except Exception:
            pass

    @staticmethod
    def _dir_size(path):
        total = 0
        try:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isfile(full):
                    total += os.path.getsize(full)
        except Exception:
            pass
        return total
