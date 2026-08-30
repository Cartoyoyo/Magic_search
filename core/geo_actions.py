"""
Actions geographiques communes (couleurs de couches, zoom, surbrillance)
partagees entre les styles d'UI (barre flottante 'maps' et panneau ancrable 'qt5')
pour eviter que les correctifs ne s'appliquent qu'a un seul des deux.
"""
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsPointXY, QgsGeometry, Qgis
)
from qgis.gui import QgsRubberBand

VC_TURQUOISE = '#00a096'
COLOR_HIGHLIGHT = '#ff00ff'

# Echelles de zoom sur un resultat de couche.
# Un point n'a pas d'emprise : sans echelle imposee, le canevas resterait ou
# il est. On serre au 1:200 pour voir l'objet et son contexte immediat, la ou
# lignes et polygones se contentent d'un plancher plus large.
POINT_SCALE_CHOICES = (200, 500, 1000)
DEFAULT_POINT_SCALE = 200
MIN_SCALE = 1000

# Echelle courante, pilotee par la configuration (set_point_scale).
_point_scale = DEFAULT_POINT_SCALE


def set_point_scale(scale):
    """Fixe l'echelle de zoom sur un resultat ponctuel.

    Une valeur hors des choix proposes est ignoree plutot que corrigee : elle
    ne peut venir que d'une configuration ecrite a la main ou d'un ancien
    projet, et un zoom aberrant est plus deroutant qu'un zoom inchange.
    """
    global _point_scale
    try:
        scale = int(scale)
    except (TypeError, ValueError):
        return
    if scale in POINT_SCALE_CHOICES:
        _point_scale = scale


def point_scale():
    return _point_scale

LAYER_COLORS = [
    ('#eef2ff', '#3730a3'),  # indigo
    ('#fef3c7', '#92400e'),  # ambre
    ('#dcfce7', '#166534'),  # vert
    ('#fce7f3', '#9d174d'),  # rose
    ('#e0f2fe', '#075985'),  # bleu ciel
    ('#fef9c3', '#854d0e'),  # jaune
    ('#f3e8ff', '#6b21a8'),  # violet
    ('#ccfbf1', '#115e59'),  # teal
    ('#fee2e2', '#991b1b'),  # rouge
    ('#e0e7ff', '#3b0764'),  # lavande
]
_layer_color_map = {}


def color_for_layer(layer_id):
    """Retourne (bg, fg) pastel unique par couche, partage entre tous les styles d'UI."""
    if layer_id not in _layer_color_map:
        idx = len(_layer_color_map) % len(LAYER_COLORS)
        _layer_color_map[layer_id] = LAYER_COLORS[idx]
    return _layer_color_map[layer_id]


def _point_geom_type():
    try:
        return Qgis.GeometryType.Point            # QGIS >= 3.30
    except AttributeError:
        from qgis.core import QgsWkbTypes
        return QgsWkbTypes.GeometryType.PointGeometry


def _circle_icon():
    """Marqueur circulaire d'un QgsRubberBand.

    Sous Qt 6 (QGIS 4) les enums ne sont plus exposees a plat sur la classe :
    QgsRubberBand.ICON_CIRCLE n'existe que sous Qt 5, la forme scopee
    QgsRubberBand.IconType.ICON_CIRCLE fonctionne sur les deux.
    """
    icon_type = getattr(QgsRubberBand, 'IconType', None)
    if icon_type is not None:
        return icon_type.ICON_CIRCLE
    # getattr et non l'acces direct : le verificateur Qt6 de plugins.qgis.org
    # signale la forme non scopee sans voir le garde ci-dessus.
    return getattr(QgsRubberBand, 'ICON_CIRCLE')


def transform_point(iface, lon, lat):
    """Transforme un point WGS84 (lon, lat) vers le CRS du canevas."""
    canvas = iface.mapCanvas()
    crs_src = QgsCoordinateReferenceSystem('EPSG:4326')
    crs_dst = canvas.mapSettings().destinationCrs()
    transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
    return transform.transform(QgsPointXY(lon, lat))


def to_wgs84(x, y, crs_epsg):
    """Convertit un point (x, y) depuis crs_epsg (ex: 'EPSG:2154') vers
    WGS84. Retourne (lon, lat). Utilise par la recherche de coordonnees
    (core/coord_parser.py) pour ramener toute saisie vers le format commun
    attendu par zoom_to_point/transform_point."""
    crs_src = QgsCoordinateReferenceSystem(crs_epsg)
    crs_dst = QgsCoordinateReferenceSystem('EPSG:4326')
    transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
    point = transform.transform(QgsPointXY(x, y))
    return point.x(), point.y()


def zoom_to_point(iface, lon, lat, scale=1000):
    """Centre/zoome le canevas sur un point WGS84 (lon, lat). Retourne le point transforme."""
    canvas = iface.mapCanvas()
    point = transform_point(iface, lon, lat)
    canvas.setCenter(point)
    canvas.zoomScale(scale)
    canvas.refresh()
    return point


def make_point_rubber(canvas, point, color=VC_TURQUOISE):
    rb = QgsRubberBand(canvas, _point_geom_type())
    rb.setColor(QColor(color))
    rb.setWidth(3)
    rb.setIcon(_circle_icon())
    rb.setIconSize(15)
    rb.addPoint(point)
    return rb


def zoom_to_features(iface, layer_id, fids):
    """Zoome/centre le canevas sur la geometrie combinee des fids, puis les selectionne."""
    if not layer_id or not fids:
        return
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        return
    canvas = iface.mapCanvas()
    combined = QgsGeometry()
    for fid in fids:
        feat = layer.getFeature(fid)
        if feat.hasGeometry():
            if combined.isEmpty():
                combined = QgsGeometry(feat.geometry())
            else:
                combined = combined.combine(feat.geometry())
    if not combined.isEmpty():
        crs_src = layer.crs()
        crs_dst = canvas.mapSettings().destinationCrs()
        if crs_src != crs_dst:
            transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
            combined.transform(transform)
        # Agrandir l'emprise x2 autour du centre : l'objet occupe ~50% de l'ecran
        # au lieu de le remplir entierement.
        try:
            is_point = combined.type() == _point_geom_type()
        except Exception:
            is_point = False
        floor = _point_scale if is_point else MIN_SCALE

        bbox = combined.boundingBox()
        if bbox.isEmpty():
            # Point unique (ou objets confondus) : aucune emprise a cadrer.
            canvas.setCenter(combined.centroid().asPoint())
            canvas.zoomScale(floor)
        else:
            bbox.scale(2.0)
            canvas.setExtent(bbox)
            if canvas.scale() < floor:
                canvas.setCenter(combined.centroid().asPoint())
                canvas.zoomScale(floor)
        canvas.refresh()
    layer.selectByIds(fids)


def make_features_rubber(iface, layer_id, fids, color=COLOR_HIGHLIGHT, max_features=20):
    """Cree un QgsRubberBand mettant en surbrillance jusqu'a max_features entites."""
    if not layer_id or not fids:
        return None
    layer = QgsProject.instance().mapLayer(layer_id)
    if not layer:
        return None
    canvas = iface.mapCanvas()
    rb = QgsRubberBand(canvas, layer.geometryType())
    rb.setColor(QColor(color))
    rb.setWidth(3)
    rb.setFillColor(QColor(255, 0, 255, 40))
    crs_src = layer.crs()
    crs_dst = canvas.mapSettings().destinationCrs()
    transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance()) if crs_src != crs_dst else None
    for fid in fids[:max_features]:
        feat = layer.getFeature(fid)
        if feat.hasGeometry():
            geom = QgsGeometry(feat.geometry())
            if transform:
                geom.transform(transform)
            # La geometrie est deja ramenee au CRS du canevas (transform
            # ci-dessus) : on le redonne explicitement. L'autre surcharge,
            # addGeometry(geom, layer), attend un QgsMapLayer et devient
            # ambigue quand on lui passe None sous PyQt6.
            rb.addGeometry(geom, crs_dst)
    return rb


def clear_rubber(rubber_band):
    """Reset un QgsRubberBand existant. Retourne toujours None (a reassigner par l'appelant)."""
    if rubber_band:
        rubber_band.reset()
    return None
