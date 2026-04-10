"""
Web Widget - Interface moderne hybride instanciant HTML/JS via QWebEngineView.
Stylé en TailwindCSS nativement.
"""
import json
import urllib.parse
from qgis.PyQt.QtWidgets import QDockWidget, QVBoxLayout, QWidget, QLabel
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsGeometry
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtGui import QColor

try:
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

if HAS_WEBENGINE:
    class CustomWebPage(QWebEnginePage):
        action_requested = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)

        def acceptNavigationRequest(self, url, nav_type, isMainFrame):
            url_str = url.toString()
            if url_str.startswith("action:"):
                self.action_requested.emit(url_str)
                return False
            if url_str.startswith("data:"):
                return True
            return super().acceptNavigationRequest(url, nav_type, isMainFrame)

class MagicSearchWebWidget(QDockWidget):
    config_requested = pyqtSignal()

    def __init__(self, iface, index_manager, ban_provider, layer_provider, parent=None):
        super().__init__("Magic Search (Web/Tailwind)", parent)
        self._iface = iface
        self._ban_provider = ban_provider
        self._layer_provider = layer_provider

        self._ban_results = []
        self._layer_results = []
        self._rubber_band = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        if not HAS_WEBENGINE:
            lbl = QLabel("Le composant QWebEngine n'est pas disponible sur votre version de QGIS (souvent absent sous Linux natif/minimal).\nVeuillez retourner dans Extension > Magic Search > Config et choisir le style Qt5 ou Maps.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("padding: 20px; color: #b91c1c; font-weight: bold; background: white;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            self.setWidget(main_widget)
            return

        self.web_view = QWebEngineView()
        self.page = CustomWebPage(self)
        self.web_view.setPage(self.page)
        layout.addWidget(self.web_view)
        self.setWidget(main_widget)

        self.page.action_requested.connect(self._handle_web_action)

        html = self._get_html()
        self.web_view.setHtml(html)

        self._ban_provider.results_ready.connect(self._on_ban_results)
        self._layer_provider.results_ready.connect(self._on_layer_results)

    def _handle_web_action(self, url):
        if url.startswith("action:search?q="):
            query = urllib.parse.unquote(url.replace("action:search?q=", ""))
            if len(query) < 2:
                self._ban_results = []
                self._layer_results = []
                self._update_web()
                return
            self._ban_provider.search(query)
            self._layer_provider.search(query)
            
        elif url == "action:config":
            self.config_requested.emit()
            
        elif url.startswith("action:click_ban?idx="):
            idx = int(url.split("=")[-1])
            data = self._ban_results[idx]
            self._zoom_to_ban(data)
            
        elif url.startswith("action:click_layer?g="):
            params = urllib.parse.parse_qs(url.split("?")[-1])
            g = int(params['g'][0])
            m = int(params['m'][0])
            group = self._layer_results[g]
            data = group['matches'][m]
            data['layer_id'] = group['layer_id']
            self._zoom_to_features(data)

    def _on_ban_results(self, results):
        self._ban_results = results
        self._update_web()

    def _on_layer_results(self, results):
        self._layer_results = results
        self._update_web()

    def _update_web(self):
        data = {
            'ban': self._ban_results,
            'layers': self._layer_results
        }
        json_str = json.dumps(data)
        js = f"window.updateResults({json_str});"
        self.web_view.page().runJavaScript(js)

    def _get_html(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #f8fafc; color: #1e293b; font-family: ui-sans-serif, system-ui, sans-serif; overflow-x: hidden; }
        .card { transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s; border: 1px solid #e2e8f0; }
        .card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025); border-color: #0d9488; }
        .scroll-smooth { scroll-behavior: smooth; }
    </style>
</head>
<body class="p-4 scroll-smooth">
    <div class="flex gap-2 mb-4 sticky top-0 bg-[#f8fafc] pt-2 pb-2 z-10 w-full">
        <input type="text" id="searchInput" placeholder="Magic Web Search (Tailwind)..." 
               class="flex-1 p-3 rounded-lg border border-slate-300 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-sm">
        <button onclick="window.location.href='action:config'" class="p-3 rounded-lg bg-white border border-slate-300 shadow-sm hover:bg-slate-50 text-slate-500 transition-colors" title="Configuration">⚙️</button>
    </div>
    
    <div id="results" class="space-y-3 pb-8">
        <p class="text-sm text-slate-400 italic mt-8 text-center animate-pulse">Frappez au moins 2 caractères...</p>
    </div>

    <script>
        const input = document.getElementById('searchInput');
        input.addEventListener('input', (e) => {
            const val = encodeURIComponent(e.target.value);
            window.location.href = 'action:search?q=' + val;
        });

        window.updateResults = function(data) {
            const container = document.getElementById('results');
            container.innerHTML = '';
            
            let hasResults = false;

            if (data.ban && data.ban.length > 0) {
                hasResults = true;
                data.ban.forEach((r, idx) => {
                    const div = document.createElement('div');
                    div.className = "card bg-white p-4 rounded-xl cursor-pointer flex justify-between items-center";
                    div.onclick = () => window.location.href = 'action:click_ban?idx=' + idx;
                    div.innerHTML = `
                        <div class="text-sm font-medium text-slate-700 truncate pr-2">${r.label}</div>
                        <div class="px-2 py-1 bg-teal-50 text-teal-700 text-xs font-extrabold rounded-md shadow-sm border border-teal-100 flex-shrink-0">BAN</div>
                    `;
                    container.appendChild(div);
                });
            }

            if (data.layers && data.layers.length > 0) {
                hasResults = true;
                data.layers.forEach((group, gIdx) => {
                    const tag = group.layer_name + ' | ' + group.field_name;
                    group.matches.forEach((m, mIdx) => {
                        const div = document.createElement('div');
                        div.className = "card bg-white p-4 rounded-xl cursor-pointer flex justify-between items-center";
                        div.onclick = () => window.location.href = `action:click_layer?g=${gIdx}&m=${mIdx}`;
                        
                        let countTxt = m.fids && m.fids.length > 1 ? ` <span class="text-slate-400 font-normal">(${m.fids.length})</span>` : '';
                        
                        div.innerHTML = `
                            <div class="text-sm font-medium text-slate-700 truncate pr-2">${m.original}${countTxt}</div>
                            <div class="px-2 py-1 bg-slate-50 text-slate-600 text-xs font-extrabold rounded-md shadow-sm border border-slate-100 flex-shrink-0">${tag}</div>
                        `;
                        container.appendChild(div);
                    });
                });
            }

            if (!hasResults && input.value.length >= 2) {
                container.innerHTML = '<p class="text-sm text-slate-500 italic text-center py-6">Aucun résultat magique trouvé ✨.</p>';
            } else if (!hasResults) {
                container.innerHTML = '<p class="text-sm text-slate-400 italic mt-8 text-center animate-pulse">Frappez au moins 2 caractères...</p>';
            }
        };
    </script>
</body>
</html>"""

    def _zoom_to_ban(self, data):
        self._clear_rubber_band()
        canvas = self._iface.mapCanvas()
        crs_src = QgsCoordinateReferenceSystem('EPSG:4326')
        crs_dst = canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(crs_src, crs_dst, QgsProject.instance())
        point = transform.transform(QgsPointXY(data['lon'], data['lat']))
        canvas.setCenter(point)
        canvas.zoomScale(2000)
        canvas.refresh()
        self._show_point_rubber(point, canvas)

    def _zoom_to_features(self, data):
        self._clear_rubber_band()
        layer_id = data.get('layer_id')
        fids = data.get('fids', [])
        if not layer_id or not fids: return
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer: return
        canvas = self._iface.mapCanvas()
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
            canvas.setCenter(combined.centroid().asPoint())
            canvas.zoomScale(2000)
            canvas.refresh()
        layer.selectByIds(fids)

    def _show_point_rubber(self, point, canvas):
        try:
            from qgis.core import Qgis as QgisCore
            geom_type = QgisCore.GeometryType.Point
        except AttributeError:
            from qgis.core import QgsWkbTypes
            geom_type = QgsWkbTypes.PointGeometry
        self._rubber_band = QgsRubberBand(canvas, geom_type)
        self._rubber_band.setColor(QColor('#00a096'))
        self._rubber_band.setWidth(3)
        self._rubber_band.setIcon(QgsRubberBand.ICON_CIRCLE)
        self._rubber_band.setIconSize(15)
        self._rubber_band.addPoint(point)

    def _clear_rubber_band(self):
        if self._rubber_band:
            self._rubber_band.reset()
            self._rubber_band = None

    def cleanup(self):
        self._clear_rubber_band()
        if HAS_WEBENGINE:
            self.web_view.deleteLater()

    def set_focus(self):
        if HAS_WEBENGINE:
            self.web_view.page().runJavaScript("document.getElementById('searchInput').focus();")
