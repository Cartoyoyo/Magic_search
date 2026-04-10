"""
Layer Provider - Recherche dans les couches locales via l'IndexManager.
"""

from qgis.PyQt.QtCore import QObject, pyqtSignal


class LayerProvider(QObject):
    """Fournisseur de resultats couches locales (via index)."""

    results_ready = pyqtSignal(list)

    def __init__(self, index_manager, parent=None):
        super().__init__(parent)
        self._index_manager = index_manager

    def search(self, query, max_per_field=5):
        """Recherche dans l'index des couches."""
        if not query or len(query) < 2:
            self.results_ready.emit([])
            return

        results = self._index_manager.search(query, max_per_field=max_per_field)
        self.results_ready.emit(results)
