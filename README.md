# Magic Search - Universal Search for QGIS

Barre de recherche universelle pour QGIS : recherchez simultanement dans les adresses BAN/OSM et dans tous les champs de toutes les couches de votre projet.

## Fonctionnalites

- **Recherche BAN** : geocodage d'adresses francaises via l'API BAN (api-adresse.data.gouv.fr)
- **Recherche OSM** : geocodage mondial via Nominatim (OpenStreetMap)
- **Recherche couches** : recherche instantanee dans tous les champs de toutes les couches vectorielles du projet
- **Geocodage inverse** : bouton "?" dans la barre de recherche - cliquez sur la carte pour afficher l'adresse BAN la plus proche (rayon 25 m) directement dans le champ de recherche
- **Vue de rue** : bouton "◎" - Google Street View, Mapillary, Panoramax, Bing Streetside, ou copier les coordonnees (WGS84 + Lambert93) - choisissez puis cliquez sur la carte
- **Menu "..."** : regroupe favoris et historique derriere un seul bouton pour garder la barre compacte
  - **Favoris** : enregistrez des points recurrents (regard, vanne...) et zoomez dessus en un clic
  - **Historique** : les 5 dernieres recherches
- **Recherche de coordonnees** : tapez `45.123, 3.456` (WGS84) ou `652461, 6862050` (Lambert93) directement dans le champ pour zoomer dessus
- **Indexation incrementale** : cache compresse (gzip + msgpack) stocke a cote du projet
- **2 styles d'interface** : barre flottante style Maps ou panneau ancrable Qt5
- **Apercu geometrie** : surbrillance au survol, zoom au clic
- **Configuration avancee** : exclusion couches/champs, choix du geocodeur, filtre BAN par code postal, rayon de geocodage inverse, opacite
- **i18n** : Francais, English, Espanol, Portugues, Deutsch — detection automatique depuis la locale QGIS, changement de langue applique a chaud (placeholders, infobulles, messages d'indexation, menus)
- **Menus habilles** : sur la barre flottante, les menus deroulants ("◎", "⋮" et sous-menus) reprennent la charte de la barre (bordure marine arrondie, survol turquoise) au lieu du style Qt generique

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
- Cliquer sur le bouton **"?"** puis sur un point de la carte pour afficher l'adresse BAN la plus proche (rayon 25 m) dans le champ de recherche
- Cliquer sur le bouton **"◎"**, choisir un service (Google/Mapillary/Panoramax/Bing) ou "Copier les coordonnees", puis cliquer sur la carte
- Cliquer sur le bouton **"⋮"** pour acceder au sous-menu Favoris (zoomer/ajouter/supprimer) ou Recherches recentes
- Acceder a la configuration via le bouton engrenage

## Configuration

- **Geocodeur** : BAN (France), OSM/Nominatim (mondial), ou aucun
- **Filtre BAN** : restreindre les resultats BAN a un code postal
- **Rayon geocodage inverse** : distance max (metres) pour le bouton "?" (defaut 25 m)
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

**Yoan Laloux** - [linkedin.com/in/ylaloux](https://www.linkedin.com/in/ylaloux/)

Repository : [github.com/Cartoyoyo/Magic_search](https://github.com/Cartoyoyo/Magic_search)
