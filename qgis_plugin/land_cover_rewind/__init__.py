"""Land Cover Rewind QGIS plugin."""


def classFactory(iface):  # noqa: N802 (QGIS API name)
    from .plugin import LandCoverRewindPlugin
    return LandCoverRewindPlugin(iface)
