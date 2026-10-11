"""Liens profonds vers le front — source de vérité unique.

Le fil d'activité, les notifications et les e-mails renvoient vers une page qui
contient souvent des centaines d'éléments répartis en onglets. Y arriver sans
précision oblige l'utilisateur à chercher ce sur quoi il vient de cliquer.

La convention du projet (cf. `front/src/lib/deepLink.ts`) tient en deux morceaux :

  - une **route dédiée** par onglet (`/annonces`, `/calendrier/kanban`)
  - `#<prefixe>-<id>`  → l'élément à déplier et à révéler

⚠️ Le premier morceau était `?onglet=<id>` jusqu'au 05/09/2026. Les anciennes URL
restent servies — le front les redirige en 308 — mais aucune ne s'écrit plus ici :
une adresse qu'on fabrique doit être celle qu'on veut voir dans la barre du
navigateur, sinon on envoie un lien qui rebondit.

Le problème n'est pas la convention, c'est qu'elle était **recopiée à la main** dans
une quinzaine de f-strings réparties sur `flux.py`, `annonces.py`, `idees.py` et
`calendrier.py`. Chaque nouvel appel devait redevenir savoir dans quel onglet vit
l'élément visé — et le 28/07/2026 une fiche prestataire est partie sans onglet :
`/prestataires#presta-23` déposait l'utilisateur sur « Prestations ponctuelles »,
où aucun élément ne porte cet id. La page était la bonne, la fiche invisible.

Ce module remplace ces f-strings par une table unique. Y ajouter une ligne est le
seul geste nécessaire pour exposer un nouveau type d'élément, et
`api/tests/test_liens_front.py` vérifie que chaque ligne pointe vers une page
réelle, un onglet réellement déclaré, et un onglet qui rend bien cette ancre.
"""

from __future__ import annotations

#: L'adresse publique du site, telle qu'on peut la CONCATÉNER.
#:
#: 🔴 Signalé à l'écran le 11/09/2026 : un e-mail de ticket portait
#: `https://5hostachy.fr//tickets/34` — double barre, **404**. La valeur en base
#: se terminait par « / », et les modèles écrivent tous `{{ app.url }}/tickets/…`.
#:
#: Le défaut n'était PAS dans le modèle d'e-mail. `site_url` est lu à une
#: vingtaine d'endroits dans l'API ; onze n'enlevaient pas la barre finale, et les
#: autres le faisaient chacun dans leur coin, par `rstrip("/")` recopié. C'est la
#: forme canonique de la duplication : une notion écrite N fois, corrigée une
#: seule, et le défaut réapparaît par le chemin qu'on n'a pas relu.
#:
#: ⚠️ Normaliser à l'ENREGISTREMENT ne suffit pas et ne suffira jamais : les bases
#: déjà en service portent la valeur sale (celle-ci l'avait depuis toujours), un
#: import ou une restauration peut la ramener, et rien n'oblige un administrateur
#: à passer par l'écran. On normalise donc **aux deux bouts** — ici à la lecture,
#: et dans `PUT /config` à l'écriture.
DEFAUT_SITE = "https://localhost"

#: Le nom du site quand la base n'en porte pas — **neutre, et c'est délibéré**.
#:
#: 🔴 « 5Hostachy » était écrit en dur DIX-SEPT fois dans `app/`, plus une
#: dix-huitième sous une autre valeur (« Ma Résidence », dans le moteur d'envoi).
#: C'est le nom propre de CETTE copropriété : le produit doit en servir une
#: autre, qui n'a « ni AFUL, ni quatre bâtiments » — et qui aurait vu le nom de
#: celle-ci en pied de ses courriels le jour où sa configuration serait vide.
#:
#: ⚠️ Ce n'est PAS la règle la plus déployée qui l'emporte ici, et c'est
#: l'exception que la règle prévoit : la plus déployée prime *si elle est en
#: phase avec les préconisations*. Un nom propre en dur ne l'est pas.
NOM_SITE_PAR_DEFAUT = "Ma Résidence"


def base_site(valeur: str | None) -> str:
    """L'adresse du site sans barre finale, prête à recevoir un chemin.

    >>> base_site("https://5hostachy.fr/")
    'https://5hostachy.fr'
    >>> base_site("https://5hostachy.fr")
    'https://5hostachy.fr'
    >>> base_site("  https://5hostachy.fr///  ")
    'https://5hostachy.fr'
    >>> base_site(None)
    'https://localhost'
    >>> base_site("   ")
    'https://localhost'

    ⚠️ Une valeur vide rend le DÉFAUT, jamais une chaîne vide : un lien
    `"/tickets/34"` sans domaine part quand même dans l'e-mail, et il n'y ouvre
    rien. Mieux vaut une adresse manifestement fausse qu'un lien muet — la
    première se voit, la seconde se clique.
    """
    propre = (valeur or "").strip().rstrip("/")
    return propre or DEFAUT_SITE


def nom_site(*valeurs: str | None) -> str:
    """Le nom du site : la première valeur renseignée, sinon un repli neutre.

    >>> nom_site("Les Quatre Saisons")
    'Les Quatre Saisons'
    >>> nom_site(None, "  Résidence du Parc  ")
    'Résidence du Parc'
    >>> nom_site(None)
    'Ma Résidence'
    >>> nom_site("")
    'Ma Résidence'
    >>> nom_site("   ")
    'Ma Résidence'

    🔴 **Dix-huit écritures, TROIS comportements** jusqu'au 14/09/2026 :

    ===================================  ==============================================
    Forme                                Ce qu'elle fait d'une valeur VIDE en base
    ===================================  ==============================================
    ``cfg.get("site_nom") or "…"``       repli (10 fois)
    ``cfg.get("site_nom", "…")``         **rend la chaîne vide** (7 fois)
    ``… or "Ma Résidence"``              repli, sous un AUTRE nom (1 fois)
    ===================================  ==============================================

    La deuxième ligne est un défaut : ``.get(cle, defaut)`` ne se replie que si la
    clé est **absente**. Une `site_nom` présente et vide — ce qu'un champ de
    configuration effacé produit — passait telle quelle, et le courriel annonçait
    une résidence sans nom. Sept chemins sur dix-huit, tous du côté dangereux.

    ⚠️ **Variadique**, parce que deux appelants lisent une configuration
    spécifique AVANT la générale (``site_cfg`` puis ``cfg``). Les aplatir en un
    seul argument aurait obligé chacun à réécrire la cascade — c'est-à-dire à
    recréer la duplication qu'on retire.

    ⚠️ Le ``strip()`` fait partie de la règle, comme dans `base_site` : une valeur
    saisie avec une espace de fin n'est pas une valeur différente.
    """
    for valeur in valeurs:
        propre = (valeur or "").strip()
        if propre:
            return propre
    return NOM_SITE_PAR_DEFAUT


def adresse_lisible(valeur: str | None) -> str:
    """L'adresse du site telle qu'on l'IMPRIME — sans protocole ni barre finale.

    >>> adresse_lisible("https://residence.example/")
    'residence.example'
    >>> adresse_lisible("http://residence.example")
    'residence.example'
    >>> adresse_lisible(None)
    'localhost'

    Elle part de `base_site`, donc du même repli : la fiche arrivant recevait
    une adresse sans protocole écrite en dur, et y préfixait `https://` (#1725).
    """
    return base_site(valeur).split("://", 1)[-1]


# préfixe d'ancre → route du front qui rend réellement `id="<prefixe>-…"`.
#
# La route est celle de l'ONGLET, pas seulement de la page : `/calendrier` est la vue
# liste (le Kanban ne pose pas d'id par événement), `/annonces` et `/idees` sont deux
# rubriques d'un même écran. C'est ce que `test_liens_front.py` vérifie ligne à ligne,
# en relisant la table des onglets du front.
EMPLACEMENTS: dict[str, str] = {
    #  « pub » (`/actualites`) est parti le 23/09/2026 avec la page : une
    #  actualité est une affaire, son adresse est celle de sa fiche (`lien_ticket`).
    #  « ev » et « ev_archive » (`/calendrier`) sont partis le 23/09/2026 : un
    #  événement est une affaire (#1092), son adresse celle de sa fiche. Les
    #  anciens liens `#ev-N` sont rattrapés par la page `/calendrier`.
    "presta": "/prestataires",
    "annonce": "/annonces",
    "idee": "/idees",
    "faq": "/faq",
    #  Un contrat d'entretien : sa fiche vit dans l'onglet Contrats des
    #  prestataires. Ajouté le 10/09/2026 avec le carnet d'entretien, qui y
    #  renvoie — fabriquer l'URL à la main aurait échappé à `test_liens_front`.
    "contrat": "/prestataires/contrats",
    "diag": "/residence",
    "doc": "/residence",
    #  Une question au règlement : l'onglet Règlement de Ma résidence la déplie
    #  (`OngletReglement`, `cibleDuHash`). Le fil y mène (11/10/2026), et les
    #  fichiers que l'assistant lit y sont joints — sans ancre, `page_element`.
    "question-reglement": "/residence/reglement",
}


def lien_element(prefixe: str, identifiant: int) -> str:
    """URL qui ouvre la page, sélectionne le bon onglet et révèle l'élément.

    >>> lien_element("presta", 23)
    '/prestataires#presta-23'
    >>> lien_element("annonce", 12)
    '/annonces#annonce-12'
    """
    try:
        route = EMPLACEMENTS[prefixe]
    except KeyError:
        raise KeyError(
            f"préfixe d'ancre inconnu : {prefixe!r}. Ajoutez-le à "
            f"EMPLACEMENTS (app/utils/liens.py) plutôt que de fabriquer "
            f"l'URL à la main — sinon la rubrique cible redevient une devinette."
        ) from None
    return f"{route}#{prefixe}-{identifiant}"


def page_element(prefixe: str) -> str:
    """Route seule (sans ancre) — pour un repli quand l'identifiant est inconnu."""
    return EMPLACEMENTS[prefixe]


def lien_sondage(sondage_id: int | None = None) -> str:
    """Fiche d'un sondage, ou la rubrique elle-même quand l'identifiant est inconnu.

    Un sondage a sa propre page (`/sondages/12`) : il n'a donc pas d'ancre, et rien
    à faire dans `EMPLACEMENTS`. Il a quand même sa place ICI — c'est la règle du
    module, et `signalements.py` écrivait ces deux formes à la main juste à côté de
    deux liens d'ancre qu'il fabriquait aussi lui-même.

    >>> lien_sondage(12)
    '/sondages/12'
    >>> lien_sondage()
    '/sondages'
    """
    return f"/sondages/{sondage_id}" if sondage_id else "/sondages"


#: L'onglet « Courriels » d'Espace CS : ce que la relève a fait de chaque message
#: reçu à l'adresse des affaires. Une alerte qui n'a pas d'affaire à nommer — un
#: transfert refusé, un numéro inconnu — y renvoie (05/10/2026).
LIEN_COURRIELS_AFFAIRES = "/espace-cs/courriels"


def lien_ticket(ticket_id: int, message_id: int | None = None) -> str:
    """URL d'un ticket, éventuellement ancrée sur un message précis.

    Les six URLs `/tickets/{id}` de tickets.py étaient fabriquées à la main,
    alors que ce module existe précisément pour que personne n'ait à le faire.
    Conséquence : une notification « nouvelle réponse » déposait le lecteur en
    haut de la page, à lui de retrouver ce qui avait déclenché l'alerte.
    Avec `message_id`, il arrive dessus.

    >>> lien_ticket(23)
    '/tickets/23'
    >>> lien_ticket(23, 45)
    '/tickets/23#msg-45'
    """
    base = f"/tickets/{ticket_id}"
    return f"{base}#msg-{message_id}" if message_id else base


#: Ce qu'un résident peut TRANSMETTRE par courriel depuis son 🔗 (#1357) — le
#: préfixe d'ancre, et ce qu'il désigne, écrit pour une phrase (« X vous
#: transmet une petite annonce »). Le lien se RECONSTRUIT ici à partir du type
#: et de l'identifiant : l'écran n'envoie jamais un chemin ni un texte libre, si
#: bien que le courriel ne peut mener qu'à une page de ce site.
#:
#: ⚠️ Le TITRE n'y figure pas : le donner supposerait de vérifier que
#: l'expéditeur peut lire l'objet, et tous les types n'ont pas de règle de
#: lecture écrite. Le destinataire se connecte ; sans droits, il ne voit rien.
#: L'affaire, elle, a la sienne (`ticket_visible`) : son titre part.
OBJETS_TRANSMISSIBLES: dict[str, str] = {
    "annonce": "une petite annonce",
    "idee": "une idée",
    "faq": "une question de la FAQ",
    "sondage": "un sondage",
    "doc": "un document",
    "diag": "un rapport de diagnostic",
    "contrat": "un contrat",
    "presta": "une fiche prestataire",
}


def lien_transmissible(objet: str, identifiant: int) -> str:
    """Le lien d'un objet de `OBJETS_TRANSMISSIBLES` — `KeyError` sinon."""
    if objet not in OBJETS_TRANSMISSIBLES:
        raise KeyError(objet)
    return lien_sondage(identifiant) if objet == "sondage" else lien_element(objet, identifiant)
