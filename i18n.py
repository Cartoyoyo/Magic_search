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
        'es': "Buscar una dirección, una parcela...",
        'pt': "Pesquisar um endereço, uma parcela...",
        'de': "Adresse, Flurstück suchen..."},
    'tip_clear': {
        'fr': "Effacer",
        'en': "Clear",
        'es': "Borrar",
        'pt': "Limpar",
        'de': "Löschen"},
    'tip_config': {
        'fr': "Configuration",
        'en': "Settings",
        'es': "Configuración",
        'pt': "Configuração",
        'de': "Einstellungen"},
    'tip_collapse': {
        'fr': "Réduire",
        'en': "Collapse",
        'es': "Reducir",
        'pt': "Reduzir",
        'de': "Einklappen"},

    # ---- Bouton de synchronisation ----
    'tip_sync_never': {
        'fr': "Aucune couche indexée - cliquez pour synchroniser",
        'en': "No layer indexed - click to sync",
        'es': "Ninguna capa indexada - haga clic para sincronizar",
        'pt': "Nenhuma camada indexada - clique para sincronizar",
        'de': "Keine Ebene indiziert - zum Synchronisieren klicken"},
    'tip_sync_partial': {
        'fr': "Synchronisation incomplète - cliquez pour synchroniser",
        'en': "Incomplete sync - click to sync",
        'es': "Sincronización incompleta - haga clic para sincronizar",
        'pt': "Sincronização incompleta - clique para sincronizar",
        'de': "Unvollständige Synchronisierung - zum Synchronisieren klicken"},
    'tip_sync_syncing': {
        'fr': "Synchronisation en cours...",
        'en': "Syncing...",
        'es': "Sincronización en curso...",
        'pt': "Sincronização em curso...",
        'de': "Synchronisierung läuft..."},
    'tip_sync_complete': {
        'fr': "Synchronisation complète",
        'en': "Sync complete",
        'es': "Sincronización completa",
        'pt': "Sincronização completa",
        'de': "Synchronisierung abgeschlossen"},

    # ---- Resultats ----
    'no_results': {
        'fr': "Aucun résultat",
        'en': "No result",
        'es': "Sin resultados",
        'pt': "Sem resultados",
        'de': "Kein Ergebnis"},
    'expand_more': {
        'fr': "... {count} autre(s) - zoom global",
        'en': "... {count} more - zoom to all",
        'es': "... {count} más - zoom global",
        'pt': "... {count} mais - zoom global",
        'de': "... {count} weitere - Gesamtansicht"},

    # ---- Indexation ----
    'status_indexing': {
        'fr': "Indexation en cours... encore quelques instants de patience "
              "(des ralentissements sont possibles)",
        'en': "Indexing in progress... please wait a moment "
              "(slowdowns are possible)",
        'es': "Indexación en curso... espere un momento "
              "(son posibles ralentizaciones)",
        'pt': "Indexação em curso... aguarde um momento "
              "(são possíveis lentidões)",
        'de': "Indizierung läuft... bitte einen Moment Geduld "
              "(Verlangsamungen sind möglich)"},
    'status_progress': {
        'fr': "Indexation : {layer} ({count} entités)",
        'en': "Indexing: {layer} ({count} features)",
        'es': "Indexación: {layer} ({count} entidades)",
        'pt': "Indexação: {layer} ({count} entidades)",
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
        'es': "Magic Search - Configuración",
        'pt': "Magic Search - Configuração",
        'de': "Magic Search - Einstellungen"},
    'tip_reverse_geocode': {
        'fr': "Adresse BAN la plus proche (cliquer sur la carte)",
        'en': "Nearest BAN address (click on the map)",
        'es': "Dirección BAN más cercana (clic en el mapa)",
        'pt': "Endereço BAN mais próximo (clique no mapa)",
        'de': "Nächste BAN-Adresse (auf die Karte klicken)"},

    # ---- Geocodage inverse ----
    'msg_reverse_none': {
        'fr': "Aucune adresse BAN à moins de {max} m",
        'en': "No BAN address within {max} m",
        'es': "Ninguna dirección BAN a menos de {max} m",
        'pt': "Nenhum endereço BAN a menos de {max} m",
        'de': "Keine BAN-Adresse innerhalb von {max} m"},

    # ---- Vue de rue ----
    'tip_street_view': {
        'fr': "Vue de rue (choisir un service puis cliquer sur la carte)",
        'en': "Street view (pick a service then click on the map)",
        'es': "Vista de calle (elija un servicio y haga clic en el mapa)",
        'pt': "Vista de rua (escolha um serviço e clique no mapa)",
        'de': "Straßenansicht (Dienst wählen, dann auf die Karte klicken)"},
    'msg_street_view_prompt': {
        'fr': "Cliquez sur la carte pour ouvrir {service}",
        'en': "Click on the map to open {service}",
        'es': "Haga clic en el mapa para abrir {service}",
        'pt': "Clique no mapa para abrir {service}",
        'de': "Klicken Sie auf die Karte, um {service} zu öffnen"},
    'menu_copy_coords': {
        'fr': "Copier les coordonnées",
        'en': "Copy coordinates",
        'es': "Copiar coordenadas",
        'pt': "Copiar coordenadas",
        'de': "Koordinaten kopieren"},
    'msg_copy_coords_prompt': {
        'fr': "Cliquez sur la carte pour copier ses coordonnées",
        'en': "Click on the map to copy its coordinates",
        'es': "Haga clic en el mapa para copiar sus coordenadas",
        'pt': "Clique no mapa para copiar as coordenadas",
        'de': "Klicken Sie auf die Karte, um ihre Koordinaten zu kopieren"},
    'tip_more': {
        'fr': "Plus d'outils (favoris, historique)",
        'en': "More tools (favorites, history)",
        'es': "Más herramientas (favoritos, historial)",
        'pt': "Mais ferramentas (favoritos, histórico)",
        'de': "Weitere Werkzeuge (Favoriten, Verlauf)"},
    'tip_history': {
        'fr': "Recherches récentes",
        'en': "Recent searches",
        'es': "Búsquedas recientes",
        'pt': "Pesquisas recentes",
        'de': "Letzte Suchen"},
    'history_empty': {
        'fr': "(aucune recherche récente)",
        'en': "(no recent search)",
        'es': "(sin búsquedas recientes)",
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
        'es': "Agregar un favorito aquí...",
        'pt': "Adicionar um favorito aqui...",
        'de': "Favorit hier hinzufügen..."},
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
        'fr': "Favori \"{label}\" enregistré",
        'en': "Favorite \"{label}\" saved",
        'es': "Favorito \"{label}\" guardado",
        'pt': "Favorito \"{label}\" guardado",
        'de': "Favorit \"{label}\" gespeichert"},
    'tag_coord': {
        'fr': "COORD", 'en': "COORD", 'es': "COORD", 'pt': "COORD", 'de': "KOORD"},
    'msg_coords_copied': {
        'fr': "Coordonnées copiées dans le presse-papiers",
        'en': "Coordinates copied to clipboard",
        'es': "Coordenadas copiadas al portapapeles",
        'pt': "Coordenadas copiadas para a área de transferência",
        'de': "Koordinaten in die Zwischenablage kopiert"},

    # ---- Barre flottante (modele M2c) ----
    'scope_checked': {
        'fr': "Cochées", 'en': "Visible", 'es': "Visibles", 'pt': "Visíveis", 'de': "Sichtbar"},
    'scope_all': {
        'fr': "Toutes", 'en': "All", 'es': "Todas", 'pt': "Todas", 'de': "Alle"},
    'tip_scope': {
        'fr': "Périmètre de la recherche dans les couches",
        'en': "Layer search scope",
        'es': "Alcance de la búsqueda en las capas",
        'pt': "Âmbito da pesquisa nas camadas",
        'de': "Suchbereich in den Layern"},
    'menu_scope_checked': {
        'fr': "Couches cochées", 'en': "Checked layers", 'es': "Capas marcadas",
        'pt': "Camadas marcadas", 'de': "Aktivierte Layer"},
    'menu_scope_all': {
        'fr': "Toutes les couches", 'en': "All layers", 'es': "Todas las capas",
        'pt': "Todas as camadas", 'de': "Alle Layer"},
    'menu_reverse': {
        'fr': "Adresse au clic sur la carte", 'en': "Address at map click",
        'es': "Dirección al hacer clic en el mapa", 'pt': "Endereço ao clicar no mapa",
        'de': "Adresse per Klick auf die Karte"},
    'tip_reverse_active': {
        'fr': "Adresse au clic active - cliquer pour arrêter",
        'en': "Address at click is on - click to stop",
        'es': "Direccion al clic activa - clic para detener",
        'pt': "Endereco ao clique ativo - clique para parar",
        'de': "Adresse per Klick aktiv - zum Beenden klicken"},
    'menu_street_view': {
        'fr': "Vue de rue", 'en': "Street view", 'es': "Vista de calle",
        'pt': "Vista de rua", 'de': "Straßenansicht"},
    'menu_collapse': {
        'fr': "Replier la barre", 'en': "Collapse the bar", 'es': "Plegar la barra",
        'pt': "Recolher a barra", 'de': "Leiste einklappen"},
    'sub_address': {
        'fr': "Adresse", 'en': "Address", 'es': "Dirección", 'pt': "Endereço", 'de': "Adresse"},
    'ban_housenumber': {
        'fr': "numéro", 'en': "house number", 'es': "número", 'pt': "número", 'de': "Hausnummer"},
    'ban_street': {
        'fr': "voie", 'en': "street", 'es': "vía", 'pt': "via", 'de': "Straße"},
    'ban_locality': {
        'fr': "lieu-dit", 'en': "locality", 'es': "paraje", 'pt': "lugar", 'de': "Flurname"},
    'ban_municipality': {
        'fr': "commune", 'en': "municipality", 'es': "municipio", 'pt': "município", 'de': "Gemeinde"},
    'sub_coord': {
        'fr': "Coordonnées", 'en': "Coordinates", 'es': "Coordenadas",
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
        'fr': "Tab réduire", 'en': "Tab show less", 'es': "Tab ver menos",
        'pt': "Tab ver menos", 'de': "Tab weniger"},
    'state_never': {
        'fr': "Index à créer", 'en': "No index yet", 'es': "Índice por crear",
        'pt': "Índice por criar", 'de': "Kein Index"},
    'state_partial': {
        'fr': "Index incomplet", 'en': "Index incomplete", 'es': "Índice incompleto",
        'pt': "Índice incompleto", 'de': "Index unvollständig"},
    'state_syncing': {
        'fr': "Indexation...", 'en': "Indexing...", 'es': "Indexando...",
        'pt': "A indexar...", 'de': "Indizierung..."},
    'state_complete': {
        'fr': "Index à jour", 'en': "Index up to date", 'es': "Índice al día",
        'pt': "Índice atualizado", 'de': "Index aktuell"},
    'footer_stats': {
        'fr': "{layers} couche(s) · {values} valeurs",
        'en': "{layers} layer(s) · {values} values",
        'es': "{layers} capa(s) · {values} valores",
        'pt': "{layers} camada(s) · {values} valores",
        'de': "{layers} Layer · {values} Werte"},

    # ---- Geocodeur injoignable (ligne d'avertissement de la liste) ----
    'geo_unavailable': {
        'fr': "{source} indisponible",
        'en': "{source} unavailable",
        'es': "{source} no disponible",
        'pt': "{source} indisponível",
        'de': "{source} nicht erreichbar"},
    'geo_err_offline': {
        'fr': "pas de connexion réseau",
        'en': "no network connection",
        'es': "sin conexión de red",
        'pt': "sem ligação à rede",
        'de': "keine Netzwerkverbindung"},
    'geo_err_timeout': {
        'fr': "pas de réponse (délai dépassé)",
        'en': "no answer (timed out)",
        'es': "sin respuesta (tiempo agotado)",
        'pt': "sem resposta (tempo esgotado)",
        'de': "keine Antwort (Zeitüberschreitung)"},
    'geo_err_service': {
        'fr': "le service a renvoyé une erreur",
        'en': "the service returned an error",
        'es': "el servicio devolvió un error",
        'pt': "o serviço devolveu um erro",
        'de': "der Dienst meldet einen Fehler"},

    # ---- Etat du cache (dialogue de configuration) ----
    'cache_not_created': {
        'fr': "(pas encore créé)",
        'en': "(not created yet)",
        'es': "(aún no creado)",
        'pt': "(ainda não criado)",
        'de': "(noch nicht erstellt)"},
    'cache_no_project': {
        'fr': "(projet non enregistré)",
        'en': "(project not saved)",
        'es': "(proyecto no guardado)",
        'pt': "(projeto não guardado)",
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
