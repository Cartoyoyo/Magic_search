"""
coord_parser - Reconnait une paire de coordonnees tapee dans la barre de
recherche (WGS84 decimal ou Lambert93) et la traite comme une source de
resultat supplementaire, au meme titre que BAN/OSM/couches.
"""
import re

# Decimales WGS84 : separateur '.' uniquement (la ',' et le ';' servent a
# separer les deux valeurs, pas de decimales, pour lever toute ambiguite
# avec la notation francaise a virgule).
_DECIMAL_RE = re.compile(
    r'^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,;\s]+\s*(-?\d{1,3}(?:\.\d+)?)\s*$'
)
# Lambert93 (EPSG:2154) : X ~ [0, 1 300 000], Y ~ [6 000 000, 7 200 000]
# sur le territoire francais.
_LAMBERT93_RE = re.compile(
    r'^\s*(\d{5,7}(?:\.\d+)?)\s*[,;\s]+\s*(\d{6,8}(?:\.\d+)?)\s*$'
)


def parse_coordinates(text):
    """Retourne un dict decrivant la coordonnee reconnue, sinon None.
    - WGS84  : {'crs': 'EPSG:4326', 'lon': float, 'lat': float, 'label': str}
    - Lambert93 : {'crs': 'EPSG:2154', 'x': float, 'y': float, 'label': str}
    Quand les deux ordres sont possibles, c'est lat, lon qui est retenu ;
    coordinate_candidates() donne les deux.
    """
    candidates = coordinate_candidates(text)
    return candidates[0] if candidates else None


def _wgs84(lat, lon, order):
    # Libelle explicite : quand les deux lectures sont proposees, c'est lui
    # qui dit laquelle est laquelle (les chiffres tapes sont les memes).
    return {
        'crs': 'EPSG:4326', 'lat': lat, 'lon': lon, 'order': order,
        'label': f'lat {lat:.6f}, lon {lon:.6f} (WGS84)',
    }


def coordinate_candidates(text, near=None):
    """Toutes les lectures plausibles d'une saisie, la plus probable d'abord.

    Une paire decimale peut etre lat, lon (ordre GPS) ou lon, lat (ordre x, y
    que QGIS affiche et copie en EPSG:4326). Lire "3.42, 46.12" en lat, lon
    envoyait en Somalie au lieu de Vichy. Quand les deux ordres sont valides,
    les deux sont proposes ; `near` (lon, lat), le centre de la carte en
    general, place en tete celui qui tombe le plus pres.
    """
    text = text.strip()

    m = _DECIMAL_RE.match(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        found = []
        if -90 <= a <= 90 and -180 <= b <= 180:
            found.append(_wgs84(a, b, 'latlon'))
        if -90 <= b <= 90 and -180 <= a <= 180 and a != b:
            found.append(_wgs84(b, a, 'lonlat'))
        if near is not None and len(found) > 1:
            n_lon, n_lat = near
            found.sort(key=lambda c: (c['lon'] - n_lon) ** 2 + (c['lat'] - n_lat) ** 2)
        if found:
            return found

    m = _LAMBERT93_RE.match(text)
    if m:
        x, y = float(m.group(1)), float(m.group(2))
        if 0 <= x <= 1_300_000 and 6_000_000 <= y <= 7_200_000:
            return [{
                'crs': 'EPSG:2154', 'x': x, 'y': y,
                'label': f'{x:.1f}, {y:.1f} (Lambert93)',
            }]

    return []


def to_lonlat(coord):
    """Ramene un dict retourne par parse_coordinates vers (lon, lat) WGS84,
    quel que soit le CRS reconnu. Importe geo_actions ici (et non en tete de
    module) pour garder ce fichier testable sans QGIS quand seul parse_coordinates
    est utilise."""
    if coord['crs'] == 'EPSG:4326':
        return coord['lon'], coord['lat']
    from . import geo_actions
    return geo_actions.to_wgs84(coord['x'], coord['y'], coord['crs'])
