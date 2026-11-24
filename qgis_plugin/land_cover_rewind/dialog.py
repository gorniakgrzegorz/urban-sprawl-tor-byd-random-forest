"""Dialog for the Land Cover Rewind plugin (UI built in code, no .ui file).

Bilingual (Polish / English, following the QGIS locale), with automatic detection
of a working Python interpreter and of the landcoverrewind command-line tool, an
option to install the Python dependencies, and three ways to give the area of
interest: a polygon layer, a rectangle drawn on the map, or a vector file.
"""
import glob
import math
import os
import subprocess
import sys
import tempfile

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QGridLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox, QDoubleSpinBox,
    QSpinBox, QProgressBar, QPlainTextEdit, QFileDialog, QDialogButtonBox,
    QRadioButton, QButtonGroup, QWidget,
)
from qgis.core import (
    QgsProject, QgsWkbTypes, QgsRasterLayer, QgsVectorLayer,
    QgsVectorFileWriter, QgsCoordinateTransformContext, QgsApplication, QgsSettings,
    QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
)

from . import core, styling
from .task import RunTask
from .maptool import RectangleMapTool

SETTINGS = "land_cover_rewind"
CONTACT = "ggorniak@doktorant.umk.pl"

# -- translations ------------------------------------------------------------
STR = {
    "pl": {
        "title": "Land Cover Rewind",
        "intro": ("Odtwarza mapy zabudowy i pokrycia terenu z archiwum Landsat dla wskazanego "
                  "obszaru. Wskaż obszar, wybierz lata i kliknij „Uruchom”. Wyniki pojawią się "
                  "jako warstwy rastrowe na mapie."),
        "grp_area": "Obszar zainteresowania",
        "opt_layer": "Z warstwy poligonowej w projekcie",
        "opt_draw": "Narysuj prostokąt na mapie",
        "opt_file": "Z pliku wektorowego",
        "sel_only": "Tylko zaznaczone obiekty",
        "draw_btn": "Narysuj prostokąt na mapie…",
        "draw_none": "Nie narysowano jeszcze obszaru.",
        "draw_done": "Narysowany obszar: {w:.1f} × {h:.1f} km.",
        "file_ph": "plik GPKG / GeoJSON / SHP z poligonem obszaru",
        "browse": "Przeglądaj…",
        "grp_params": "Parametry",
        "epochs_lbl": "Lata (epoki):",
        "epochs_tip": "Zaznacz lata, dla których mają powstać mapy (od 1985).",
        "threshold_lbl": "Próg zabudowy:",
        "threshold_tip": "Wyżej = ostrożniej klasyfikuje zabudowę (mniej, ale pewniej).",
        "cloud_lbl": "Maks. zachmurzenie sceny:",
        "crs_lbl": "Układ współrzędnych:",
        "crs_ph": "opcjonalnie, metryczny, np. EPSG:2180",
        "grp_backend": "Silnik obliczeń (landcoverrewind)",
        "python_lbl": "Python:",
        "python_ph": "interpreter Pythona z pakietem landcoverrewind",
        "cli_lbl": "Narzędzie:",
        "cli_ph": "ścieżka do landcoverrewind_cli.py (wykrywana automatycznie)",
        "out_lbl": "Folder wyników:",
        "out_ph": "domyślnie: folder tymczasowy",
        "detect_btn": "Wykryj automatycznie",
        "check_btn": "Sprawdź",
        "install_btn": "Zainstaluj zależności",
        "run_btn": "Uruchom",
        "cancel_btn": "Przerwij",
        "close_btn": "Zamknij",
        "st_checking": "Sprawdzam silnik obliczeń…",
        "st_ok": "Gotowe: Python i pakiet landcoverrewind wykryte.",
        "st_no_python": "Nie znaleziono Pythona. Wskaż go ręcznie przyciskiem „Przeglądaj”.",
        "st_no_cli": "Nie znaleziono landcoverrewind_cli.py. Wskaż plik przyciskiem „Przeglądaj”.",
        "st_missing": "Brakuje pakietu lub zależności. Kliknij „Zainstaluj zależności”.",
        "st_installing": "Instaluję zależności (to może potrwać kilka minut)…",
        "st_installed": "Zależności zainstalowane. Sprawdzam ponownie…",
        "st_install_fail": "Instalacja się nie powiodła — zobacz dziennik poniżej.",
        "e_no_area": "Wskaż obszar: wybierz warstwę, narysuj prostokąt lub wskaż plik.",
        "e_no_layer": "W projekcie nie ma warstwy poligonowej. Dodaj ją albo narysuj prostokąt.",
        "e_sel_empty": "Zaznaczono opcję „tylko zaznaczone obiekty”, ale nic nie jest zaznaczone.",
        "e_no_drawn": "Najpierw narysuj prostokąt na mapie.",
        "e_file_missing": "Nie znaleziono pliku obszaru: {p}",
        "e_no_python": "Ustaw interpreter Pythona dla landcoverrewind.",
        "e_no_cli": "Ustaw poprawną ścieżkę do landcoverrewind_cli.py.",
        "e_export": "Nie udało się wyeksportować warstwy obszaru: {e}",
        "e_busy": "Obliczenia już trwają.",
        "e_busy_install": "Trwa instalacja zależności — poczekaj na jej zakończenie.",
        "msg_running": "Uruchamiam obliczenia…",
        "msg_done": "Gotowe. Dodano warstw wynikowych: {n}.",
        "msg_none": "Obliczenia zakończone, ale nie znaleziono warstw wynikowych.",
        "msg_cancel": "Obliczenia przerwane lub zakończone błędem.",
        "draw_tip": "Kliknij i przeciągnij na mapie, aby narysować prostokątny obszar.",
    },
    "en": {
        "title": "Land Cover Rewind",
        "intro": ("Reconstructs built-up and land-cover maps from the Landsat archive for an area "
                  "you choose. Pick the area, choose the years and click “Run”. Results are added "
                  "to the map as raster layers."),
        "grp_area": "Area of interest",
        "opt_layer": "From a polygon layer in the project",
        "opt_draw": "Draw a rectangle on the map",
        "opt_file": "From a vector file",
        "sel_only": "Selected features only",
        "draw_btn": "Draw a rectangle on the map…",
        "draw_none": "No area drawn yet.",
        "draw_done": "Drawn area: {w:.1f} × {h:.1f} km.",
        "file_ph": "GPKG / GeoJSON / SHP file with the area polygon",
        "browse": "Browse…",
        "grp_params": "Parameters",
        "epochs_lbl": "Years (epochs):",
        "epochs_tip": "Tick the years you want maps for (from 1985).",
        "threshold_lbl": "Built-up threshold:",
        "threshold_tip": "Higher = more cautious about calling a pixel built-up.",
        "cloud_lbl": "Max scene cloud:",
        "crs_lbl": "Coordinate system:",
        "crs_ph": "optional, metric, e.g. EPSG:2180",
        "grp_backend": "Processing backend (landcoverrewind)",
        "python_lbl": "Python:",
        "python_ph": "Python interpreter with the landcoverrewind package",
        "cli_lbl": "Tool:",
        "cli_ph": "path to landcoverrewind_cli.py (detected automatically)",
        "out_lbl": "Output folder:",
        "out_ph": "default: a temporary folder",
        "detect_btn": "Detect automatically",
        "check_btn": "Check",
        "install_btn": "Install dependencies",
        "run_btn": "Run",
        "cancel_btn": "Cancel",
        "close_btn": "Close",
        "st_checking": "Checking the processing backend…",
        "st_ok": "Ready: Python and the landcoverrewind package were found.",
        "st_no_python": "No Python found. Set it manually with “Browse”.",
        "st_no_cli": "landcoverrewind_cli.py not found. Set the file with “Browse”.",
        "st_missing": "The package or its dependencies are missing. Click “Install dependencies”.",
        "st_installing": "Installing dependencies (this can take a few minutes)…",
        "st_installed": "Dependencies installed. Re-checking…",
        "st_install_fail": "Installation failed — see the log below.",
        "e_no_area": "Choose an area: pick a layer, draw a rectangle, or select a file.",
        "e_no_layer": "There is no polygon layer in the project. Add one or draw a rectangle.",
        "e_sel_empty": "“Selected features only” is on, but nothing is selected.",
        "e_no_drawn": "Draw a rectangle on the map first.",
        "e_file_missing": "Area file not found: {p}",
        "e_no_python": "Set the Python interpreter for landcoverrewind.",
        "e_no_cli": "Set a valid path to landcoverrewind_cli.py.",
        "e_export": "Could not export the area layer: {e}",
        "e_busy": "A run is already in progress.",
        "e_busy_install": "Dependencies are installing — wait for that to finish.",
        "msg_running": "Starting the run…",
        "msg_done": "Done. Result layers added: {n}.",
        "msg_none": "The run finished but no result layers were found.",
        "msg_cancel": "The run was cancelled or failed.",
        "draw_tip": "Click and drag on the map to draw a rectangular area.",
    },
}


def _plugin_locale():
    """'pl' when the QGIS UI locale is Polish, otherwise 'en'."""
    loc = QgsSettings().value("locale/userLocale", "en")
    return "pl" if str(loc or "").lower().startswith("pl") else "en"


class LandCoverRewindDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._lang = _plugin_locale()
        self.task = None
        self.install_task = None
        self._tmpdir = None
        self._drawn_rect = None          # QgsRectangle in canvas CRS
        self._drawn_crs = None           # QgsCoordinateReferenceSystem
        self._prev_tool = None
        self._rect_tool = None
        self.setWindowTitle(self.T("title"))
        self.setMinimumWidth(600)
        self._build_ui()
        self._load_settings()
        self._refresh_layers()
        self._update_area_mode()

    def T(self, key, **kw):
        s = STR[self._lang].get(key) or STR["en"].get(key, key)
        return s.format(**kw) if kw else s

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(self.T("intro"))
        intro.setWordWrap(True)
        root.addWidget(intro)

        # --- area of interest ---
        area = QGroupBox(self.T("grp_area"))
        av = QVBoxLayout(area)
        self.area_group = QButtonGroup(self)
        self.rb_layer = QRadioButton(self.T("opt_layer"))
        self.rb_draw = QRadioButton(self.T("opt_draw"))
        self.rb_file = QRadioButton(self.T("opt_file"))
        self.rb_layer.setChecked(True)
        for rb in (self.rb_layer, self.rb_draw, self.rb_file):
            self.area_group.addButton(rb)
            av.addWidget(rb)
            rb.toggled.connect(self._update_area_mode)

        # layer sub-panel
        self.panel_layer = QWidget()
        lf = QFormLayout(self.panel_layer)
        lf.setContentsMargins(20, 0, 0, 0)
        self.layer_combo = QComboBox()
        lf.addRow(self.T("grp_area") + ":", self.layer_combo)
        self.selected_only = QCheckBox(self.T("sel_only"))
        lf.addRow("", self.selected_only)
        av.addWidget(self.panel_layer)

        # draw sub-panel
        self.panel_draw = QWidget()
        df = QHBoxLayout(self.panel_draw)
        df.setContentsMargins(20, 0, 0, 0)
        self.draw_btn = QPushButton(self.T("draw_btn"))
        self.draw_btn.setToolTip(self.T("draw_tip"))
        self.draw_btn.clicked.connect(self._draw_on_map)
        self.draw_lbl = QLabel(self.T("draw_none"))
        df.addWidget(self.draw_btn)
        df.addWidget(self.draw_lbl, 1)
        av.addWidget(self.panel_draw)

        # file sub-panel
        self.panel_file = QWidget()
        ff = QHBoxLayout(self.panel_file)
        ff.setContentsMargins(20, 0, 0, 0)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText(self.T("file_ph"))
        fb = QPushButton(self.T("browse"))
        fb.clicked.connect(self._browse_aoi)
        ff.addWidget(self.file_edit)
        ff.addWidget(fb)
        av.addWidget(self.panel_file)
        root.addWidget(area)

        # --- parameters ---
        params = QGroupBox(self.T("grp_params"))
        pf = QFormLayout(params)
        ep_box = QGridLayout()
        self.epoch_checks = {}
        for i, y in enumerate(core.EPOCHS):
            cb = QCheckBox(str(y))
            cb.setChecked(True)
            self.epoch_checks[y] = cb
            ep_box.addWidget(cb, i // 5, i % 5)
        ep_lbl = QLabel(self.T("epochs_lbl"))
        ep_lbl.setToolTip(self.T("epochs_tip"))
        pf.addRow(ep_lbl, ep_box)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.05, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.65)
        self.threshold.setToolTip(self.T("threshold_tip"))
        pf.addRow(self.T("threshold_lbl"), self.threshold)

        self.max_cloud = QSpinBox()
        self.max_cloud.setRange(1, 100)
        self.max_cloud.setValue(70)
        self.max_cloud.setSuffix(" %")
        pf.addRow(self.T("cloud_lbl"), self.max_cloud)

        self.crs_edit = QLineEdit()
        self.crs_edit.setPlaceholderText(self.T("crs_ph"))
        pf.addRow(self.T("crs_lbl"), self.crs_edit)
        root.addWidget(params)

        # --- backend ---
        run_env = QGroupBox(self.T("grp_backend"))
        rf = QFormLayout(run_env)
        interp_row = QHBoxLayout()
        self.interp_edit = QLineEdit()
        self.interp_edit.setPlaceholderText(self.T("python_ph"))
        ib = QPushButton(self.T("browse"))
        ib.clicked.connect(lambda: self._browse_into(self.interp_edit))
        interp_row.addWidget(self.interp_edit)
        interp_row.addWidget(ib)
        rf.addRow(self.T("python_lbl"), interp_row)

        cli_row = QHBoxLayout()
        self.cli_edit = QLineEdit()
        self.cli_edit.setPlaceholderText(self.T("cli_ph"))
        cb = QPushButton(self.T("browse"))
        cb.clicked.connect(lambda: self._browse_into(self.cli_edit, "Python (*.py)"))
        cli_row.addWidget(self.cli_edit)
        cli_row.addWidget(cb)
        rf.addRow(self.T("cli_lbl"), cli_row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText(self.T("out_ph"))
        ob = QPushButton(self.T("browse"))
        ob.clicked.connect(self._browse_out)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(ob)
        rf.addRow(self.T("out_lbl"), out_row)

        tools_row = QHBoxLayout()
        self.detect_btn = QPushButton(self.T("detect_btn"))
        self.detect_btn.clicked.connect(self._autodetect)
        self.check_btn = QPushButton(self.T("check_btn"))
        self.check_btn.clicked.connect(self._check_backend)
        self.install_btn = QPushButton(self.T("install_btn"))
        self.install_btn.clicked.connect(self._install_deps)
        self.install_btn.setEnabled(False)
        tools_row.addWidget(self.detect_btn)
        tools_row.addWidget(self.check_btn)
        tools_row.addWidget(self.install_btn)
        tools_row.addStretch(1)
        rf.addRow("", tools_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        rf.addRow("", self.status_lbl)
        root.addWidget(run_env)

        # --- progress + log ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(120)
        root.addWidget(self.log)

        # --- buttons ---
        self.buttons = QDialogButtonBox()
        self.run_btn = self.buttons.addButton(self.T("run_btn"), QDialogButtonBox.AcceptRole)
        self.cancel_btn = self.buttons.addButton(self.T("cancel_btn"), QDialogButtonBox.ResetRole)
        self.cancel_btn.setEnabled(False)
        self.close_btn = self.buttons.addButton(QDialogButtonBox.Close)
        self.close_btn.setText(self.T("close_btn"))
        self.run_btn.clicked.connect(self.start_run)
        self.cancel_btn.clicked.connect(self.cancel_run)
        self.close_btn.clicked.connect(self.close)
        root.addWidget(self.buttons)

        # --- tiny copyright footer linked to e-mail ---
        foot_row = QHBoxLayout()
        foot_row.addStretch(1)
        foot = QLabel('<a style="color:#888;text-decoration:none" '
                      'href="mailto:%s">© Grzegorz Górniak</a>' % CONTACT)
        foot.setTextFormat(Qt.RichText)
        foot.setOpenExternalLinks(True)
        foot.setToolTip(CONTACT)
        ff2 = foot.font()
        ff2.setPointSize(max(7, ff2.pointSize() - 2))
        foot.setFont(ff2)
        foot_row.addWidget(foot)
        root.addLayout(foot_row)

    # ---------- area mode ----------
    def _update_area_mode(self, *args):
        self.panel_layer.setVisible(self.rb_layer.isChecked())
        self.panel_draw.setVisible(self.rb_draw.isChecked())
        self.panel_file.setVisible(self.rb_file.isChecked())

    def _refresh_layers(self):
        self.layer_combo.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if (isinstance(lyr, QgsVectorLayer) and lyr.isValid()
                    and lyr.geometryType() == QgsWkbTypes.PolygonGeometry):
                self.layer_combo.addItem(lyr.name(), lyr.id())

    # ---------- draw on map ----------
    def _draw_on_map(self):
        canvas = self.iface.mapCanvas()
        self._prev_tool = canvas.mapTool()
        self._rect_tool = RectangleMapTool(canvas)
        self._rect_tool.finished.connect(self._on_rectangle)
        canvas.setMapTool(self._rect_tool)
        self.hide()

    def _on_rectangle(self, rect):
        canvas = self.iface.mapCanvas()
        self._drawn_rect = QgsRectangle(rect)
        self._drawn_crs = canvas.mapSettings().destinationCrs()
        # approximate size in km, via a metric transform of the centre
        try:
            km_rect = self._rect_in_4326(self._drawn_rect, self._drawn_crs)
            mid_lat = (km_rect.yMinimum() + km_rect.yMaximum()) / 2
            w_km = km_rect.width() * 111.32 * max(0.1, abs(math.cos(math.radians(mid_lat))))
            h_km = km_rect.height() * 110.57
            self.draw_lbl.setText(self.T("draw_done", w=w_km, h=h_km))
        except Exception:
            self.draw_lbl.setText(self.T("draw_none"))
        if self._prev_tool is not None:
            canvas.setMapTool(self._prev_tool)
        self.show()
        self.raise_()
        self.activateWindow()

    def _rect_in_4326(self, rect, src_crs):
        dst = QgsCoordinateReferenceSystem("EPSG:4326")
        if src_crs is None or not src_crs.isValid() or src_crs == dst:
            return QgsRectangle(rect)
        tr = QgsCoordinateTransform(src_crs, dst, QgsProject.instance())
        return tr.transformBoundingBox(rect)

    # ---------- browse ----------
    def _browse_aoi(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.T("opt_file"), "", "Vector (*.gpkg *.geojson *.json *.shp);;All files (*)")
        if path:
            self.file_edit.setText(path)
            self.rb_file.setChecked(True)

    def _browse_into(self, edit, flt="All files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, self.T("browse"), edit.text() or "", flt)
        if path:
            edit.setText(path)

    def _browse_out(self):
        path = QFileDialog.getExistingDirectory(self, self.T("out_lbl"), self.out_edit.text() or "")
        if path:
            self.out_edit.setText(path)

    # ---------- settings & detection ----------
    def _load_settings(self):
        s = QgsSettings()
        interp = s.value(f"{SETTINGS}/python", "")
        cli = s.value(f"{SETTINGS}/cli", "")
        if not interp:
            interp = self._detect_python() or (sys.executable or "python3")
        if not cli:
            cli = self._detect_cli() or ""
        self.interp_edit.setText(interp)
        self.cli_edit.setText(cli)

    def _save_settings(self):
        s = QgsSettings()
        s.setValue(f"{SETTINGS}/python", self.interp_edit.text().strip())
        s.setValue(f"{SETTINGS}/cli", self.cli_edit.text().strip())

    def _detect_python(self):
        """Best-guess Python path without running anything heavy."""
        import shutil
        cands = [QgsSettings().value(f"{SETTINGS}/python", "")]
        for n in ("python3", "python", "py"):
            cands.append(shutil.which(n))
        cands.append(sys.executable)
        for pat in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\python.exe"),
                    os.path.expandvars(r"%USERPROFILE%\anaconda3\python.exe"),
                    os.path.expandvars(r"%USERPROFILE%\miniconda3\python.exe"),
                    r"C:\Python3*\python.exe"):
            cands.extend(sorted(glob.glob(pat)))
        cands = core.dedupe(cands)
        return cands[0] if cands else ""

    def _detect_cli(self):
        here = os.path.dirname(os.path.abspath(__file__))
        roots = [os.path.dirname(here), os.path.dirname(os.path.dirname(here)),
                 os.path.expanduser("~")]
        for sub in ("Documents", "Downloads", "Desktop", os.path.join("Documents", "GitHub")):
            roots.append(os.path.join(os.path.expanduser("~"), sub))
        return core.find_cli(roots) or ""

    def _autodetect(self):
        self.interp_edit.setText(self._detect_python() or self.interp_edit.text())
        self.cli_edit.setText(self._detect_cli() or self.cli_edit.text())
        self._check_backend()

    def _backend_env(self):
        """Environment that makes `import landcoverrewind` work from the CLI folder."""
        cli = self.cli_edit.text().strip()
        d = core.project_dir(cli)
        if not d:
            return None
        prev = os.environ.get("PYTHONPATH", "")
        return {"PYTHONPATH": d + (os.pathsep + prev if prev else "")}

    def _check_backend(self):
        interp = self.interp_edit.text().strip()
        cli = self.cli_edit.text().strip()
        self.install_btn.setEnabled(False)
        if not interp:
            self.status_lbl.setText(self.T("st_no_python"))
            return False
        if not cli or not os.path.isfile(cli):
            self.status_lbl.setText(self.T("st_no_cli"))
            return False
        self.status_lbl.setText(self.T("st_checking"))
        QApplication_processEvents()
        env = dict(os.environ)
        be = self._backend_env()
        if be:
            env.update(be)
        probe = ("import landcoverrewind, geopandas, rasterio, sklearn, odc.geo, "
                 "odc.stac, pystac_client, planetary_computer, pyproj, shapely")
        try:
            out = subprocess.run([interp, "-c", probe], capture_output=True, text=True,
                                 timeout=60, env=env)
        except Exception as e:
            self.status_lbl.setText(str(e))
            return False
        if out.returncode == 0:
            self.status_lbl.setText(self.T("st_ok"))
            self._save_settings()
            return True
        self.status_lbl.setText(self.T("st_missing"))
        self.install_btn.setEnabled(True)
        if out.stderr:
            self.log.appendPlainText(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "")
        return False

    def _install_deps(self):
        from qgis.core import Qgis
        if self.install_task is not None:
            self._message(self.T("e_busy_install"), Qgis.Warning)
            return
        if self.task is not None:
            self._message(self.T("e_busy"), Qgis.Warning)
            return
        interp = self.interp_edit.text().strip()
        cli = self.cli_edit.text().strip()
        req = core.requirements_path(cli)
        if not interp:
            self._message(self.T("e_no_python"), Qgis.Critical)
            return
        if req and os.path.isfile(req):
            cmd = [interp, "-m", "pip", "install", "-r", req]
        else:
            cmd = [interp, "-m", "pip", "install",
                   "geopandas", "rasterio", "scikit-learn>=1.9,<1.10", "odc-geo", "odc-stac",
                   "pystac-client", "planetary-computer", "pyproj", "shapely", "scipy",
                   "xarray", "dask", "pandas", "numpy", "matplotlib"]
        self.status_lbl.setText(self.T("st_installing"))
        self.log.appendPlainText("$ " + " ".join(cmd))
        self.install_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        tmp = tempfile.mkdtemp(prefix="lcr_pip_")
        self.install_task = RunTask(cmd, tmp, [], cwd=core.project_dir(cli) or None,
                                    description="Land Cover Rewind: install dependencies")
        self.install_task.progressChanged.connect(lambda v: None)
        self.install_task.taskCompleted.connect(self._after_install_ok)
        self.install_task.taskTerminated.connect(self._after_install_fail)
        QgsApplication.taskManager().addTask(self.install_task)

    def _after_install_ok(self):
        if self.install_task is not None:
            self.log.setPlainText(self.install_task.log_text())
        self.install_task = None
        self.run_btn.setEnabled(True)
        self.status_lbl.setText(self.T("st_installed"))
        self._check_backend()

    def _after_install_fail(self):
        from qgis.core import Qgis
        if self.install_task is not None:
            self.log.setPlainText(self.install_task.log_text())
        err = self.install_task.error if self.install_task else ""
        self.install_task = None
        self.run_btn.setEnabled(True)
        self.install_btn.setEnabled(True)
        self.status_lbl.setText(self.T("st_install_fail"))
        if err:
            self._message(err, Qgis.Warning)

    # ---------- helpers ----------
    def _message(self, text, level):
        self.iface.messageBar().pushMessage(self.T("title"), text, level=level)

    def _chosen_epochs(self):
        return [y for y, cb in self.epoch_checks.items() if cb.isChecked()]

    def _export_layer(self, layer, selected_only, folder):
        path = os.path.join(folder, "aoi.gpkg")
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.onlySelectedFeatures = bool(selected_only)
        res = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, QgsCoordinateTransformContext(), opts)
        if res[0] != QgsVectorFileWriter.NoError:
            raise RuntimeError(self.T("e_export", e=res[1]))
        return path

    def _write_drawn_aoi(self, folder):
        rect = self._rect_in_4326(self._drawn_rect, self._drawn_crs)
        gj = core.bbox_geojson(rect.xMinimum(), rect.yMinimum(),
                               rect.xMaximum(), rect.yMaximum())
        path = os.path.join(folder, "aoi.geojson")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(gj)
        return path

    def _resolve_aoi(self, out_dir):
        """Return the AOI file path for the selected mode, or raise ValueError."""
        if self.rb_file.isChecked():
            aoi = self.file_edit.text().strip()
            if not aoi:
                raise ValueError(self.T("e_no_area"))
            if not os.path.isfile(aoi):
                raise ValueError(self.T("e_file_missing", p=aoi))
            return aoi
        if self.rb_draw.isChecked():
            if self._drawn_rect is None:
                raise ValueError(self.T("e_no_drawn"))
            return self._write_drawn_aoi(out_dir)
        # layer mode
        lid = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(lid) if lid else None
        if layer is None:
            raise ValueError(self.T("e_no_layer"))
        if self.selected_only.isChecked() and layer.selectedFeatureCount() == 0:
            raise ValueError(self.T("e_sel_empty"))
        return self._export_layer(layer, self.selected_only.isChecked(), out_dir)

    # ---------- run ----------
    def start_run(self):
        from qgis.core import Qgis
        if self.task is not None:
            self._message(self.T("e_busy"), Qgis.Warning)
            return
        if self.install_task is not None:
            self._message(self.T("e_busy_install"), Qgis.Warning)
            return
        try:
            epochs = self._chosen_epochs()
            core.validate_params(epochs, self.threshold.value(), self.max_cloud.value(), "pretrained")

            interp = self.interp_edit.text().strip()
            cli = self.cli_edit.text().strip()
            if not interp:
                raise ValueError(self.T("e_no_python"))
            if not cli or not os.path.isfile(cli):
                raise ValueError(self.T("e_no_cli"))

            out_dir = self.out_edit.text().strip()
            if not out_dir:
                self._tmpdir = tempfile.mkdtemp(prefix="lcr_")
                out_dir = self._tmpdir
            os.makedirs(out_dir, exist_ok=True)

            aoi = self._resolve_aoi(out_dir)
            crs = self.crs_edit.text().strip() or None
            cmd = core.build_command(interp, cli, aoi, out_dir, epochs, "pretrained",
                                     self.threshold.value(), self.max_cloud.value(), crs,
                                     lang=self._lang)
        except (ValueError, RuntimeError) as e:
            self._message(str(e), Qgis.Critical)
            return

        self._out_dir = out_dir
        self._epochs = epochs
        self.log.clear()
        self.log.appendPlainText("$ " + " ".join(cmd))
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._save_settings()
        self._message(self.T("msg_running"), Qgis.Info)

        self.task = RunTask(cmd, out_dir, epochs, cwd=core.project_dir(cli) or None,
                            env=self._backend_env())
        self.task.progressChanged.connect(lambda v: self.progress.setValue(int(v)))
        self.task.taskCompleted.connect(self._on_completed)
        self.task.taskTerminated.connect(self._on_terminated)
        QgsApplication.taskManager().addTask(self.task)

    def cancel_run(self):
        if self.task is not None:
            self.task.cancel()

    def _finish_common(self):
        if self.task is not None:
            self.log.setPlainText(self.task.log_text())
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_completed(self):
        from qgis.core import Qgis
        self._finish_common()
        layers = core.result_layers(self._out_dir, self._epochs)
        added = 0
        extent = QgsRectangle()
        extent.setMinimal()
        canvas = self.iface.mapCanvas()
        dst = canvas.mapSettings().destinationCrs()
        for info in layers:
            rl = QgsRasterLayer(info["path"], info["title"])
            if not rl.isValid():
                continue
            QgsProject.instance().addMapLayer(rl)
            styling.style_layer(rl, info["kind"], self._epochs)
            try:
                ext = rl.extent()
                if rl.crs().isValid() and dst.isValid() and rl.crs() != dst:
                    ext = QgsCoordinateTransform(rl.crs(), dst, QgsProject.instance()).transformBoundingBox(ext)
                extent.combineExtentWith(ext)
            except Exception:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage("Could not combine layer extent for zoom", "Land Cover Rewind", Qgis.Info)
            added += 1
        if added and not extent.isEmpty():
            canvas.setExtent(extent)
            canvas.refresh()
        if added:
            self._message(self.T("msg_done", n=added), Qgis.Success)
        else:
            self._message(self.T("msg_none"), Qgis.Warning)
        self.task = None

    def _on_terminated(self):
        from qgis.core import Qgis
        self._finish_common()
        err = (self.task.error if self.task else "") or self.T("msg_cancel")
        self._message(err, Qgis.Warning)
        self.task = None

    def closeEvent(self, event):
        if self.task is not None:
            self.task.cancel()
        if self._rect_tool is not None:
            try:
                canvas = self.iface.mapCanvas()
                if self._prev_tool is not None:
                    canvas.setMapTool(self._prev_tool)
                else:
                    canvas.unsetMapTool(self._rect_tool)
            except Exception:
                from qgis.core import QgsMessageLog, Qgis
                QgsMessageLog.logMessage("Could not restore previous map tool", "Land Cover Rewind", Qgis.Info)
        super().closeEvent(event)


def QApplication_processEvents():
    """Let the status label repaint during a short synchronous check."""
    from qgis.PyQt.QtWidgets import QApplication
    QApplication.processEvents()
