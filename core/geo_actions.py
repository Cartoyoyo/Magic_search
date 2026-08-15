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
        return Qgis.GeometryType.Point
    except AttributeError:
        from qgis.core import QgsWkbTypes
        return QgsWkbTypes.PointGeometry


def transform_point(iface, lon, lat):
    """Transforme un point WGS84 (lon, lat) vers le CRS du canevas."""
    canvas = iface.mapCanvas()
    crs_src = QgsCoordinateReferenceSystem('EPSG:4326')
    crs_dst = canvas.mapSettings().destinationCrs()
    transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
    return transform.transform(QgsPointXY(lon, lat))


def zoom_to_point(iface, lon, lat, scale=2000):
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
    rb.setIcon(QgsRubberBand.ICON_CIRCLE)
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
        canvas.setExtent(combined.boundingBox())
        if canvas.scale() < 2000:
            canvas.setCenter(combined.centroid().asPoint())
            canvas.zoomScale(2000)
        else:
            # Ajouter 10% de marge pour ne pas que l'objet touche les bords
            canvas.zoomScale(canvas.scale() * 1.1)
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
            rb.addGeometry(geom, None)
    return rb


def clear_rubber(rubber_band):
    """Reset un QgsRubberBand existant. Retourne toujours None (a reassigner par l'appelant)."""
    if rubber_band:
        rubber_band.reset()
    return None
