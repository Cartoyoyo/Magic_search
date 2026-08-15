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
    """
    text = text.strip()

    m = _DECIMAL_RE.match(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        # Convention lat, lon (ordre GPS le plus courant) ; le premier nombre
        # doit rester dans l'intervalle de latitude pour lever l'ambiguite.
        if -90 <= a <= 90 and -180 <= b <= 180:
            return {
                'crs': 'EPSG:4326', 'lat': a, 'lon': b,
                'label': f'{a:.6f}, {b:.6f} (WGS84)',
            }

    m = _LAMBERT93_RE.match(text)
    if m:
        x, y = float(m.group(1)), float(m.group(2))
        if 0 <= x <= 1_300_000 and 6_000_000 <= y <= 7_200_000:
            return {
                'crs': 'EPSG:2154', 'x': x, 'y': y,
                'label': f'{x:.1f}, {y:.1f} (Lambert93)',
            }

    return None


def to_lonlat(coord):
    """Ramene un dict retourne par parse_coordinates vers (lon, lat) WGS84,
    quel que soit le CRS reconnu. Importe geo_actions ici (et non en tete de
    module) pour garder ce fichier testable sans QGIS quand seul parse_coordinates
    est utilise."""
    if coord['crs'] == 'EPSG:4326':
        return coord['lon'], coord['lat']
    from . import geo_actions
    return geo_actions.to_wgs84(coord['x'], coord['y'], coord['crs'])
