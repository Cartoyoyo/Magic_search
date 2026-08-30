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
from qgis.PyQt.QtCore import QTimer, pyqtSignal, QObject, QMetaType
from qgis.core import (QgsProject, QgsVectorLayer, QgsMessageLog, Qgis,
                       QgsFeatureRequest)

from bisect import bisect_right as _bisect_right

from ..i18n import tr

DEFAULT_MAX_CACHE_MB = 50
CACHE_VERSION = 4

# Codec du cache. LZMA preset 3. Le preset 0 a ete essaye : sur un index
# synthetique il ecrit 5,5x plus vite pour un fichier 21 % plus petit, mais
# sur un vrai projet le gain n'a ete que de 4 s sur 60 s d'indexation --
# l'ecriture du cache n'est pas le poste dominant. Le preset 3 est donc
# conserve pour sa taille sur des donnees reelles.
#
# Le preset ne concerne que l'ecriture : les proprietes du filtre voyagent
# dans le flux .xz et lzma.decompress relit n'importe quel preset, donc en
# changer n'invalide aucun cache et ne demande pas de bump de CACHE_VERSION.
LZMA_PRESET = 3


def _compress(data):
    return lzma.compress(data, preset=LZMA_PRESET)


def _decompress(data):
    return lzma.decompress(data)
TAG = 'Magic Search'

# Un tick d'indexation travaille pendant BUDGET_MS puis rend la main a la
# boucle d'evenements, au lieu de traiter un nombre fixe d'entites. Le lot
# fixe avait les deux defauts a la fois : 2000 entites sur une couche a huit
# champs bloquaient deja l'interface ~70 ms, et le delai qui suivait ajoutait
# 10 ms de temps mort par lot (10 s sur deux millions d'entites). Le budget
# borne la latence ET supprime l'attente, quel que soit le nombre de champs
# ou le cout du fournisseur de donnees.
BUDGET_MS = 30
BUDGET_S = BUDGET_MS / 1000.0

# Le lot est lu puis indexe champ par champ (cf. _index_batch), il faut donc
# decider a l'avance combien d'entites lire. Sa taille s'ajuste au debit
# observe au tick precedent pour tenir dans BUDGET_MS : elle depend du
# fournisseur, du nombre de champs et de la longueur des valeurs, aucune
# constante ne conviendrait a tous les cas.
BATCH_START = 1000
BATCH_MIN = 100
BATCH_MAX = 50000


def _fmt(n):
    """Entier avec separateur de milliers, pour le journal."""
    return '{:,}'.format(int(n)).replace(',', ' ')


def _rate(n, seconds):
    """Debit formate (n par seconde), ou '-' si la duree est nulle."""
    return _fmt(n / seconds) if seconds > 0 else '-'


# Journal d'indexation ecrit dans le dossier de cache du projet, a cote des
# index. Le panneau de journal de QGIS se vide a chaque session ; ce fichier
# garde les passes precedentes, ce qui permet de comparer un avant et un
# apres. Il suit le projet, comme le cache.
LOG_FILE = 'indexation.log'
LOG_MAX_BYTES = 1024 * 1024   # au-dela, la passe suivante repart d'un fichier vide

# Drapeau "sans geometrie" : Qgis.FeatureRequestFlag n'apparait qu'en QGIS 3.36,
# QgsFeatureRequest.Flag existe depuis toujours et reste accessible sous Qt 6.
# Les deux formes sont cadrees : la forme nue QgsFeatureRequest.NoGeometry est
# signalee par le verificateur Qt6 du depot et disparait sous QGIS 4.
try:
    NO_GEOMETRY = Qgis.FeatureRequestFlag.NoGeometry
except AttributeError:
    NO_GEOMETRY = QgsFeatureRequest.Flag.NoGeometry


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
    """Hash rapide pour detecter les changements sur une couche.

    blake2b tronque a 16 octets : meme longueur qu'un MD5 (32 caracteres hex),
    plus rapide, et sans le signalement B324 de Bandit qui bloque la
    publication sur plugins.qgis.org. Ce n'est pas un hash de securite.
    """
    source = layer.source()
    feat_count = layer.featureCount()
    fields = [f.name() for f in layer.fields()]
    raw = f"{source}|{feat_count}|{'|'.join(fields)}"
    return hashlib.blake2b(raw.encode('utf-8'), digest_size=16).hexdigest()


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
    return hashlib.blake2b(raw.encode('utf-8'), digest_size=16).hexdigest()


def _key_file(key):
    return key + '.idx'


# Types QGIS sans interet pour une recherche textuelle. Les dates sont
# exclues d'office ; les reels sont mis "en observation" (cf. _index_feature).
# On compare des entiers : QgsField.type() renvoie un QVariant.Type sous
# QGIS 3 et un QMetaType.Type sous QGIS 4, mais les deux portent les memes
# valeurs numeriques.
DATE_TYPES = frozenset((int(QMetaType.Type.QDate),
                        int(QMetaType.Type.QDateTime),
                        int(QMetaType.Type.QTime)))
REAL_TYPES = frozenset((int(QMetaType.Type.Double),))


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
            ftype = int(f.type())
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


def _index_batch(feats, field_names, layer_index, watched=None, stats=None):
    """Indexe un lot d'entites, un champ apres l'autre.

    Parcourir le lot une fois par champ plutot qu'une fois par entite sort de
    la boucle interne tout ce qui ne depend que du champ : le dict de valeurs
    et le test d'observation. Mesure sur 250 000 entites et 8 champs :
    6,17 s contre 7,18 s pour l'ancien parcours (x1,16), chronometrage inclus.

    C'est aussi ce qui rend le chronometrage par champ gratuit : une lecture
    d'horloge par champ et par lot, la ou chronometrer a la valeur coutait
    30 % (mesure). `stats` est un dict {champ: [nb_valeurs, secondes]} rempli
    au passage, ou None pour ne rien mesurer.

    L'index produit est strictement identique a celui de l'ancien parcours :
    les entites restent vues dans l'ordre pour chaque champ, donc l'ordre
    d'insertion des valeurs comme celui des fid sont inchanges.

    `watched` contient les champs reels encore en observation. Des qu'une
    valeur porte une decimale non nulle, le champ est abandonne et tout ce qui
    avait ete accumule pour lui est jete : on ne garde que les colonnes typees
    en double qui se revelent entieres de bout en bout.
    """
    if not feats:
        return
    # Un champ abandonne en cours de lot doit le rester jusqu'a ce que
    # l'appelant l'ote de field_names, sinon le lot suivant le reindexerait
    # comme du texte.
    dropped = layer_index.setdefault('dropped', set())
    all_fields = layer_index['fields']
    perf_counter = time.perf_counter

    for fname in field_names:
        if fname in dropped:
            continue
        t0 = perf_counter()
        field_values = all_fields.get(fname)
        if field_values is None:
            field_values = all_fields[fname] = {}
        is_watched = watched is not None and fname in watched
        count = 0

        # Un champ qui explose ne doit pas emporter le reste du lot. Le try
        # est ici et non autour de chaque valeur : au lot il est gratuit.
        try:
            for feat in feats:
                try:
                    val = feat[fname]
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if val is None or val == '':
                    continue

                if is_watched:
                    if not _is_integral(val):
                        watched.discard(fname)
                        all_fields.pop(fname, None)
                        dropped.add(fname)
                        break
                    # 12.0 se cherche en tapant "12", pas "12.0"
                    original = str(int(float(val)))
                else:
                    original = str(val)
                normalized = normalize_text(original)

                slot = field_values.get(normalized)
                if slot is None:
                    field_values[normalized] = {'original': original,
                                                'fids': [feat.id()]}
                else:
                    slot['fids'].append(feat.id())
                count += 1
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur d'indexation du champ {fname}: {e}",
                TAG, Qgis.MessageLevel.Warning
            )

        # Le dict a ete cree d'avance : le retirer s'il n'a rien recu, pour
        # qu'un champ entierement vide reste absent de l'index comme avant.
        if not field_values and fname in all_fields:
            del all_fields[fname]

        if stats is not None:
            entry = stats.get(fname)
            if entry is not None:
                entry[0] += count
                entry[1] += perf_counter() - t0


def _index_feature(feat, field_names, layer_index, watched=None):
    """Indexe une seule entite. Le parcours d'une couche passe par
    _index_batch ; cette forme reste pour les appels unitaires."""
    _index_batch((feat,), field_names, layer_index, watched)


class IndexManager(QObject):
    """Gestionnaire principal de l'index avec traitement incremental par champ."""

    SYNC_NEVER = 'never'
    SYNC_PARTIAL = 'partial'
    SYNC_SYNCING = 'syncing'
    SYNC_COMPLETE = 'complete'

    # Defaut de classe : search() doit repondre meme sur une instance montee
    # sans __init__ (c'est ce que font les tests unitaires).
    _search_all_layers = False
    _skipped = frozenset()

    indexing_started = pyqtSignal()
    indexing_progress = pyqtSignal(str)
    indexing_finished = pyqtSignal()
    layer_ready = pyqtSignal(str)
    sync_state_changed = pyqtSignal(str)  # 'never', 'partial', 'syncing', 'complete'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._index = {}           # layer_id -> index data
        self._layers_config = {}   # config exclusions
        self._max_cache_mb = DEFAULT_MAX_CACHE_MB
        self._is_ready = False
        self._sync_state = self.SYNC_NEVER
        # Couches examinees mais volontairement laissees hors de l'index
        # (source illisible, aucun champ indexable). Sans cela elles
        # compteraient eternellement comme "manquantes" et le bouton de
        # synchronisation resterait orange apres une passe complete.
        self._skipped = set()

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
        self._current_count = 0
        self._current_t0 = None
        self._current_read_s = 0.0
        self._current_index_s = 0.0
        self._current_stats = {}     # champ -> [nb_valeurs, secondes]
        self._batch_size = BATCH_START
        self._reset_session()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._process_next)

    def _reset_session(self):
        """Remet a zero les cumuls de la passe (ligne de synthese finale)."""
        self._session_layers = 0      # couches reellement parcourues
        self._session_attached = 0    # couches rattachees a un index existant
        self._session_features = 0
        self._session_values = 0
        self._session_read_s = 0.0
        self._session_index_s = 0.0
        self._session_cols_s = 0.0
        self._session_cache_s = 0.0
        self._log_warned = False

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

    def clear_index(self):
        """Oublie l'index en memoire (changement de projet).

        Les identifiants de couche appartiennent a un projet : garder l'index
        du projet precedent n'a aucun sens. Le cache disque, lui, est conserve
        (il est range par projet) : la prochaine synchronisation demandee par
        l'utilisateur le relira au lieu de tout reparcourir.
        """
        self.stop()
        self._index = {}
        self._by_key = {}
        self._keys = {}
        self._skipped = set()
        self._is_ready = False

    def missing_layers(self):
        """Couches indexables du projet qui ne sont pas (encore) dans l'index.

        Test volontairement bon marche (type, validite, exclusion) : il est
        appele a chaque changement de couche, il ne doit jamais interroger la
        source de donnees.
        """
        project = QgsProject.instance()
        return [
            layer_id for layer_id, layer in project.mapLayers().items()
            if self._is_indexable(layer_id, layer)
            and layer_id not in self._index
            and layer_id not in self._skipped
        ]

    def refresh_sync_state(self):
        """Recalcule l'etat de synchronisation a partir du projet courant.

        L'indexation ne demarrant plus toute seule, c'est cet etat qui dit a
        l'utilisateur ce que vaut son index : rien du tout ('never'), une
        partie seulement ('partial'), ou tout ('complete').
        """
        if self.is_running():
            self._set_sync_state(self.SYNC_SYNCING)
            return self._sync_state

        missing = self.missing_layers()
        if not self._index:
            state = self.SYNC_NEVER if missing else self.SYNC_COMPLETE
        elif missing:
            state = self.SYNC_PARTIAL
        else:
            state = self.SYNC_COMPLETE
        self._set_sync_state(state)
        return state

    def set_config(self, layers_config, max_cache_mb=None, index_all_types=None,
                   search_all_layers=None):
        self._layers_config = layers_config
        if max_cache_mb is not None:
            self._max_cache_mb = max_cache_mb
        if index_all_types is not None:
            self._index_all_types = bool(index_all_types)
        if search_all_layers is not None:
            self._search_all_layers = bool(search_all_layers)

    def is_running(self):
        """Une passe d'indexation est-elle en cours ?"""
        return bool(self._pending or self._queue or self._current_iterator)

    def _visible_layer_ids(self):
        """Ids des couches cochees dans l'arbre des couches.

        checkedLayers() suit l'etat reel de l'arbre : decocher un groupe
        decoche ses enfants, donc une couche rangee dans un groupe masque
        n'apparait pas ici. Retourne None si l'arbre est indisponible, ce qui
        vaut "pas de filtre" plutot que "aucune couche".

        Appele a chaque recherche : l'arbre est en memoire, le cout est
        negligeable devant le balayage des colonnes, et le filtre suit donc
        les cases cochees sans la moindre reindexation.
        """
        try:
            root = QgsProject.instance().layerTreeRoot()
            return {layer.id() for layer in root.checkedLayers() if layer}
        except Exception:
            return None

    def _is_indexable(self, layer_id, layer):
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return False
        if self._layers_config.get(layer_id, {}).get('excluded', False):
            return False
        return True

    def _purge_all(self):
        """Efface le cache disque du projet et vide les index en memoire.

        Sans cela, "Reindexer maintenant" se contente de relire ce qui existe
        deja : _by_key est conserve d'un demarrage a l'autre et les fichiers
        du dossier de cache sont reutilises des que l'empreinte concorde.
        """
        cache_dir = self._cache_dir()
        if cache_dir and os.path.isdir(cache_dir):
            self._clear_cache_dir(cache_dir)
        self._drop_legacy_cache()
        self._by_key = {}
        self._index = {}
        self._cache_bytes = 0
        QgsMessageLog.logMessage(
            f"{TAG}: reindexation complete demandee, cache efface.",
            TAG, Qgis.MessageLevel.Info
        )

    def start_indexing(self, force=False, purge=False):
        """Lance l'indexation.

        purge=True repart de zero : les fichiers de cache du projet sont
        effacies et les index gardes en memoire sont jetes, de sorte que
        chaque couche est reellement reparcourue. C'est ce que demande le
        bouton "Reindexer maintenant" ; l'ouverture d'un projet, elle,
        conserve le cache (purge=False).

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
                f"{TAG}: indexation deja en cours, demande ignoree.", TAG, Qgis.MessageLevel.Info
            )
            return

        self.stop()
        if purge:
            self._purge_all()
        self._is_ready = False
        self._manifest = None
        self._keys = {}
        self._skipped = set()
        # _by_key est volontairement CONSERVE : une cle identifie un contenu
        # (source + entites + champs + config), jamais une couche. Ce qui est
        # deja en memoire reste donc valide apres un redemarrage force, et
        # n'est ni relu sur disque ni reconstruit.
        self._t0 = time.perf_counter()
        self._reset_session()
        # Ecrit apres _purge_all() : l'entete d'une reindexation complete
        # survit ainsi a l'effacement du cache.
        self._append_log(
            ['', '=' * 78,
             'Magic Search - passe du %s'
             % time.strftime('%Y-%m-%d %H:%M:%S')],
            rotate=True
        )

        project = QgsProject.instance()
        all_layers = project.mapLayers()

        # Nettoyer les couches supprimees de l'index en memoire
        for lid in list(self._index.keys()):
            if lid not in all_layers:
                del self._index[lid]

        # Toutes les couches non exclues sont indexees, visibles ou non : la
        # visibilite se filtre a la recherche (cf. search), ou elle est
        # gratuite et suit l'arbre en temps reel. Indexer sur ce critere
        # obligerait a tout reparcourir a chaque case cochee.
        self._pending = [
            layer_id for layer_id, layer in all_layers.items()
            if self._is_indexable(layer_id, layer)
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
        self._session_attached += 1
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
                self._skipped.add(layer_id)
                self._timer.start(0)
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
                # Aucun champ indexable : rien a stocker, mais la couche a bien
                # ete traitee (elle ne doit pas rester comptee comme manquante).
                self._skipped.add(layer_id)
                self._timer.start(0)
                return

            self._current_layer_id = layer_id
            self._current_count = 0
            # Debut du scan de la couche : c'est cette horloge, comparee a
            # celle de la fin, qui donne les entites/s du journal.
            self._current_t0 = time.perf_counter()
            self._current_read_s = 0.0
            self._current_index_s = 0.0
            self._current_stats = {f: [0, 0.0] for f in self._current_fields}
            self._batch_size = BATCH_START
            # Ne demander au fournisseur que ce que l'index consomme. La
            # geometrie n'est jamais lue ici (seuls les fid sont stockes) et
            # les champs exclus, dates ou decimaux ont deja ete ecartes par
            # _classify_fields. Sur PostGIS cela retire la geometrie et les
            # colonnes inutiles du SELECT ; sur un fichier cela evite de
            # construire un QgsGeometry par entite.
            #
            # Un champ reel demasque en cours de route sort de
            # _current_fields mais reste dans la requete : sans consequence,
            # _index_feature l'ignore via 'dropped'.
            request = (QgsFeatureRequest()
                       .setFlags(NO_GEOMETRY)
                       .setSubsetOfAttributes(self._current_fields,
                                              layer.fields()))
            self._current_iterator = layer.getFeatures(request)
            self._current_layer_data = {
                'name': layer.name(),
                'key': key,
                'fields': {}
            }
            QgsMessageLog.logMessage(f"Magic Search: Debut indexation {layer.name()}", TAG, Qgis.MessageLevel.Info)

        # Un tick = lecture d'un lot d'entites, puis indexation de ce lot
        # champ par champ. Les deux phases sont chronometrees separement :
        # savoir si le temps part dans le fournisseur de donnees ou dans la
        # normalisation est ce qui dit ou optimiser.
        perf_counter = time.perf_counter
        t_start = perf_counter()
        iterator = self._current_iterator
        feats = []
        append = feats.append
        done = False
        for _ in range(self._batch_size):
            try:
                append(next(iterator))
            except StopIteration:
                done = True
                break
            except Exception as e:
                QgsMessageLog.logMessage(f"Erreur entité: {e}", TAG, Qgis.MessageLevel.Warning)
        t_read = perf_counter()

        _index_batch(feats, self._current_fields, self._current_layer_data,
                     self._watched_fields, self._current_stats)
        t_end = perf_counter()

        self._current_count += len(feats)
        self._current_read_s += t_read - t_start
        self._current_index_s += t_end - t_read

        # Viser BUDGET_S au prochain tick. La moyenne avec la taille courante
        # amortit les a-coups (un lot ralenti par une requete reseau ne doit
        # pas faire s'effondrer le suivant).
        elapsed = t_end - t_start
        if feats and elapsed > 0:
            target = len(feats) * BUDGET_S / elapsed
            self._batch_size = int(max(BATCH_MIN, min(
                BATCH_MAX, (self._batch_size + target) / 2)))

        # Champs reels demasques pendant ce lot : on cesse de les parcourir.
        dropped = self._current_layer_data.get('dropped')
        if dropped:
            self._current_fields = [f for f in self._current_fields
                                    if f not in dropped]
            QgsMessageLog.logMessage(
                f"{TAG}: champs decimaux ignores dans "
                f"{self._current_layer_data['name']}: {', '.join(sorted(dropped))}",
                TAG, Qgis.MessageLevel.Info
            )
            dropped.clear()

        if done:
            layer_id = self._current_layer_id
            data = self._current_layer_data
            # Le nombre de valeurs distinctes se lit sur les dicts, avant que
            # _to_columnar ne les remplace par des colonnes.
            uniques = {f: len(v) for f, v in data['fields'].items()}
            # Le dict d'indexation a fait son office (dedoublonnage) : on le
            # fige en colonnes et on laisse le ramasse-miettes reprendre la
            # centaine de Mo de petits objets qu'il occupait.
            t_cols = time.perf_counter()
            data['fields'] = _to_columnar(data['fields'])
            data.pop('dropped', None)
            key = data.get('key')
            if key is not None:
                self._by_key[key] = data['fields']
            self._index[layer_id] = data
            t_cache = time.perf_counter()
            self._save_key_cache(key, data)
            t_done = time.perf_counter()
            # Le rapport est emis ici, et non avant, pour pouvoir imputer la
            # mise en colonnes et la compression du cache : sur une grosse
            # couche elles pesent plus que l'indexation elle-meme.
            self._log_layer_report(data['name'], uniques,
                                   t_cache - t_cols, t_done - t_cache)
            if self._manifest is not None and key is not None:
                self._manifest[layer_id] = {
                    'file': _key_file(key),
                    'key': key,
                    'name': data['name'],
                }
                self._write_manifest()
            self.layer_ready.emit(layer_id)
            self._current_iterator = None
            self._current_layer_id = None
            self._current_layer_data = None
            self._current_count = 0
        else:
            # Total courant de la couche : le nombre d'entites traitees par
            # tick varie desormais avec le budget de temps, l'afficher ne
            # voudrait plus rien dire.
            self.indexing_progress.emit(
                tr('status_progress', layer=self._current_layer_data['name'],
                   count=self._current_count)
            )

        self._timer.start(0)

    def _log_path(self):
        """Chemin du journal, ou None si le projet n'est pas enregistre."""
        cache_dir = self._cache_dir()
        return os.path.join(cache_dir, LOG_FILE) if cache_dir else None

    def _append_log(self, lines, rotate=False):
        """Ajoute des lignes au journal du projet.

        Toute erreur est avalee (avec un avertissement, une seule fois par
        passe) : un journal illisible ne doit jamais interrompre une
        indexation, ni noyer le panneau de messages.
        """
        path = self._log_path()
        if not path:
            return                       # projet jamais enregistre
        try:
            directory = os.path.dirname(path)
            if not os.path.isdir(directory):
                os.makedirs(directory)
            if (rotate and os.path.exists(path)
                    and os.path.getsize(path) > LOG_MAX_BYTES):
                os.remove(path)
            with io.open(path, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            if not self._log_warned:
                self._log_warned = True
                QgsMessageLog.logMessage(
                    "%s: journal non ecrit dans %s (%s)" % (TAG, path, e),
                    TAG, Qgis.MessageLevel.Warning
                )

    def _log_layer_report(self, layer_name, uniques, cols_s=0.0, cache_s=0.0):
        """Ecrit dans le journal ce que la couche vient de couter.

        Un seul message multiligne : le panneau de journal horodate chaque
        message, un rapport eclate en dix messages serait entrelace avec ceux
        des autres couches et illisible.

        Le debit en entites/s se lit sur l'horloge de la couche (debut du
        scan -> maintenant). Il inclut donc les allers-retours par la boucle
        d'evenements entre deux lots : c'est le temps que l'utilisateur a
        reellement attendu, pas seulement celui passe a travailler.
        """
        stats = self._current_stats or {}
        values = sum(s[0] for s in stats.values())
        feats = self._current_count
        wall = (time.perf_counter() - self._current_t0
                if self._current_t0 is not None else 0.0)
        work = self._current_read_s + self._current_index_s

        lines = [
            "[%s] %s entites en %.2f s -> %s entites/s"
            % (layer_name, _fmt(feats), wall, _rate(feats, wall)),
            "    valeurs : %s indexees, %s uniques -> %s valeurs/s"
            % (_fmt(values), _fmt(sum(uniques.values())), _rate(values, work)),
            "    temps   : lecture %.2f s + indexation %.2f s "
            "+ colonnes %.2f s + cache %.2f s"
            % (self._current_read_s, self._current_index_s, cols_s, cache_s),
        ]
        if stats:
            lines.append("    champs  : (part du temps d'indexation)")
            total_s = self._current_index_s
            for fname, (n, seconds) in sorted(stats.items(),
                                              key=lambda kv: -kv[1][1]):
                share = (seconds / total_s * 100) if total_s > 0 else 0.0
                lines.append(
                    "      %-28s %11s val. %11s uniq. %7.2f s %5.1f %% "
                    "%11s val/s"
                    % (fname[:28], _fmt(n), _fmt(uniques.get(fname, 0)),
                       seconds, share, _rate(n, seconds)))

        QgsMessageLog.logMessage("\n".join(lines), TAG, Qgis.MessageLevel.Info)
        self._append_log(['[%s] %s' % (time.strftime('%H:%M:%S'), lines[0])]
                         + lines[1:])

        self._session_layers += 1
        self._session_features += feats
        self._session_values += values
        self._session_read_s += self._current_read_s
        self._session_index_s += self._current_index_s
        self._session_cols_s += cols_s
        self._session_cache_s += cache_s

    def _finalize(self):
        """Termine l'indexation et sauvegarde."""
        self._is_ready = True
        # Ne garder en memoire que les index encore references par une couche.
        live = {d.get('key') for d in self._index.values()}
        self._by_key = {k: v for k, v in self._by_key.items() if k in live}
        self._prune_cache()
        if self._t0 is not None:
            wall = time.perf_counter() - self._t0
            work = self._session_read_s + self._session_index_s
            summary = (
                "indexation terminee en %.2f s | %d couche(s) parcourue(s), "
                "%d rattachee(s) a un index existant\n"
                "    %s entites, %s valeurs -> %s entites/s, %s valeurs/s\n"
                "    temps : lecture %.2f s + indexation %.2f s "
                "+ colonnes %.2f s + cache %.2f s ; le reste va au triage, "
                "aux empreintes et a la relecture du cache"
                % (wall, self._session_layers, self._session_attached,
                   _fmt(self._session_features), _fmt(self._session_values),
                   _rate(self._session_features, work),
                   _rate(self._session_values, work),
                   self._session_read_s, self._session_index_s,
                   self._session_cols_s, self._session_cache_s))
            QgsMessageLog.logMessage(summary, TAG, Qgis.MessageLevel.Info)
            self._append_log(['[%s] %s' % (time.strftime('%H:%M:%S'), summary)])
            self._t0 = None
        self.refresh_sync_state()
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
        self._current_count = 0
        self._current_stats = {}
        self._current_t0 = None
        # Une passe interrompue laisse un index partiel : l'etat le dit.
        self.refresh_sync_state()

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

        # Par defaut on ne repond que sur les couches cochees dans QGIS :
        # c'est ce que l'utilisateur a sous les yeux. L'index, lui, reste
        # complet, donc recocher une couche la rend cherchable aussitot.
        visible_ids = None if self._search_all_layers else self._visible_layer_ids()

        for layer_id, layer_data in self._index.items():
            if visible_ids is not None and layer_id not in visible_ids:
                continue
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

        if not self._is_indexable(layer_id, layer):
            if layer_id in self._index:
                del self._index[layer_id]
            return

        if layer_id not in self._queue:
            self._queue.append(layer_id)

        if self._current_iterator is None and not self._timer.isActive():
            # Reindexation isolee : elle merite le meme rapport qu'une passe
            # complete, il lui faut donc sa propre horloge de depart.
            if self._t0 is None:
                self._t0 = time.perf_counter()
                self._reset_session()
            self._set_sync_state(self.SYNC_SYNCING)
            self.indexing_started.emit()
            self._timer.start(0)

    def remove_layer(self, layer_id):
        self._skipped.discard(layer_id)
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
            self._current_count = 0
            self._current_stats = {}
            self._current_t0 = None

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
                    TAG, Qgis.MessageLevel.Info
                )
                self._clear_cache_dir(cache_dir)
        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: manifeste de cache illisible ({e}), reconstruction.",
                TAG, Qgis.MessageLevel.Warning
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
                f"{TAG}: erreur chargement cache: {e}", TAG, Qgis.MessageLevel.Warning
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
                    TAG, Qgis.MessageLevel.Warning
                )
                return

            with open(path, 'wb') as f:
                f.write(compressed)
            self._cache_bytes = projected

        except Exception as e:
            QgsMessageLog.logMessage(
                f"{TAG}: erreur sauvegarde cache: {e}", TAG, Qgis.MessageLevel.Warning
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
                f"{TAG}: erreur ecriture manifeste: {e}", TAG, Qgis.MessageLevel.Warning
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
            keep = {'manifest.json', LOG_FILE}
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
                f"{TAG}: erreur nettoyage cache: {e}", TAG, Qgis.MessageLevel.Warning
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
                f"{TAG}: ancien cache monolithique supprime.", TAG, Qgis.MessageLevel.Info
            )
        except OSError:
            pass

    @staticmethod
    def _clear_cache_dir(cache_dir):
        """Vide le cache d'un projet. Le journal, lui, n'est pas du cache :
        il survit a une reindexation complete pour rester comparable."""
        try:
            for name in os.listdir(cache_dir):
                if name == LOG_FILE:
                    continue
                full = os.path.join(cache_dir, name)
                if os.path.isfile(full):
                    os.remove(full)
        except OSError:
            pass

    @staticmethod
    def _dir_size(path):
        total = 0
        try:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isfile(full):
                    total += os.path.getsize(full)
        except OSError:
            pass
        return total
