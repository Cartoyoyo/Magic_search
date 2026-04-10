# Magic Search - Universal Search for QGIS

Barre de recherche universelle pour QGIS : recherchez simultanement dans les adresses BAN/OSM et dans tous les champs de toutes les couches de votre projet.

## Fonctionnalites

- **Recherche BAN** : geocodage d'adresses francaises via l'API BAN (api-adresse.data.gouv.fr)
- **Recherche OSM** : geocodage mondial via Nominatim (OpenStreetMap)
- **Recherche couches** : recherche instantanee dans tous les champs de toutes les couches vectorielles du projet
- **Indexation incrementale** : cache compresse (gzip + msgpack) stocke a cote du projet
- **2 styles d'interface** : barre flottante style Maps ou panneau ancrable Qt5
- **Apercu geometrie** : surbrillance au survol, zoom au clic
- **Configuration avancee** : exclusion couches/champs, choix du geocodeur, opacite
- **i18n** : Francais, English, Espanol, Portugues, Deutsch

## Installation

1. Copier le dossier `magic_search/` dans le repertoire des plugins QGIS :
   - **Windows** : `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux** : `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS** : `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
2. Redemarrer QGIS
3. Activer le plugin dans Extensions > Gerer les extensions

## Utilisation

- Cliquer sur l'icone Magic Search dans la barre d'outils ou utiliser **Ctrl+Shift+F**
- Taper au moins 2 caracteres pour lancer la recherche
- Les resultats sont groupes par source (BAN/OSM/couches)
- Cliquer sur un resultat pour zoomer, survoler pour previsualiser la geometrie
- Acceder a la configuration via le bouton engrenage

## Configuration

- **Geocodeur** : BAN (France), OSM/Nominatim (mondial), ou aucun
- **Couches/champs** : cocher/decocher les couches et champs a indexer
- **Cache** : taille max configurable (defaut 50 Mo)
- **Opacite** : reglable de 10% a 100%
- **Style** : barre flottante (Maps) ou panneau ancrable (Qt5)

## Prerequis

- QGIS >= 3.16
- Connexion internet pour BAN/OSM (optionnel)

## Licence

GNU General Public License v3.0 - voir [LICENSE](LICENSE)

## Auteur

Yoan Laloux - [y.laloux@vichy-communaute.fr](mailto:y.laloux@vichy-communaute.fr)

Repository : [github.com/Cartoyoyo/magic-search](https://github.com/Cartoyoyo/magic-search)
