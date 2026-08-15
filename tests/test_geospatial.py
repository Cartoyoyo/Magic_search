"""
Tests geospatiaux minimaux pour Magic Search.
Executable hors QGIS (mock des modules qgis/PyQt).
Lancer avec : python -m unittest discover -s tests -v
"""

import unittest
import sys
import os
import types

# --- Mock des modules QGIS pour pouvoir tester hors QGIS ---
def _setup_qgis_mocks():
    """Cree des mocks minimaux pour qgis.PyQt.QtCore et qgis.core."""
    if 'qgis' in sys.modules:
        return  # deja disponible (execution dans QGIS)

    # Module qgis
    qgis_mod = types.ModuleType('qgis')
    # qgis.PyQt
    pyqt_mod = types.ModuleType('qgis.PyQt')
    # qgis.PyQt.QtCore
    qtcore_mod = types.ModuleType('qgis.PyQt.QtCore')

    class FakeQTimer:
        pass
    class FakeQObject:
        pass
    def fake_pyqtSignal(*args, **kwargs):
        return property(lambda self: None)

    qtcore_mod.QTimer = FakeQTimer
    qtcore_mod.QObject = FakeQObject
    qtcore_mod.pyqtSignal = fake_pyqtSignal

    # qgis.core
    core_mod = types.ModuleType('qgis.core')
    class FakeQgsProject:
        @staticmethod
        def instance():
            return FakeQgsProject()
    class FakeQgsVectorLayer:
        pass
    class FakeQgsMessageLog:
        @staticmethod
        def logMessage(*args, **kwargs):
            pass
    class FakeQgis:
        Info = 0
        Warning = 1

    core_mod.QgsProject = FakeQgsProject
    core_mod.QgsVectorLayer = FakeQgsVectorLayer
    core_mod.QgsMessageLog = FakeQgsMessageLog
    core_mod.Qgis = FakeQgis

    sys.modules['qgis'] = qgis_mod
    sys.modules['qgis.PyQt'] = pyqt_mod
    sys.modules['qgis.PyQt.QtCore'] = qtcore_mod
    sys.modules['qgis.core'] = core_mod
    qgis_mod.PyQt = pyqt_mod
    pyqt_mod.QtCore = qtcore_mod
    qgis_mod.core = core_mod

_setup_qgis_mocks()

# Importer via le package du plugin (et non 'core' seul) pour que les imports
# relatifs internes (ex: 'from ..i18n import tr') se resolvent comme dans QGIS.
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(_PLUGIN_DIR))
_PKG = os.path.basename(_PLUGIN_DIR)

_index_manager = __import__(_PKG + '.core.index_manager', fromlist=['*'])
normalize_text = _index_manager.normalize_text
_layer_fingerprint = _index_manager._layer_fingerprint
_get_cache_path = _index_manager._get_cache_path
_index_feature = _index_manager._index_feature
IndexManager = _index_manager.IndexManager


class TestNormalizeText(unittest.TestCase):
    """Tests de la fonction normalize_text."""

    def test_lowercase(self):
        self.assertEqual(normalize_text('HELLO'), 'hello')

    def test_accents_removed(self):
        self.assertEqual(normalize_text('caf\u00e9'), 'cafe')
        self.assertEqual(normalize_text('\u00c9cole'), 'ecole')
        self.assertEqual(normalize_text('no\u00ebl'), 'noel')

    def test_french_accents(self):
        self.assertEqual(normalize_text('R\u00e9publique'), 'republique')
        self.assertEqual(normalize_text('Ch\u00e2teau'), 'chateau')

    def test_non_string_input(self):
        self.assertEqual(normalize_text(42), '42')
        self.assertEqual(normalize_text(3.14), '3.14')
        self.assertEqual(normalize_text(None), 'none')

    def test_empty_string(self):
        self.assertEqual(normalize_text(''), '')

    def test_mixed_case_accents(self):
        self.assertEqual(normalize_text('\u00c9GLISE'), 'eglise')


class TestLayerFingerprint(unittest.TestCase):
    """Tests de _layer_fingerprint."""

    def _make_mock_layer(self, source='/tmp/test.gpkg', count=100, field_names=None):
        if field_names is None:
            field_names = ['id', 'nom']
        class MockField:
            def __init__(self, name):
                self._name = name
            def name(self):
                return self._name
        class MockLayer:
            pass
        layer = MockLayer()
        layer.source = lambda: source
        layer.featureCount = lambda: count
        layer.fields = lambda: [MockField(n) for n in field_names]
        return layer

    def test_fingerprint_is_md5(self):
        fp = _layer_fingerprint(self._make_mock_layer())
        self.assertIsInstance(fp, str)
        self.assertEqual(len(fp), 32)

    def test_fingerprint_changes_with_count(self):
        fp1 = _layer_fingerprint(self._make_mock_layer(count=100))
        fp2 = _layer_fingerprint(self._make_mock_layer(count=200))
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_changes_with_source(self):
        fp1 = _layer_fingerprint(self._make_mock_layer(source='a.gpkg'))
        fp2 = _layer_fingerprint(self._make_mock_layer(source='b.gpkg'))
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_deterministic(self):
        fp1 = _layer_fingerprint(self._make_mock_layer())
        fp2 = _layer_fingerprint(self._make_mock_layer())
        self.assertEqual(fp1, fp2)


class TestIndexFeature(unittest.TestCase):
    """Tests de _index_feature (indexation des valeurs d'un champ)."""

    class MockFeature:
        def __init__(self, values, fid=1):
            self._values = values
            self._fid = fid

        def __getitem__(self, key):
            return self._values[key]

        def id(self):
            return self._fid

    def test_zero_value_is_indexed(self):
        layer_index = {'fields': {}}
        feat = self.MockFeature({'numero': 0})
        _index_feature(feat, ['numero'], layer_index)
        self.assertIn(normalize_text('0'), layer_index['fields']['numero'])

    def test_zero_float_value_is_indexed(self):
        layer_index = {'fields': {}}
        feat = self.MockFeature({'score': 0.0})
        _index_feature(feat, ['score'], layer_index)
        self.assertIn(normalize_text('0.0'), layer_index['fields']['score'])

    def test_empty_string_not_indexed(self):
        layer_index = {'fields': {}}
        feat = self.MockFeature({'nom': ''})
        _index_feature(feat, ['nom'], layer_index)
        self.assertNotIn('nom', layer_index['fields'])

    def test_none_value_not_indexed(self):
        layer_index = {'fields': {}}
        feat = self.MockFeature({'nom': None})
        _index_feature(feat, ['nom'], layer_index)
        self.assertNotIn('nom', layer_index['fields'])


class TestGetCachePath(unittest.TestCase):
    """Tests de _get_cache_path."""

    def test_qgz_project(self):
        result = _get_cache_path('/home/user/projet.qgz')
        self.assertEqual(result, '/home/user/projet_magic_search_cache.gz')

    def test_qgs_project(self):
        result = _get_cache_path('/home/user/mon_projet.qgs')
        self.assertEqual(result, '/home/user/mon_projet_magic_search_cache.gz')

    def test_none_project(self):
        self.assertIsNone(_get_cache_path(None))

    def test_empty_project(self):
        self.assertIsNone(_get_cache_path(''))


class TestIndexSearch(unittest.TestCase):
    """Tests de la methode search de IndexManager."""

    def _make_index(self):
        mgr = IndexManager.__new__(IndexManager)
        mgr._index = {
            'layer_1': {
                'name': 'Communes',
                'fingerprint': 'abc123',
                'fields': {
                    'nom': {
                        normalize_text('Vichy'): {
                            'original': 'Vichy',
                            'fids': [1]
                        },
                        normalize_text('Cusset'): {
                            'original': 'Cusset',
                            'fids': [2]
                        },
                        normalize_text('Bellerive-sur-Allier'): {
                            'original': 'Bellerive-sur-Allier',
                            'fids': [3]
                        },
                    },
                    'code_postal': {
                        normalize_text('03200'): {
                            'original': '03200',
                            'fids': [1, 3]
                        },
                        normalize_text('03300'): {
                            'original': '03300',
                            'fids': [2]
                        },
                    }
                }
            }
        }
        return mgr

    def test_search_exact(self):
        mgr = self._make_index()
        results = mgr.search('vichy')
        self.assertTrue(len(results) > 0)
        originals = [m['original'] for r in results for m in r['matches']]
        self.assertIn('Vichy', originals)

    def test_search_partial(self):
        mgr = self._make_index()
        results = mgr.search('bell')
        originals = [m['original'] for r in results for m in r['matches']]
        self.assertTrue(any('Bellerive' in o for o in originals))

    def test_search_too_short(self):
        mgr = self._make_index()
        self.assertEqual(mgr.search('v'), [])

    def test_search_empty(self):
        mgr = self._make_index()
        self.assertEqual(mgr.search(''), [])

    def test_search_no_match(self):
        mgr = self._make_index()
        self.assertEqual(mgr.search('zzzzz'), [])

    def test_search_postal_code(self):
        mgr = self._make_index()
        results = mgr.search('032')
        self.assertTrue(len(results) > 0)

    def test_search_returns_structure(self):
        mgr = self._make_index()
        results = mgr.search('vichy')
        r = results[0]
        self.assertEqual(r['layer_id'], 'layer_1')
        self.assertEqual(r['layer_name'], 'Communes')
        self.assertIn('field_name', r)
        self.assertIn('matches', r)
        self.assertIn('total_matches', r)

    def test_search_case_insensitive(self):
        mgr = self._make_index()
        r1 = mgr.search('VICHY')
        r2 = mgr.search('vichy')
        self.assertEqual(len(r1), len(r2))

    def test_search_max_per_field(self):
        mgr = self._make_index()
        results = mgr.search('03', max_per_field=1)
        for r in results:
            self.assertLessEqual(len(r['matches']), 1)


if __name__ == '__main__':
    unittest.main()
