"""Dialog for the Land Cover Rewind plugin (UI built in code, no .ui file)."""
import os
import sys
import tempfile

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QGridLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox, QDoubleSpinBox,
    QSpinBox, QProgressBar, QPlainTextEdit, QFileDialog, QDialogButtonBox,
)
from qgis.core import (
    QgsProject, QgsWkbTypes, QgsRasterLayer, QgsVectorLayer,
    QgsVectorFileWriter, QgsCoordinateTransformContext, QgsApplication, QgsSettings,
    QgsRectangle,
)

from . import core, styling
from .task import RunTask

SETTINGS = "land_cover_rewind"


class LandCoverRewindDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.task = None
        self._tmpdir = None
        self.setWindowTitle("Land Cover Rewind 1985-2025")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_settings()
        self._refresh_layers()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        area = QGroupBox("Area of interest")
        af = QFormLayout(area)
        self.layer_combo = QComboBox()
        af.addRow("Polygon layer:", self.layer_combo)
        self.selected_only = QCheckBox("Selected features only")
        af.addRow("", self.selected_only)
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("or a GPKG / GeoJSON / SHP file (overrides the layer)")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_aoi)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse)
        af.addRow("From file:", file_row)
        root.addWidget(area)

        params = QGroupBox("Parameters")
        pf = QFormLayout(params)
        ep_box = QGridLayout()
        self.epoch_checks = {}
        for i, y in enumerate(core.EPOCHS):
            cb = QCheckBox(str(y))
            cb.setChecked(True)
            self.epoch_checks[y] = cb
            ep_box.addWidget(cb, i // 5, i % 5)
        pf.addRow("Epochs:", ep_box)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Pretrained (Torun/Bydgoszcz 2025 model)", "pretrained")
        self.mode_combo.addItem("Local (train here on IO LULC 2023)", "local")
        pf.addRow("Mode:", self.mode_combo)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.05, 0.95)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(0.65)
        pf.addRow("Built-up threshold:", self.threshold)

        self.max_cloud = QSpinBox()
        self.max_cloud.setRange(1, 100)
        self.max_cloud.setValue(70)
        self.max_cloud.setSuffix(" %")
        pf.addRow("Max scene cloud:", self.max_cloud)

        self.crs_edit = QLineEdit()
        self.crs_edit.setPlaceholderText("optional projected CRS in metres, e.g. EPSG:2180")
        pf.addRow("CRS:", self.crs_edit)
        root.addWidget(params)

        run_env = QGroupBox("Processing backend (landcoverrewind)")
        rf = QFormLayout(run_env)
        interp_row = QHBoxLayout()
        self.interp_edit = QLineEdit()
        self.interp_edit.setPlaceholderText("Python with landcoverrewind installed, e.g. python3")
        ib = QPushButton("Browse...")
        ib.clicked.connect(lambda: self._browse_into(self.interp_edit))
        interp_row.addWidget(self.interp_edit)
        interp_row.addWidget(ib)
        rf.addRow("Python:", interp_row)

        cli_row = QHBoxLayout()
        self.cli_edit = QLineEdit()
        self.cli_edit.setPlaceholderText("path to landcoverrewind_cli.py")
        cb = QPushButton("Browse...")
        cb.clicked.connect(lambda: self._browse_into(self.cli_edit, "Python (*.py)"))
        cli_row.addWidget(self.cli_edit)
        cli_row.addWidget(cb)
        rf.addRow("CLI script:", cli_row)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("output folder (default: a temporary folder)")
        ob = QPushButton("Browse...")
        ob.clicked.connect(self._browse_out)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(ob)
        rf.addRow("Output folder:", out_row)
        root.addWidget(run_env)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(120)
        root.addWidget(self.log)

        self.buttons = QDialogButtonBox()
        self.run_btn = self.buttons.addButton("Run", QDialogButtonBox.AcceptRole)
        self.cancel_btn = self.buttons.addButton("Cancel run", QDialogButtonBox.ResetRole)
        self.cancel_btn.setEnabled(False)
        self.close_btn = self.buttons.addButton(QDialogButtonBox.Close)
        self.run_btn.clicked.connect(self.start_run)
        self.cancel_btn.clicked.connect(self.cancel_run)
        self.close_btn.clicked.connect(self.close)
        root.addWidget(self.buttons)

    # ---------- helpers ----------
    def _refresh_layers(self):
        self.layer_combo.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if (isinstance(lyr, QgsVectorLayer) and lyr.isValid()
                    and lyr.geometryType() == QgsWkbTypes.PolygonGeometry):
                self.layer_combo.addItem(lyr.name(), lyr.id())

    def _browse_aoi(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Area file", "", "Vector (*.gpkg *.geojson *.json *.shp);;All files (*)")
        if path:
            self.file_edit.setText(path)

    def _browse_into(self, edit, flt="All files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, "Select", edit.text() or "", flt)
        if path:
            edit.setText(path)

    def _browse_out(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", self.out_edit.text() or "")
        if path:
            self.out_edit.setText(path)

    def _settings(self):
        return QgsSettings()

    def _load_settings(self):
        s = self._settings()
        self.interp_edit.setText(s.value(f"{SETTINGS}/python", sys.executable or "python3"))
        cli = s.value(f"{SETTINGS}/cli", "")
        if not cli:
            here = os.path.dirname(os.path.abspath(__file__))
            cli = core.find_cli([here, os.path.dirname(here), os.path.expanduser("~")]) or ""
        self.cli_edit.setText(cli)

    def _save_settings(self):
        s = self._settings()
        s.setValue(f"{SETTINGS}/python", self.interp_edit.text().strip())
        s.setValue(f"{SETTINGS}/cli", self.cli_edit.text().strip())

    def _message(self, text, level):
        self.iface.messageBar().pushMessage("Land Cover Rewind", text, level=level)

    def _chosen_epochs(self):
        return [y for y, cb in self.epoch_checks.items() if cb.isChecked()]

    def _export_layer(self, layer, selected_only, folder):
        path = os.path.join(folder, "aoi.gpkg")
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.onlySelectedFeatures = bool(selected_only)
        res = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, path, QgsCoordinateTransformContext(), opts)
        err = res[0]
        if err != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"could not export the area layer: {res[1]}")
        return path

    # ---------- run ----------
    def start_run(self):
        from qgis.core import Qgis
        if self.task is not None:
            self._message("A run is already in progress.", Qgis.Warning)
            return
        try:
            epochs = self._chosen_epochs()
            mode = self.mode_combo.currentData()
            core.validate_params(epochs, self.threshold.value(), self.max_cloud.value(), mode)

            interp = self.interp_edit.text().strip()
            cli = self.cli_edit.text().strip()
            if not interp:
                raise ValueError("set the Python interpreter for landcoverrewind")
            if not cli or not os.path.isfile(cli):
                raise ValueError("set a valid path to landcoverrewind_cli.py")

            out_dir = self.out_edit.text().strip()
            if not out_dir:
                self._tmpdir = tempfile.mkdtemp(prefix="lcr_")
                out_dir = self._tmpdir
            os.makedirs(out_dir, exist_ok=True)

            aoi = self.file_edit.text().strip()
            if not aoi:
                lid = self.layer_combo.currentData()
                layer = QgsProject.instance().mapLayer(lid) if lid else None
                if layer is None:
                    raise ValueError("choose a polygon layer or an area file")
                if self.selected_only.isChecked() and layer.selectedFeatureCount() == 0:
                    raise ValueError("'Selected features only' is on but nothing is selected")
                aoi = self._export_layer(layer, self.selected_only.isChecked(), out_dir)
            elif not os.path.isfile(aoi):
                raise ValueError(f"area file not found: {aoi}")

            crs = self.crs_edit.text().strip() or None
            cmd = core.build_command(interp, cli, aoi, out_dir, epochs, mode,
                                     self.threshold.value(), self.max_cloud.value(), crs, lang="pl")
        except (ValueError, RuntimeError) as e:
            self._message(str(e), Qgis.Critical)
            return

        self._out_dir = out_dir
        self._epochs = epochs
        self.log.clear()
        self.log.appendPlainText("Running: " + " ".join(cmd))
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._save_settings()

        self.task = RunTask(cmd, out_dir, epochs, cwd=os.path.dirname(cli))
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
        for info in layers:
            rl = QgsRasterLayer(info["path"], info["title"])
            if not rl.isValid():
                continue
            QgsProject.instance().addMapLayer(rl)
            styling.style_layer(rl, info["kind"], self._epochs)
            extent.combineExtentWith(rl.extent())
            added += 1
        if added and not extent.isEmpty():
            canvas = self.iface.mapCanvas()
            canvas.setExtent(extent)
            canvas.refresh()
        self._message(f"Done. Added {added} result layers.", Qgis.Success)
        self.task = None

    def _on_terminated(self):
        from qgis.core import Qgis
        self._finish_common()
        err = self.task.error if self.task else "the run was cancelled or failed"
        self._message(err or "the run was cancelled", Qgis.Warning)
        self.task = None

    def closeEvent(self, event):
        # don't leave a running task without its dialog callbacks; ask it to stop
        if self.task is not None:
            self.task.cancel()
        super().closeEvent(event)
