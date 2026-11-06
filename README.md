<!-- Badges : syntaxe, styles et encodage des URL shields.io
     https://github.com/badges/shields
     espace = %20 · barre verticale = %7C · tiret litteral = -- · plus = %2B
     « langues » designe l'interface du plugin, traduite en 5 langues. -->

<div align="center">

# Magic Search

<img src="icon.png" width="96" alt="Magic Search"/>

**Une seule barre pour tout retrouver dans QGIS : une adresse, un numero de regard, une parcelle ou des coordonnees**

[![QGIS](https://img.shields.io/badge/QGIS-3.16%20%7C%204.x-green?logo=qgis&logoColor=white)](https://qgis.org)
[![Qt](https://img.shields.io/badge/Qt-5%20%7C%206-41cd52?logo=qt&logoColor=white)](#-qgis-3-et-qgis-4)
[![Version](https://img.shields.io/badge/version-2.2.0-blue)](metadata.txt)
[![License](https://img.shields.io/badge/license-GPL%20v3-orange)](LICENSE)
[![Langues](https://img.shields.io/badge/langues-FR%20%7C%20EN%20%7C%20ES%20%7C%20PT%20%7C%20DE-purple)](#-langues--languages)
[![Dependances](https://img.shields.io/badge/dependances-aucune-lightgrey)](#-prerequis)

**[Francais](#-francais) · [English](#-english) · [Espanol](#-espanol) · [Portugues](#-portugues) · [Deutsch](#-deutsch)**

</div>

---

## 🇫🇷 Francais

## 📝 Description

**Magic Search** ajoute a QGIS une barre de recherche unique, celle qui manque quand on travaille sur un reseau ou un fond cadastral : vous tapez, et le plugin interroge **en meme temps** le geocodeur d'adresses (BAN pour la France, OSM/Nominatim pour le reste du monde) et **tous les champs de toutes les couches vectorielles** du projet. Les resultats arrivent groupes par source, la geometrie s'allume au survol, un clic zoome dessus.

Fini l'aller-retour entre la table attributaire, le filtre par expression et un onglet de navigateur ouvert sur une carte d'adresses : une seule zone de saisie accepte une adresse (`12 rue de Paris`), une valeur metier (`RG-0421`, un numero de branchement, un nom de parcelle) ou des coordonnees brutes (`45.123, 3.456` en WGS84, `652461, 6862050` en Lambert 93). Le plugin devine de quoi il s'agit et vous emmene au bon endroit.

Le cout de cette recherche instantanee est paye une seule fois, et quand vous le decidez : l'indexation ne demarre jamais toute seule, elle se lance sur un clic du bouton de synchronisation de la barre. Ce bouton dit d'un coup d'oeil ou en est l'index - rouge si aucune couche n'est indexee, orange si l'indexation est incomplete (couche ajoutee, passe interrompue), vert quand tout est a jour. Une fois lance, le parcours se fait en tache de fond sans bloquer l'interface, et l'index est conserve dans un cache compresse pose a cote du fichier projet : la synchronisation suivante ne reconstruit que les couches modifiees depuis.

### 🗂️ Sommaire

- [⚙️ Fonctionnalites](#-fonctionnalites)
- [🖥️ Les deux interfaces](#-les-deux-interfaces)
- [🔎 Les boutons de la barre](#-les-boutons-de-la-barre)
- [⌨️ Utilisation](#-utilisation)
- [🛠️ Configuration](#-configuration)
- [🗃️ Indexation et cache](#-indexation-et-cache)
- [🔄 QGIS 3 et QGIS 4](#-qgis-3-et-qgis-4)
- [🚀 Installation](#-installation)
- [📋 Prerequis](#-prerequis)
- [🌍 Langues · Languages](#-langues--languages)
- [🏗️ Architecture](#-architecture)
- [🧪 Tests](#-tests)
- [📜 Changelog](#-changelog)
- [👤 Auteur](#-auteur)

---

## ⚙️ Fonctionnalites

| Fonctionnalite | Ce qu'elle fait |
|---|---|
| **Recherche adresses BAN** | Geocodage des adresses francaises via l'API officielle `api-adresse.data.gouv.fr`, avec filtre optionnel par code postal |
| **Recherche adresses OSM** | Geocodage mondial via Nominatim (OpenStreetMap), quand le projet sort de France |
| **Recherche dans les couches** | Recherche instantanee dans tous les champs de toutes les couches vectorielles du projet, sans ecrire une expression |
| **Recherche par mots** | Tous les mots, dans n'importe quel ordre : `chatel step` trouve « STEP Chatel Montagne ». Tirets, apostrophes, barres, points et parentheses sont ignores, chaque mot est surligne |
| **Recherche de coordonnees** | Saisissez `45.123, 3.456` (WGS84) ou `652461, 6862050` (Lambert 93) : le plugin reconnait le format et zoome |
| **Geocodage inverse** | Menu **⋮ → Adresse au clic sur la carte** : cliquez sur la carte, l'adresse BAN la plus proche (rayon configurable, 25 m par defaut) s'affiche dans le champ ; une puce **?** rappelle que l'outil est actif |
| **Vue de rue** | Bouton **jumelles** : Google Street View, Mapillary, Panoramax ou Bing Streetside s'ouvrent dans le navigateur sur le point clique — ou copie des coordonnees (WGS84 + Lambert 93) |
| **Favoris** | Enregistrez les points recurrents (un regard, une vanne, un poste) et revenez dessus en un clic |
| **Historique** | Les 5 dernieres recherches, rappelees depuis le menu **⋮** |
| **Apercu geometrie** | Surbrillance de l'objet au survol du resultat, zoom au clic |
| **Clavier** | **↑ ↓** pour parcourir la liste, **Entree** pour zoomer, **Echap** pour la fermer, **Tab** pour afficher plus de resultats |
| **Classement par distance** | Adresses et coordonnees classees par distance au centre de la carte : `rue de Paris` tape depuis Vichy donne d'abord celle de Vichy |
| **Indexation incrementale** | Jamais bloquante : la recherche fonctionne deja sur les couches pretes pendant que les autres se chargent |
| **Cache compresse** | Index conserve a cote du `.qgz`, avec empreinte par couche : seul ce qui a change est reconstruit |
| **Indexation a la demande** | Rien ne part tout seul : le bouton **⟳** de la barre declenche la passe et affiche l'etat de l'index par sa couleur |
| **Perimetre de recherche** | Puce **◉ Cochees ▾** a gauche de la barre : ne repondre que sur les couches cochees, ou sur toutes, en un clic — les autres restent indexees |
| **Echelle de zoom** | Sur un resultat ponctuel : 1:200, 1:500 ou 1:1000, au choix |
| **2 styles d'interface** | Barre flottante posee sur le canevas, ou panneau ancrable |
| **QGIS 3 et QGIS 4** | Un seul code, de QGIS 3.16 (Qt 5) a QGIS 4 (Qt 6) |
| **5 langues** | FR, EN, ES, PT, DE — detection automatique depuis la locale QGIS, changement applique a chaud |

**Performance** — depuis la 1.5.0, l'index n'est plus un dictionnaire Python mais des colonnes compactes balayees en C. Sur un projet de **870 000 valeurs distinctes**, une frappe passe de **90-590 ms a 3-24 ms**, soit jusqu'a 25x plus rapide.

---

## 🖥️ Les deux interfaces

| Style | Description | Pour qui |
|---|---|---|
| **Barre flottante** | Barre posee sur le canevas, deplacable et redimensionnable a la souris, opacite reglable de 10 % a 100 % | Ceux qui veulent la recherche sous les yeux sans perdre de place au bord de la fenetre |
| **Panneau ancrable** | Panneau QGIS classique, ancre a gauche ou a droite comme les autres | Ceux qui travaillent avec une disposition de panneaux figee |

Le style se change a tout moment dans la configuration. Les deux partagent la meme pilule de recherche et la meme liste de resultats, donc exactement les memes fonctions ; le panneau affiche en plus le logo du plugin en tete de pilule.

---

## 🔎 Les boutons de la barre

La barre est une pilule arrondie. De gauche a droite :

| Element | Action |
|:---:|---|
| **◉ Cochees ▾** | Perimetre de la recherche dans les couches : **couches cochees** ou **toutes les couches**. Le choix est memorise, comme la case correspondante de la configuration |
| **?** | N'apparait que lorsque l'outil d'adresse au clic est actif ; un clic l'arrete |
| **✕** | Efface le champ de recherche |
| pastille + **⟳** | Etat de l'index et synchronisation. Leur couleur dit ou en est l'index : **rouge** rien d'indexe (le glyphe devient **⚠**), **orange** incomplet, **ambre** passe en cours, **vert** a jour. Un clic sur **⟳** lance une passe |
| **jumelles** | Menu vue de rue : choisissez Google Street View, Mapillary, Panoramax, Bing Streetside ou « Copier les coordonnees », puis cliquez sur la carte |
| **⋮** | **Adresse au clic sur la carte**, **Favoris** (zoomer, ajouter, supprimer), **Recherches recentes**, **Configuration** et **Replier la barre** |

Les menus deroulants reprennent la charte de la barre (coins arrondis, survol turquoise) plutot que le style Qt generique.

### La liste de resultats

Sous la pilule, une ligne par resultat : la valeur trouvee en gras, les mots cherches surlignes, puis en gris la couche et le champ (ou le type d'adresse BAN : numero, voie, lieu-dit, commune). Une bordure a la couleur de la source les distingue d'un coup d'oeil — turquoise pour la BAN. A droite, la distance au centre de la carte pour une adresse ou des coordonnees, le nombre d'objets pour une valeur partagee par plusieurs entites.

Les coordonnees viennent en tete, puis les adresses, puis les valeurs des couches. Quand les resultats sont nombreux, les lignes et le texte se resserrent pour en montrer davantage, puis la liste defile. Le pied indique combien de resultats sont affiches, rappelle **Tab** pour tout voir, et montre l'etat de l'index avec une jauge.

---

## ⌨️ Utilisation

1. Cliquez sur l'icone **Magic Search** dans la barre d'outils, ou appuyez sur **`Ctrl+Alt+F`**.
2. Tapez **au moins 2 caracteres**. La recherche part a chaque frappe.
3. Les resultats s'affichent dans une seule liste : coordonnees, adresses (**BAN** ou **OSM**), puis valeurs trouvees dans les couches. Plusieurs mots se tapent dans n'importe quel ordre.
4. **Survolez** un resultat pour voir la geometrie s'allumer sur la carte, **cliquez** (ou **Entree**) pour zoomer dessus.
5. Pour retrouver une adresse depuis la carte : menu **⋮ → Adresse au clic sur la carte**, puis clic sur le point voulu.
6. Pour ouvrir une vue de rue : bouton **jumelles**, choisissez le service, puis clic sur la carte.

> Astuce : un point que vous consultez souvent (poste de relevage, regard de reference) merite un favori — menu **⋮ → Favoris → Ajouter**. Le zoom se fait ensuite en deux clics, sans rien retaper.

---

## 🛠️ Configuration

Accessible par le menu **⋮ → Configuration** de la barre.

| Reglage | Detail |
|---|---|
| **Geocodeur** | BAN (France), OSM/Nominatim (mondial), ou aucun |
| **Filtre BAN** | Restreint les resultats BAN a un code postal |
| **Rayon de geocodage inverse** | Distance maximale, en metres, pour le bouton **?** (defaut 25 m) |
| **Couches et champs** | Cochez/decochez ce qui doit etre indexe |
| **Perimetre de recherche** | Ne repondre que sur les couches cochees, sans cesser d'indexer les autres — le meme reglage que la puce **◉** de la barre |
| **Zoom sur un point** | Echelle appliquee a un resultat ponctuel : 1:200 (defaut), 1:500 ou 1:1000 |
| **Dates et decimales** | Non indexees par defaut ; une case a cocher les inclut |
| **Cache** | Taille maximale (defaut 50 Mo) ; le chemin affiche est cliquable et ouvre le dossier |
| **Opacite** | De 10 % a 100 % (barre flottante) |
| **Style** | Barre flottante ou panneau ancrable |
| **Langue** | FR, EN, ES, PT, DE, ou suivi automatique de la locale QGIS |

Le style, la langue, le geocodeur, la taille de cache, le rayon, l'echelle de zoom et l'opacite sont memorises **globalement** : ils vous suivent d'un projet a l'autre. Les couches et champs exclus, ainsi que les favoris, restent **propres au projet**, puisqu'ils referencent ses couches.

---

## 🗃️ Indexation et cache

### Quand elle a lieu

Depuis la 2.0, **l'indexation ne demarre jamais d'elle-meme**. Ouvrir un projet, ajouter une couche ou recharger le plugin ne fait que recalculer l'etat de l'index ; c'est le bouton **⟳** de la barre qui lance la passe, et lui seul.

Ce choix vient de l'usage : sur un projet lourd ouvert pour une consultation rapide, une indexation automatique coute du temps et des acces disque que personne n'a demandes. Le bouton porte donc l'etat a lui seul :

| Etat | Bouton | Signification |
|---|:---:|---|
| `never` | pastille **rouge**, glyphe **⚠** | Aucune couche indexee — la recherche dans les couches ne repond pas encore |
| `partial` | pastille **orange** | Index incomplet : couche ajoutee, passe interrompue, exclusion levee |
| `syncing` | pastille **ambre** | Passe en cours, en tache de fond |
| `complete` | **⟳** vert, sans pastille | Tout est a jour |

Une couche examinee mais sans aucun champ indexable n'est pas comptee comme manquante : sans cela le bouton ne repasserait jamais au vert.

### Ce qui est indexe

Par defaut, les champs **texte et entiers**. Sont ecartes :

- les **dates** ;
- les **nombres a decimales** — on ne cherche pas une altitude au clavier ;
- les valeurs **NULL** et l'identifiant interne `fid` des GeoPackage et shapefiles (une cle primaire PostGIS, elle, reste indexee).

Les dates, si vous les incluez, sont indexees en ISO (`2024-03-01`) et au format francais (`01/03/2024`). Les ligatures sont normalisees : `coeur` trouve « cœur ».

Avec une nuance qui compte sur des donnees reelles : beaucoup de sources (shapefiles, exports) typent en decimal des colonnes qui ne contiennent que des entiers, et ce sont souvent les champs metier qu'on cherche vraiment (numero de regard, diametre, contenance). Ces colonnes sont donc indexees, et abandonnees seulement si une vraie decimale apparait — verifie a chaque valeur, pas sur un echantillon.

Une meme table chargee plusieurs fois dans le projet (copie d'une couche, couche d'etiquettes) n'est indexee, stockee et gardee en memoire **qu'une seule fois** : l'index est adresse par son contenu (source, nombre d'entites, champs, exclusions), pas par la couche.

### Le cache

Un dossier `<projet>_magic_search_cache/` a cote du `.qgz`, contenant un `manifest.json` et un fichier `.idx` par index. Chaque `.idx` est un conteneur binaire (entete JSON + tableaux d'entiers bruts) compresse en LZMA.

Il est relu **couche par couche**, une par tour de boucle d'evenements : l'interface reste utilisable pendant le chargement, et la recherche fonctionne deja sur les couches pretes. Un index dont l'empreinte ne correspond plus est reconstruit ; les autres sont repris tels quels — une synchronisation sur un projet inchange ne coute donc presque rien. L'empreinte tient aussi compte de la taille et de la date du fichier source : une valeur corrigee sans changer le nombre d'entites est bien detectee. Enregistrer des modifications sur une couche dans QGIS fait aussitot passer l'index a l'orange.

Le format du cache est versionne : un cache produit par une version anterieure du plugin est purge et reconstruit une fois.

### Structure de l'index

Un champ indexe n'est pas un dictionnaire de valeurs mais quelques blocs compacts :

| Bloc | Contenu |
|---|---|
| `hay` | Valeurs normalisees, concatenees et separees par `\x00` |
| `starts` | Offset de chaque valeur dans `hay` (`array('i')`) |
| `orig` / `orig_starts` | Valeurs d'origine, seulement si elles different des normalisees |
| `fids` / `fid_starts` | Identifiants d'entites, a plat (`array('q')`) |

La recherche devient un `str.find()` sur une grande chaine, execute en C, au lieu d'une iteration Python sur des centaines de milliers de cles. Le separateur `\x00` etant impossible a saisir, aucune correspondance ne peut chevaucher deux valeurs voisines.

Le cout de la compression se paie a l'indexation, jamais a la lecture : le codec est defini par `LZMA_PRESET` en tete de [`core/index_manager.py`](core/index_manager.py) et se change en une ligne.

---

## 🔄 QGIS 3 et QGIS 4

QGIS 4 repose sur **Qt 6**, la ou QGIS 3 utilisait Qt 5. Magic Search 2.0 tourne sur les deux **avec le meme code** : pas de branche separee, pas de version a choisir au telechargement.

Deux differences seulement demandaient un traitement.

**Les enumerations.** Qt 6 ne les expose plus a plat sur la classe : `Qt.ArrowCursor` devient `Qt.CursorShape.ArrowCursor`, `QNetworkReply.NoError` devient `QNetworkReply.NetworkError.NoError`, `QgsRubberBand.ICON_CIRCLE` devient `QgsRubberBand.IconType.ICON_CIRCLE`. La forme longue etant deja valide sous Qt 5, le plugin n'ecrit plus qu'elle.

**Les evenements souris.** Qt 6 remplace `pos()` / `globalPos()` (QPoint) par `position()` / `globalPosition()` (QPointF). C'est le seul point qui demande du code, isole dans [`core/qt_compat.py`](core/qt_compat.py) :

```python
def event_global_pos(event):
    """Position ecran (QPoint) d'un evenement souris, Qt 5 comme Qt 6."""
    global_position = getattr(event, 'globalPosition', None)
    if global_position is not None:
        return global_position().toPoint()
    return event.globalPos()
```

Le module interroge l'evenement plutot que la version de Qt : un Qt 5 recompile ou un Qt 6 conservant les API depreciees sont traites correctement dans les deux cas. Tout le plugin — deplacement et redimensionnement de la barre flottante, outils de clic sur la carte — passe par ces deux fonctions, couvertes par les tests.

Reste un detail d'import : `QAction` et `QShortcut` ont quitte `QtWidgets` pour `QtGui`. [`plugin_main.py`](plugin_main.py) tente l'import Qt 6 et retombe sur Qt 5.

> Le libelle du style d'interface passe de « Panneau ancrable (Qt5) » a « Panneau ancrable » — la mention n'avait plus lieu d'etre. La preference deja enregistree reste valable : l'identifiant interne, lui, ne change pas.

---

## 🚀 Installation

1. Telechargez ou clonez ce depot :

   ```bash
   git clone https://github.com/Cartoyoyo/Magic_search.git
   ```

2. Copiez le dossier `magic_search` dans le repertoire des plugins QGIS :

   | Systeme | Chemin |
   |---------|--------|
   | Windows | `C:\Users\<utilisateur>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\` |
   | macOS   | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |
   | Linux   | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |

3. Ouvrez QGIS, allez dans **Extensions → Installer/Gerer les extensions → Installees**, cochez **Magic Search** et cliquez sur **OK**.

4. L'icone apparait dans la barre d'outils. Raccourci : **`Ctrl+Alt+F`**.

> Le plugin est aussi disponible depuis le depot officiel : **Extensions → Installer/Gerer les extensions → Toutes**, puis recherchez « Magic Search ».

---

## 📋 Prerequis

| Dependance | Statut | Usage |
|---|---|---|
| QGIS **3.16 a 4.x** | requis | le meme code sous QGIS 3 (Qt 5) et QGIS 4 (Qt 6) |
| Connexion internet | optionnel | geocodage BAN / OSM uniquement ; la recherche dans les couches fonctionne hors ligne |

**Aucune dependance Python hors bibliotheque standard.** Rien a installer avec `pip`.

---

## 🌍 Langues · Languages

L'**interface du plugin** et **cette documentation** sont disponibles en cinq langues.

| Langue | Interface | Documentation |
|---|:---:|:---:|
| Francais | ✅ | ✅ complete |
| English | ✅ | ✅ complete |
| Espanol | ✅ | ✅ condensee |
| Portugues | ✅ | ✅ condensee |
| Deutsch | ✅ | ✅ condensee |

Au premier lancement, le plugin suit la locale de QGIS. Le choix d'une langue dans la configuration prime ensuite sur celle de QGIS et s'applique **a chaud**, sans redemarrage : placeholders, infobulles, messages d'indexation et entrees de menu suivent immediatement.

---

## 🇬🇧 English

### 📝 Description

**Magic Search** adds a single search bar to QGIS: as you type, the plugin queries **at the same time** the address geocoder (BAN for France, OSM/Nominatim worldwide) and **every field of every vector layer** in your project. Results come grouped by source, geometry highlights on hover, a click zooms to it.

No more round-trips between the attribute table, an expression filter and a browser tab open on an address map: one input accepts an address (`12 rue de Paris`), a business value (`RG-0421`, a manhole number, a parcel name) or raw coordinates (`45.123, 3.456` in WGS84, `652461, 6862050` in Lambert 93). The plugin works out which is which and takes you there.

The cost of that instant search is paid once, and when you decide: indexing never starts on its own, it runs on a click of the bar's sync button. That button shows the state of the index at a glance - red when no layer is indexed, orange when indexing is incomplete (layer added, pass interrupted), green when everything is up to date. Once started, the pass runs in the background without blocking the UI, and the index is kept in a compressed cache stored next to the project file: the next sync only rebuilds the layers changed since.

### ⚙️ Features

| Feature | What it does |
|---|---|
| **BAN address search** | French address geocoding through the official `api-adresse.data.gouv.fr` API, with optional postcode filter |
| **OSM address search** | Worldwide geocoding through Nominatim (OpenStreetMap) |
| **Layer search** | Instant search across every field of every vector layer, no expression to write |
| **Word search** | All words, in any order: `chatel step` finds "STEP Chatel Montagne". Dashes, apostrophes, slashes, dots and brackets are ignored, each word is highlighted |
| **Coordinate search** | Type `45.123, 3.456` (WGS84) or `652461, 6862050` (Lambert 93): the plugin detects the format and zooms |
| **Reverse geocoding** | **⋮ → Address at map click** menu: click the map, the nearest BAN address (configurable radius, 25 m by default) appears in the field; a **?** chip shows the tool is active |
| **Street view** | **Binoculars** button: Google Street View, Mapillary, Panoramax or Bing Streetside open in the browser at the clicked point — or copy the coordinates (WGS84 + Lambert 93) |
| **Favourites** | Save recurring points and jump back to them in one click |
| **History** | The last 5 searches, from the **⋮** menu |
| **Geometry preview** | Highlight on hover, zoom on click |
| **Keyboard** | **↑ ↓** to browse the list, **Enter** to zoom, **Esc** to close it, **Tab** to show more results |
| **Sorted by distance** | Addresses and coordinates sorted by distance from the map centre: `rue de Paris` typed while looking at Vichy gives Vichy's first |
| **Incremental indexing** | Never blocking: search already works on ready layers while the others load |
| **Compressed cache** | Index stored next to the `.qgz`, with a per-layer fingerprint so only changed layers are rebuilt |
| **On-demand indexing** | Nothing starts by itself: the bar's **⟳** button runs the pass and shows the index state through its colour |
| **Search scope** | **◉ Visible ▾** chip on the left of the bar: answer only on ticked layers, or on all of them, in one click — the others stay indexed |
| **Zoom scale** | On a point result: 1:200, 1:500 or 1:1000 |
| **2 UI styles** | Floating bar over the canvas, or dockable panel |
| **QGIS 3 and QGIS 4** | One codebase, from QGIS 3.16 (Qt 5) to QGIS 4 (Qt 6) |
| **5 languages** | FR, EN, ES, PT, DE — auto-detected from the QGIS locale, applied live |

**Performance** — since 1.5.0 the index is no longer a Python dictionary but compact columns scanned in C. On a project holding **870,000 distinct values**, a keystroke drops from **90-590 ms to 3-24 ms**, up to 25x faster.

### ⌨️ Usage

1. Click the **Magic Search** toolbar icon, or press **`Ctrl+Alt+F`**.
2. Type **at least 2 characters**; the search runs on every keystroke.
3. Results come in a single list: coordinates, addresses (**BAN** or **OSM**), then values found in the layers. Several words can be typed in any order.
4. **Hover** a result to highlight the geometry, **click** it (or press **Enter**) to zoom to it.
5. **⋮ → Address at map click**, then a map click: shows the nearest BAN address.
6. **Binoculars** button, pick a service, then a map click: opens the street view.

The bar is a rounded pill: scope chip, search field, index state (dot + **⟳** sync button), binoculars and the **⋮** menu (address at map click, favourites, recent searches, settings, collapse). Each result line shows the matched value in bold, the layer and field in grey, a border in the source colour, and on the right the distance or the number of features.

### 🔄 QGIS 3 and QGIS 4

QGIS 4 is built on **Qt 6**, where QGIS 3 used Qt 5. Magic Search 2.0 runs on both from **the same code**: no separate branch, no version to pick when downloading.

Only two differences needed work. **Enumerations** are no longer flat on the class (`Qt.CursorShape.ArrowCursor`, `QNetworkReply.NetworkError.NoError`, `QgsRubberBand.IconType.ICON_CIRCLE`); since the long form is already valid under Qt 5, the plugin now writes only that. **Mouse events** replace `pos()` / `globalPos()` (QPoint) with `position()` / `globalPosition()` (QPointF) - the one point that needs code, isolated in [`core/qt_compat.py`](core/qt_compat.py), which asks the event rather than testing the Qt version.

See the French section [QGIS 3 et QGIS 4](#-qgis-3-et-qgis-4) for the details.

### 📋 Requirements

| Dependency | Status | Purpose |
|---|---|---|
| QGIS **3.16 to 4.x** | required | same code under QGIS 3 (Qt 5) and QGIS 4 (Qt 6) |
| Internet connection | optional | BAN / OSM geocoding only; layer search works offline |

**No Python dependency outside the standard library.**

### 🚀 Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Cartoyoyo/Magic_search.git
   ```

2. Copy the `magic_search` folder into the QGIS plugins directory:

   | System | Path |
   |---------|--------|
   | Windows | `C:\Users\<user>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\` |
   | macOS   | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |
   | Linux   | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |

3. In QGIS, open **Plugins → Manage and Install Plugins → Installed**, tick **Magic Search** and click **OK**.

4. The toolbar icon appears. Shortcut: **`Ctrl+Alt+F`**.

---

## 🇪🇸 Espanol

> Las funciones detalladas y las tablas de configuracion estan en la seccion [Francais](#-francais) al inicio de este documento.

### 📝 Descripcion

**Magic Search** anade a QGIS una unica barra de busqueda: mientras escribe, el complemento consulta **a la vez** el geocodificador de direcciones (BAN en Francia, OSM/Nominatim en todo el mundo) y **todos los campos de todas las capas vectoriales** del proyecto. Los resultados se agrupan por fuente, la geometria se resalta al pasar el raton y un clic hace zoom.

Un solo campo acepta una direccion, un valor de negocio (numero de pozo, referencia catastral) o coordenadas en bruto (`45.123, 3.456` en WGS84, `652461, 6862050` en Lambert 93).

### ⚙️ Funcionalidades

- **Geocodificacion BAN** (Francia) y **OSM/Nominatim** (mundial), con filtro por codigo postal
- **Busqueda en todos los campos** de todas las capas vectoriales, sin escribir expresiones
- **Busqueda por palabras** en cualquier orden : `chatel step` encuentra « STEP Chatel Montagne »
- **Busqueda de coordenadas** WGS84 y Lambert 93
- **Geocodificacion inversa** desde el menu **⋮** : clic en el mapa, direccion BAN mas cercana (radio configurable, 25 m por defecto)
- **Vista de calle** con el boton de **prismaticos** : Google Street View, Mapillary, Panoramax, Bing Streetside, o copiar las coordenadas
- **Favoritos** e **historial** (5 ultimas busquedas) en el menu **⋮**
- **Indexacion incremental** no bloqueante y **cache comprimida** junto al archivo de proyecto
- **Indexacion a peticion** : nada se lanza solo, el boton **⟳** de la barra ejecuta la pasada y muestra el estado del indice por su color
- **Alcance de la busqueda** : responder solo en las capas marcadas, sin dejar de indexar las demas
- **Dos estilos de interfaz** : barra flotante o panel acoplable
- **Compatible con QGIS 3.16 hasta QGIS 4** (Qt 5 y Qt 6) con el mismo codigo
- **Cinco idiomas** : FR, EN, ES, PT, DE

### 🚀 Instalacion

1. Copie la carpeta `magic_search` en `.../QGIS3/profiles/default/python/plugins/`
2. Abra **Complementos → Administrar e instalar complementos → Instalados**, marque **Magic Search** y pulse **Aceptar**
3. Requisitos: QGIS **3.16 a 4.x**, ninguna dependencia de Python. Atajo: **`Ctrl+Alt+F`**

---

## 🇵🇹 Portugues

> As funcionalidades detalhadas e as tabelas de configuracao estao na seccao [Francais](#-francais) no inicio deste documento.

### 📝 Descricao

**Magic Search** acrescenta ao QGIS uma unica barra de pesquisa: enquanto escreve, o modulo consulta **ao mesmo tempo** o geocodificador de enderecos (BAN em Franca, OSM/Nominatim em todo o mundo) e **todos os campos de todas as camadas vetoriais** do projeto. Os resultados sao agrupados por fonte, a geometria e realcada ao passar o rato e um clique faz zoom.

Um unico campo aceita um endereco, um valor de negocio (numero de caixa, referencia predial) ou coordenadas em bruto (`45.123, 3.456` em WGS84, `652461, 6862050` em Lambert 93).

### ⚙️ Funcionalidades

- **Geocodificacao BAN** (Franca) e **OSM/Nominatim** (mundial), com filtro por codigo postal
- **Pesquisa em todos os campos** de todas as camadas vetoriais, sem escrever expressoes
- **Pesquisa por palavras** em qualquer ordem : `chatel step` encontra « STEP Chatel Montagne »
- **Pesquisa de coordenadas** WGS84 e Lambert 93
- **Geocodificacao inversa** a partir do menu **⋮** : clique no mapa, endereco BAN mais proximo (raio configuravel, 25 m por defeito)
- **Vista de rua** com o botao de **binoculos** : Google Street View, Mapillary, Panoramax, Bing Streetside, ou copiar as coordenadas
- **Favoritos** e **historico** (5 ultimas pesquisas) no menu **⋮**
- **Indexacao incremental** nao bloqueante e **cache comprimida** junto ao ficheiro de projeto
- **Indexacao a pedido** : nada arranca sozinho, o botao **⟳** da barra lanca a passagem e mostra o estado do indice pela sua cor
- **Ambito da pesquisa** : responder apenas nas camadas marcadas, continuando a indexar as restantes
- **Dois estilos de interface** : barra flutuante ou painel acoplavel
- **Compativel com QGIS 3.16 ate QGIS 4** (Qt 5 e Qt 6) com o mesmo codigo
- **Cinco idiomas** : FR, EN, ES, PT, DE

### 🚀 Instalacao

1. Copie a pasta `magic_search` para `.../QGIS3/profiles/default/python/plugins/`
2. Abra **Modulos → Gerir e instalar modulos → Instalados**, marque **Magic Search** e clique em **OK**
3. Requisitos: QGIS **3.16 a 4.x**, nenhuma dependencia Python. Atalho: **`Ctrl+Alt+F`**

---

## 🇩🇪 Deutsch

> Die ausfuehrlichen Funktionen und Konfigurationstabellen finden Sie im Abschnitt [Francais](#-francais) am Anfang dieses Dokuments.

### 📝 Beschreibung

**Magic Search** fuegt QGIS eine einzige Suchleiste hinzu: waehrend Sie tippen, fragt die Erweiterung **gleichzeitig** den Adress-Geocoder (BAN fuer Frankreich, OSM/Nominatim weltweit) und **alle Felder aller Vektorebenen** des Projekts ab. Die Ergebnisse sind nach Quelle gruppiert, die Geometrie wird beim Ueberfahren hervorgehoben, ein Klick zoomt darauf.

Ein einziges Feld akzeptiert eine Adresse, einen Fachwert (Schachtnummer, Flurstueckskennung) oder rohe Koordinaten (`45.123, 3.456` in WGS84, `652461, 6862050` in Lambert 93).

### ⚙️ Funktionen

- **BAN-Geokodierung** (Frankreich) und **OSM/Nominatim** (weltweit), mit Postleitzahlfilter
- **Suche in allen Feldern** aller Vektorebenen, ohne Ausdruecke zu schreiben
- **Wortsuche** in beliebiger Reihenfolge : `chatel step` findet « STEP Chatel Montagne »
- **Koordinatensuche** in WGS84 und Lambert 93
- **Rueckwaerts-Geokodierung** ueber das Menue **⋮** : Klick auf die Karte, naechste BAN-Adresse (konfigurierbarer Radius, standardmaessig 25 m)
- **Strassenansicht** mit der **Fernglas**-Schaltflaeche : Google Street View, Mapillary, Panoramax, Bing Streetside oder Koordinaten kopieren
- **Favoriten** und **Verlauf** (letzte 5 Suchen) im Menue **⋮**
- **Inkrementelle, nicht blockierende Indizierung** und **komprimierter Cache** neben der Projektdatei
- **Indizierung auf Abruf** : nichts startet von selbst, die Schaltflaeche **⟳** der Leiste startet den Durchlauf und zeigt den Zustand des Index ueber ihre Farbe
- **Suchbereich** : nur in angehakten Ebenen antworten, die uebrigen bleiben indiziert
- **Zwei Oberflaechenstile** : schwebende Leiste oder andockbares Panel
- **Kompatibel mit QGIS 3.16 bis QGIS 4** (Qt 5 und Qt 6) mit demselben Code
- **Fuenf Sprachen** : FR, EN, ES, PT, DE

### 🚀 Installation

1. Kopieren Sie den Ordner `magic_search` nach `.../QGIS3/profiles/default/python/plugins/`
2. Oeffnen Sie **Erweiterungen → Erweiterungen verwalten und installieren → Installiert**, haken Sie **Magic Search** an und klicken Sie **OK**
3. Voraussetzungen: QGIS **3.16 bis 4.x**, keine Python-Abhaengigkeit. Tastenkuerzel: **`Ctrl+Alt+F`**

---

## 🏗️ Architecture

Le diagramme [`magic_search.d2`](magic_search.d2) decrit les classes et leurs relations ; [`magic_search.svg`](magic_search.svg) en est le rendu.

```bash
d2 --theme 200 magic_search.d2 magic_search.svg
```

| Dossier | Role |
|---|---|
| `ui/` | Barre flottante, panneau ancrable, dialogue de configuration, styles partages |
| `core/` | Index et cache, geocodage inverse, vue de rue, favoris, coordonnees, compatibilite Qt 5 / Qt 6 |
| `providers/` | Sources de resultats : BAN, OSM/Nominatim, couches du projet |
| `tests/` | Tests unitaires executables hors QGIS |
| `scripts/` | Publication sur `plugins.qgis.org` |

---

## 🧪 Tests

```bash
python -m unittest discover -s tests -v
```

Les tests s'executent **hors QGIS** : les modules `qgis.core` et `qgis.PyQt` sont remplaces par des doublures minimales, ce qui permet de couvrir la normalisation du texte, les empreintes de couches, les cles d'index, l'indexation d'entites et la recherche sans lancer l'application.

La couche de compatibilite Qt 5 / Qt 6 y est testee sur des evenements souris simules des deux familles — un evenement Qt 6 sans `pos()` ni `globalPos()`, un evenement Qt 5 sans `position()` — ce qui verifie le portage sans installer les deux versions de QGIS.

---

## 📜 Changelog

| Version | Notes |
|---------|-------|
| **2.2.0** | **Nouvelle barre de recherche** (barre flottante et panneau) : puce de perimetre, etat de l'index, jumelles, menu **⋮** — liste de resultats sur deux niveaux avec distance ou nombre d'objets, lignes resserrees quand les resultats sont nombreux, navigation au clavier — **recherche par mots** dans n'importe quel ordre — adresses et coordonnees classees par distance au centre de la carte — indexation 3 a 3,6 fois plus rapide, sans gel — raccourci **`Ctrl+Alt+F`** — corrections : favoris effaces en validant la configuration, couche modifiee non detectee, NULL de shapefile indexes, dates illisibles |
| **2.1.1** | Correction d'un plantage sous QGIS 4 / Qt 6 (lecture sans geometrie) |
| **2.1.0** | Indexation pilotee par un budget de temps — lecture restreinte aux champs indexes — journal `indexation.log` a cote du cache — empreintes en blake2b |
| **2.0.0** | **Compatibilite QGIS 4 / Qt 6** avec un seul code, de QGIS 3.16 a 4.x — indexation declenchee par l'utilisateur, avec un bouton **⟳** qui affiche l'etat de l'index — option pour restreindre la recherche aux couches cochees — echelle de zoom configurable sur un resultat ponctuel — code reorganise en paquets `ui/`, `core/`, `providers/` |
| **1.5.0** | Recherche jusqu'a 25x plus rapide (index en colonnes compactes balayees en C) — rechargement instantane du plugin — deduplication des tables chargees plusieurs fois — dates et decimales exclues par defaut, avec detection des colonnes decimales ne contenant que des entiers — nouveau format de cache LZMA (pres de quatre fois moins de disque) — preferences memorisees globalement |
| **1.4.0** | Recherche de coordonnees WGS84 / Lambert 93 — copie des coordonnees — rayon de geocodage inverse configurable — filtre BAN par code postal — favoris et historique dans un menu **⋮** — repere persistant du dernier point interroge |
| **1.3.0** | Menu vue de rue : Google Street View, Mapillary, Panoramax, Bing Streetside |
| **1.2.0** | Bouton **?** : geocodage inverse BAN, avec message discret si aucune adresse dans le rayon |
| **1.1.0** | Interface entierement traduite en 5 langues — detection automatique de la langue — lien auteur dans le dialogue A propos — User-Agent Nominatim lu depuis `metadata.txt` |
| **1.0.0** | Version initiale : barre universelle (BAN + OSM + couches), 2 styles d'interface, indexation incrementale avec cache compresse, exclusions configurables, apercu geometrie |

Le detail complet de chaque version est dans [`metadata.txt`](metadata.txt).

---

## 👤 Auteur

<div align="center">

Developpe par / Developed by **Yoan Laloux**

Technicien SIG · GIS Technician

[![LinkedIn](https://img.shields.io/badge/LinkedIn-ylaloux-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/ylaloux/)
[![GitHub](https://img.shields.io/badge/GitHub-Cartoyoyo-black?logo=github)](https://github.com/Cartoyoyo)

</div>

---

## 📄 Licence · License

Ce plugin est distribue sous licence **GNU General Public License v3.0** — voir [LICENSE](LICENSE).

This plugin is released under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).

<div align="center">

Depot : <https://github.com/Cartoyoyo/Magic_search> · Anomalies et demandes : <https://github.com/Cartoyoyo/Magic_search/issues>

</div>
