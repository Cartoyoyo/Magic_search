"""
Compatibilite Qt5 / Qt6 - QGIS 3 et QGIS 4.

QGIS 4 est construit sur Qt 6, ou plusieurs accesseurs des evenements souris
ont change : `QMouseEvent.pos()` et `QMouseEvent.globalPos()` (QPoint entier)
sont remplaces par `position()` et `globalPosition()`, qui renvoient un QPointF
et sont les seuls garantis quand Qt est compile sans les API depreciees.

Le plugin doit continuer de tourner sur QGIS 3.16 (Qt 5), donc plutot que de
choisir une API il interroge l'evenement : `position` n'existe que sous Qt 6,
`pos` existe partout. Ces deux fonctions sont le seul endroit du code ou la
difference est visible.

Utiliser `event_pos` / `event_global_pos` dans tout gestionnaire de souris
(handlers, eventFilter, outils carte) plutot que d'appeler `pos()` ou
`globalPos()` directement.
"""
from qgis.PyQt.QtCore import QT_VERSION_STR

# Vrai sous QGIS 4 (Qt 6), faux sous QGIS 3 (Qt 5). Sert aux quelques enums
# renommees, pas aux evenements souris : ceux-ci passent par les fonctions
# ci-dessous, qui n'ont pas besoin de connaitre la version.
try:
    IS_QT6 = int(QT_VERSION_STR.split('.')[0]) >= 6
except (ValueError, IndexError):  # version exotique : on suppose Qt 5
    IS_QT6 = False


def event_pos(event):
    """Position locale (QPoint) d'un evenement souris, Qt 5 comme Qt 6."""
    position = getattr(event, 'position', None)
    if position is not None:
        return position().toPoint()
    return event.pos()


def event_global_pos(event):
    """Position ecran (QPoint) d'un evenement souris, Qt 5 comme Qt 6."""
    global_position = getattr(event, 'globalPosition', None)
    if global_position is not None:
        return global_position().toPoint()
    return event.globalPos()
