"""
i18n - Libelles d'interface partages entre les deux styles d'UI
('maps' = barre flottante, 'qt5' = panneau ancrable), le gestionnaire
d'index et le plugin principal.

La langue courante est un etat de module : plugin_main appelle set_lang()
a chaque chargement/changement de configuration, puis retranslate() sur les
widgets pour rafraichir les libelles deja construits (placeholders, tooltips).

Les libelles du dialogue de configuration restent dans config_dialog.py
(dictionnaire TR), car ce dialogue gere sa propre langue en direct.
"""

LANGS = ('fr', 'en', 'es', 'pt', 'de')
DEFAULT_LANG = 'en'

TR = {
    # ---- Barre de saisie ----
    'placeholder': {
        'fr': "Rechercher une adresse, une parcelle...",
        'en': "Search an address, a parcel...",
        'es': "Buscar una direccion, una parcela...",
        'pt': "Pesquisar um endereco, uma parcela...",
        'de': "Adresse, Flurstuck suchen..."},
    'tip_clear': {
        'fr': "Effacer",
        'en': "Clear",
        'es': "Borrar",
        'pt': "Limpar",
        'de': "Loschen"},
    'tip_config': {
        'fr': "Configuration",
        'en': "Settings",
        'es': "Configuracion",
        'pt': "Configuracao",
        'de': "Einstellungen"},
    'tip_collapse': {
        'fr': "Reduire",
        'en': "Collapse",
        'es': "Reducir",
        'pt': "Reduzir",
        'de': "Einklappen"},

    # ---- Bouton de synchronisation ----
    'tip_sync_never': {
        'fr': "Aucune couche indexee - cliquez pour synchroniser",
        'en': "No layer indexed - click to sync",
        'es': "Ninguna capa indexada - haga clic para sincronizar",
        'pt': "Nenhuma camada indexada - clique para sincronizar",
        'de': "Keine Ebene indiziert - zum Synchronisieren klicken"},
    'tip_sync_partial': {
        'fr': "Synchronisation incomplete - cliquez pour synchroniser",
        'en': "Incomplete sync - click to sync",
        'es': "Sincronizacion incompleta - haga clic para sincronizar",
        'pt': "Sincronizacao incompleta - clique para sincronizar",
        'de': "Unvollstandige Synchronisierung - zum Synchronisieren klicken"},
    'tip_sync_syncing': {
        'fr': "Synchronisation en cours...",
        'en': "Syncing...",
        'es': "Sincronizacion en curso...",
        'pt': "Sincronizacao em curso...",
        'de': "Synchronisierung lauft..."},
    'tip_sync_complete': {
        'fr': "Synchronisation complete",
        'en': "Sync complete",
        'es': "Sincronizacion completa",
        'pt': "Sincronizacao completa",
        'de': "Synchronisierung abgeschlossen"},

    # ---- Resultats ----
    'no_results': {
        'fr': "Aucun resultat",
        'en': "No result",
        'es': "Sin resultados",
        'pt': "Sem resultados",
        'de': "Kein Ergebnis"},
    'expand_more': {
        'fr': "... {count} autre(s) - zoom global",
        'en': "... {count} more - zoom to all",
        'es': "... {count} mas - zoom global",
        'pt': "... {count} mais - zoom global",
        'de': "... {count} weitere - Gesamtansicht"},

    # ---- Indexation ----
    'status_indexing': {
        'fr': "Indexation en cours... encore quelques instants de patience "
              "(des ralentissements sont possibles)",
        'en': "Indexing in progress... please wait a moment "
              "(slowdowns are possible)",
        'es': "Indexacion en curso... espere un momento "
              "(son posibles ralentizaciones)",
        'pt': "Indexacao em curso... aguarde um momento "
              "(sao possiveis lentidoes)",
        'de': "Indizierung lauft... bitte einen Moment Geduld "
              "(Verlangsamungen sind moglich)"},
    'status_progress': {
        'fr': "Indexation : {layer} ({count} entites)",
        'en': "Indexing: {layer} ({count} features)",
        'es': "Indexacion: {layer} ({count} entidades)",
        'pt': "Indexacao: {layer} ({count} entidades)",
        'de': "Indizierung: {layer} ({count} Objekte)"},

    # ---- Menu / barre d'outils QGIS ----
    'tip_toggle': {
        'fr': "Afficher / Masquer Magic Search",
        'en': "Show / Hide Magic Search",
        'es': "Mostrar / Ocultar Magic Search",
        'pt': "Mostrar / Ocultar Magic Search",
        'de': "Magic Search ein-/ausblenden"},
    'menu_config': {
        'fr': "Magic Search - Configuration",
        'en': "Magic Search - Settings",
        'es': "Magic Search - Configuracion",
        'pt': "Magic Search - Configuracao",
        'de': "Magic Search - Einstellungen"},
    'tip_reverse_geocode': {
        'fr': "Adresse BAN la plus proche (cliquer sur la carte)",
        'en': "Nearest BAN address (click on the map)",
        'es': "Direccion BAN mas cercana (clic en el mapa)",
        'pt': "Endereco BAN mais proximo (clique no mapa)",
        'de': "Nachste BAN-Adresse (auf die Karte klicken)"},

    # ---- Geocodage inverse ----
    'msg_reverse_none': {
        'fr': "Aucune adresse BAN a moins de {max} m",
        'en': "No BAN address within {max} m",
        'es': "Ninguna direccion BAN a menos de {max} m",
        'pt': "Nenhum endereco BAN a menos de {max} m",
        'de': "Keine BAN-Adresse innerhalb von {max} m"},

    # ---- Vue de rue ----
    'tip_street_view': {
        'fr': "Vue de rue (choisir un service puis cliquer sur la carte)",
        'en': "Street view (pick a service then click on the map)",
        'es': "Vista de calle (elija un servicio y haga clic en el mapa)",
        'pt': "Vista de rua (escolha um servico e clique no mapa)",
        'de': "Strassenansicht (Dienst waehlen, dann auf die Karte klicken)"},
    'msg_street_view_prompt': {
        'fr': "Cliquez sur la carte pour ouvrir {service}",
        'en': "Click on the map to open {service}",
        'es': "Haga clic en el mapa para abrir {service}",
        'pt': "Clique no mapa para abrir {service}",
        'de': "Klicken Sie auf die Karte, um {service} zu oeffnen"},
    'menu_copy_coords': {
        'fr': "Copier les coordonnees",
        'en': "Copy coordinates",
        'es': "Copiar coordenadas",
        'pt': "Copiar coordenadas",
        'de': "Koordinaten kopieren"},
    'msg_copy_coords_prompt': {
        'fr': "Cliquez sur la carte pour copier ses coordonnees",
        'en': "Click on the map to copy its coordinates",
        'es': "Haga clic en el mapa para copiar sus coordenadas",
        'pt': "Clique no mapa para copiar as coordenadas",
        'de': "Klicken Sie auf die Karte, um ihre Koordinaten zu kopieren"},
    'tip_more': {
        'fr': "Plus d'outils (favoris, historique)",
        'en': "More tools (favorites, history)",
        'es': "Mas herramientas (favoritos, historial)",
        'pt': "Mais ferramentas (favoritos, historico)",
        'de': "Weitere Werkzeuge (Favoriten, Verlauf)"},
    'tip_history': {
        'fr': "Recherches recentes",
        'en': "Recent searches",
        'es': "Busquedas recientes",
        'pt': "Pesquisas recentes",
        'de': "Letzte Suchen"},
    'history_empty': {
        'fr': "(aucune recherche recente)",
        'en': "(no recent search)",
        'es': "(sin busquedas recientes)",
        'pt': "(sem pesquisas recentes)",
        'de': "(keine letzten Suchen)"},
    'tip_favorites': {
        'fr': "Favoris",
        'en': "Favorites",
        'es': "Favoritos",
        'pt': "Favoritos",
        'de': "Favoriten"},
    'menu_add_favorite': {
        'fr': "Ajouter un favori ici...",
        'en': "Add a favorite here...",
        'es': "Agregar un favorito aqui...",
        'pt': "Adicionar um favorito aqui...",
        'de': "Favorit hier hinzufuegen..."},
    'menu_remove_favorite': {
        'fr': "Supprimer un favori",
        'en': "Remove a favorite",
        'es': "Eliminar un favorito",
        'pt': "Remover um favorito",
        'de': "Favorit entfernen"},
    'favorites_empty': {
        'fr': "(aucun favori)",
        'en': "(no favorite)",
        'es': "(sin favoritos)",
        'pt': "(sem favoritos)",
        'de': "(keine Favoriten)"},
    'favorite_dialog_title': {
        'fr': "Nouveau favori",
        'en': "New favorite",
        'es': "Nuevo favorito",
        'pt': "Novo favorito",
        'de': "Neuer Favorit"},
    'favorite_dialog_label': {
        'fr': "Nom du favori :",
        'en': "Favorite name:",
        'es': "Nombre del favorito:",
        'pt': "Nome do favorito:",
        'de': "Name des Favoriten:"},
    'msg_favorite_prompt': {
        'fr': "Cliquez sur la carte pour enregistrer un favori",
        'en': "Click on the map to save a favorite",
        'es': "Haga clic en el mapa para guardar un favorito",
        'pt': "Clique no mapa para guardar um favorito",
        'de': "Klicken Sie auf die Karte, um einen Favoriten zu speichern"},
    'msg_favorite_saved': {
        'fr': "Favori \"{label}\" enregistre",
        'en': "Favorite \"{label}\" saved",
        'es': "Favorito \"{label}\" guardado",
        'pt': "Favorito \"{label}\" guardado",
        'de': "Favorit \"{label}\" gespeichert"},
    'tag_coord': {
        'fr': "COORD", 'en': "COORD", 'es': "COORD", 'pt': "COORD", 'de': "KOORD"},
    'msg_coords_copied': {
        'fr': "Coordonnees copiees dans le presse-papiers",
        'en': "Coordinates copied to clipboard",
        'es': "Coordenadas copiadas al portapapeles",
        'pt': "Coordenadas copiadas para a area de transferencia",
        'de': "Koordinaten in die Zwischenablage kopiert"},

    # ---- Barre flottante (modele M2c) ----
    'scope_checked': {
        'fr': "Cochees", 'en': "Visible", 'es': "Visibles", 'pt': "Visiveis", 'de': "Sichtbar"},
    'scope_all': {
        'fr': "Toutes", 'en': "All", 'es': "Todas", 'pt': "Todas", 'de': "Alle"},
    'tip_scope': {
        'fr': "Perimetre de la recherche dans les couches",
        'en': "Layer search scope",
        'es': "Alcance de la busqueda en las capas",
        'pt': "Ambito da pesquisa nas camadas",
        'de': "Suchbereich in den Layern"},
    'menu_scope_checked': {
        'fr': "Couches cochees", 'en': "Checked layers", 'es': "Capas marcadas",
        'pt': "Camadas marcadas", 'de': "Aktivierte Layer"},
    'menu_scope_all': {
        'fr': "Toutes les couches", 'en': "All layers", 'es': "Todas las capas",
        'pt': "Todas as camadas", 'de': "Alle Layer"},
    'menu_reverse': {
        'fr': "Adresse au clic sur la carte", 'en': "Address at map click",
        'es': "Direccion al hacer clic en el mapa", 'pt': "Endereco ao clicar no mapa",
        'de': "Adresse per Klick auf die Karte"},
    'tip_reverse_active': {
        'fr': "Adresse au clic active - cliquer pour arreter",
        'en': "Address at click is on - click to stop",
        'es': "Direccion al clic activa - clic para detener",
        'pt': "Endereco ao clique ativo - clique para parar",
        'de': "Adresse per Klick aktiv - zum Beenden klicken"},
    'menu_street_view': {
        'fr': "Vue de rue", 'en': "Street view", 'es': "Vista de calle",
        'pt': "Vista de rua", 'de': "Strassenansicht"},
    'menu_collapse': {
        'fr': "Replier la barre", 'en': "Collapse the bar", 'es': "Plegar la barra",
        'pt': "Recolher a barra", 'de': "Leiste einklappen"},
    'sub_address': {
        'fr': "Adresse", 'en': "Address", 'es': "Direccion", 'pt': "Endereco", 'de': "Adresse"},
    'ban_housenumber': {
        'fr': "numero", 'en': "house number", 'es': "numero", 'pt': "numero", 'de': "Hausnummer"},
    'ban_street': {
        'fr': "voie", 'en': "street", 'es': "via", 'pt': "via", 'de': "Strasse"},
    'ban_locality': {
        'fr': "lieu-dit", 'en': "locality", 'es': "paraje", 'pt': "lugar", 'de': "Flurname"},
    'ban_municipality': {
        'fr': "commune", 'en': "municipality", 'es': "municipio", 'pt': "municipio", 'de': "Gemeinde"},
    'sub_coord': {
        'fr': "Coordonnees", 'en': "Coordinates", 'es': "Coordenadas",
        'pt': "Coordenadas", 'de': "Koordinaten"},
    'count_objects': {
        'fr': "{n} obj.", 'en': "{n} feat.", 'es': "{n} obj.", 'pt': "{n} obj.", 'de': "{n} Obj."},
    'footer_count': {
        'fr': "{shown} sur {total}", 'en': "{shown} of {total}", 'es': "{shown} de {total}",
        'pt': "{shown} de {total}", 'de': "{shown} von {total}"},
    'footer_all': {
        'fr': "Tab tout voir", 'en': "Tab show all", 'es': "Tab ver todo",
        'pt': "Tab ver tudo", 'de': "Tab alle zeigen"},
    'footer_less': {
        'fr': "Tab reduire", 'en': "Tab show less", 'es': "Tab ver menos",
        'pt': "Tab ver menos", 'de': "Tab weniger"},
    'state_never': {
        'fr': "Index a creer", 'en': "No index yet", 'es': "Indice por crear",
        'pt': "Indice por criar", 'de': "Kein Index"},
    'state_partial': {
        'fr': "Index incomplet", 'en': "Index incomplete", 'es': "Indice incompleto",
        'pt': "Indice incompleto", 'de': "Index unvollstandig"},
    'state_syncing': {
        'fr': "Indexation...", 'en': "Indexing...", 'es': "Indexando...",
        'pt': "A indexar...", 'de': "Indizierung..."},
    'state_complete': {
        'fr': "Index a jour", 'en': "Index up to date", 'es': "Indice al dia",
        'pt': "Indice atualizado", 'de': "Index aktuell"},
    'footer_stats': {
        'fr': "{layers} couche(s) · {values} valeurs",
        'en': "{layers} layer(s) · {values} values",
        'es': "{layers} capa(s) · {values} valores",
        'pt': "{layers} camada(s) · {values} valores",
        'de': "{layers} Layer · {values} Werte"},

    # ---- Etat du cache (dialogue de configuration) ----
    'cache_not_created': {
        'fr': "(pas encore cree)",
        'en': "(not created yet)",
        'es': "(aun no creado)",
        'pt': "(ainda nao criado)",
        'de': "(noch nicht erstellt)"},
    'cache_no_project': {
        'fr': "(projet non enregistre)",
        'en': "(project not saved)",
        'es': "(proyecto no guardado)",
        'pt': "(projeto nao guardado)",
        'de': "(Projekt nicht gespeichert)"},
}

_current_lang = DEFAULT_LANG


def set_lang(code):
    """Definit la langue courante. Retombe sur DEFAULT_LANG si non supportee."""
    global _current_lang
    _current_lang = code if code in LANGS else DEFAULT_LANG


def current_lang():
    return _current_lang


def tr(key, lang=None, **kwargs):
    """Libelle traduit. `lang` force une langue, sinon la langue courante.
    Les kwargs sont injectes via str.format (ex: tr('expand_more', count=3))."""
    entry = TR.get(key)
    if entry is None:
        return key
    text = entry.get(lang or _current_lang) or entry[DEFAULT_LANG]
    return text.format(**kwargs) if kwargs else text
