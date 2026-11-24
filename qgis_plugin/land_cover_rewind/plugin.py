"""Plugin entry point: adds a toolbar button and menu item that open the dialog."""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .dialog import LandCoverRewindDialog

MENU = "&Land Cover Rewind"
TITLE = "Land Cover Rewind"


class LandCoverRewindPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.toolbar = None
        self.dialog = None
        self._icon = os.path.join(os.path.dirname(__file__), "icon.png")

    def initGui(self):  # noqa: N802 (QGIS API name)
        self.action = QAction(QIcon(self._icon), TITLE, self.iface.mainWindow())
        self.action.setToolTip(TITLE)
        self.action.triggered.connect(self.run)

        # Own toolbar so the plugin name shows next to the icon
        self.toolbar = self.iface.addToolBar(TITLE)
        self.toolbar.setObjectName("LandCoverRewindToolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addAction(self.action)

        self.iface.addPluginToRasterMenu(MENU, self.action)

    def unload(self):  # noqa: N802
        if self.action is not None:
            self.iface.removePluginRasterMenu(MENU, self.action)
            if self.toolbar is not None:
                self.toolbar.removeAction(self.action)
            self.action = None
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        # one dialog instance, reused; refresh the layer list each time it opens
        if self.dialog is None:
            self.dialog = LandCoverRewindDialog(self.iface, self.iface.mainWindow())
        else:
            self.dialog._refresh_layers()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
