def classFactory(iface):
    from .plugin_main import MagicSearch
    return MagicSearch(iface)
