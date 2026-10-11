"""Flux — rubrique Tickets : ouvertures, changements d'état, réponses, commentaires.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

## Ce qui a été factorisé en même temps

Les quatre sources d'une ligne de ticket (état, réponse du CS, commentaire,
ticket neuf) recopiaient la même cascade de périmètre, et les blocs « réponse »
et « commentaire » étaient identiques **au caractère près** hors trois valeurs —
libellé, icône et préfixe d'identifiant — commentaire de six lignes compris,
recopié tel quel dans les deux. Deux écritures d'une même carte, c'est-à-dire
deux endroits à corriger : le 07/08/2026, il en a manqué un et la photo d'un
commentaire est restée invisible dans le fil.

Il n'en reste qu'une écriture : `_carte_mise_a_jour`, alimentée par
`_MISES_A_JOUR`. Ajouter un type d'évolution au fil est désormais une ligne de
table, pas un quatrième bloc à recopier.
"""

from functools import partial

from sqlmodel import select

from app.models.core import STATUTS_TICKET_ACTIFS, Ticket, TicketEvolution, Utilisateur
from app.utils.nature_affaire import ACTUALITE
from app.utils.dates_fr import duree_jhm
from app.utils.photos import parse_photos
from app.utils.recuperer import precharger
from app.utils.visibility import ticket_visible

from app.utils.copie_auteur import proprietaire
from .commun import (
    ContexteFlux,
    auteur_nom,
    badges_ticket,
    pastilles_affaire,
    perimetres_de,
    pieces_de_evolution,
    strip_html,
)
from .schemas import FluxItem
from app.utils.corrections import est_correction

#: Évolutions qui produisent une carte « ticket mis à jour » sans changer l'état.
#: (type en base, préfixe d'identifiant, libellé, icône)
#:
#: 🔴 LES ICÔNES SONT CELLES DE `front/src/lib/evolutions.ts`, et elles doivent le
#: rester. Le 19/08/2026, la même notion était écrite QUATRE fois avec TROIS
#: valeurs : le bouton disait « 💬 Commenter », les deux fils affichaient 📝, et
#: cette table 🔧. Signalé à l'écran — *« pourquoi mon commentaire a une icône de
#: type relance ? »*.
#:
#: ⚠️ Front et API ne peuvent pas partager ce fichier : les contextes de build
#: sont `./api` et `./front`, rien de la racine n'entre dans les images. Les deux
#: écritures sont donc inévitables — c'est `api/tests/test_icones_evolution.py`
#: qui les empêche de diverger, pas la bonne volonté.
#:
#: Le LIBELLÉ, lui, reste propre à cet écran : « Mise à jour » décrit une carte de
#: flux, pas une entrée de fil. Ce sont deux rendus du même fait, et seule
#: l'icône est commune.
_MISES_A_JOUR = (
    ("reponse", "tk_rep", "Réponse du CS", "↩️"),
    ("commentaire", "tk_com", "Mise à jour", "💬"),
)


def _meta_ticket(ctx: ContexteFlux, tk) -> dict:
    """Le socle de `meta` commun aux quatre cartes de ticket.

    🔴 `auteur` ajouté le 11/09/2026, signalé à l'écran : le fil ne disait pas
    QUI avait déposé le ticket, alors que sa propre carte le porte depuis le
    18/08 — « état, puis 🔹 périmètre, puis les marqueurs, puis l'auteur », un
    ordre lui-même repris de l'actualité. Le fil était le seul écran à ne pas
    suivre la règle, et il est celui qu'on regarde en premier.

    ⚠️ Il vit ICI, dans le socle des QUATRE cartes : l'écrire dans chacune aurait
    donné quatre occasions de l'oublier — c'est d'ailleurs ce qui vient d'arriver
    aux pièces jointes (#531).
    """
    return {
        "ticket_id": tk.id,
        "numero": tk.numero,
        "perimetre_codes": perimetres_de(tk),
        "description": strip_html(tk.description, 300),
        #  🔴 Le PROPRIÉTAIRE, pas celui qui a tapé (12/09/2026) : quand le
        #  conseil syndical enregistre le signalement d'un résident ou d'un
        #  intervenant, c'est ce dernier que le fil doit nommer. La règle vit dans
        #  `copie_auteur.proprietaire` — celle-là même qui décide à qui part la
        #  copie, pour que le nom lu et le destinataire servi soient la même
        #  personne.
        "auteur": proprietaire(ctx.session, tk)[0],
        #  La ligne de pastilles de la carte d'affaire, rendue telle quelle (27/09).
        "affaire": pastilles_affaire(tk),
    }


def _carte_mise_a_jour(ctx: ContexteFlux, evol, tk, *, ident, detail, icon, statut) -> FluxItem:
    """Carte « ticket mis à jour » — la seule écriture, pour les trois origines.

    Les pièces jointes de l'**évolution** priment sur celles du ticket. La carte
    annonce une mise à jour et affiche déjà `evol_contenu` : lui faire porter les
    photos d'origine montrerait une image vieille de dix jours à côté d'un texte
    du jour. Repli sur le ticket si l'évolution n'en porte aucune, pour ne rien
    retirer aux cartes qui fonctionnaient.

    Constaté le 07/08/2026 : les blocs « réponse » et « commentaire » n'émettaient
    aucune clé de pièce jointe, donc la carte du fil ne pouvait rien afficher même
    quand l'évolution en portait — alors que la photo l'était déjà dans le ticket
    et dans l'e-mail.
    """
    return FluxItem(
        id=ident,
        type="ticket_mis_a_jour",
        date=evol.cree_le,
        cree_le=tk.cree_le,
        titre=tk.titre,
        detail=detail,
        icon=icon,
        badges=badges_ticket(tk),
        lien="/tickets",
        meta={
            **_meta_ticket(ctx, tk),
            "statut": statut,
            **pieces_de_evolution(evol, tk),
            #  ⚠️ 400 et non 300 (#531). La carte PLIÉE affiche désormais cet
            #  extrait sous le libellé, sur trois lignes au plus (`clamp-3`).
            #  300 caractères en remplissent 2,3 : la coupure venait de la
            #  longueur, pas du gabarit — l'extrait s'arrêtait avant que les
            #  trois lignes soient atteintes, et le réglage visible n'était
            #  donc pas celui qui décidait.
            "evol_contenu": strip_html(evol.contenu, 400) if evol.contenu else None,
            "evol_auteur": auteur_nom(ctx.session, evol.auteur_id),
        },
    )


def _evolutions(ctx: ContexteFlux, type_evolution: str):
    """Les évolutions d'un type donné, ticket joint, les plus récentes d'abord."""
    return ctx.session.exec(
        select(TicketEvolution, Ticket)
        .join(Ticket, TicketEvolution.ticket_id == Ticket.id)
        .where(
            TicketEvolution.type == type_evolution,
            TicketEvolution.cree_le >= ctx.since,
            #  Une actualité a sa rubrique (`publications`) : ici, elle
            #  paraîtrait une seconde fois, sous une autre forme (#1091).
            Ticket.categorie != ACTUALITE,
        )
        .order_by(TicketEvolution.cree_le.desc())
    ).all()


def _carte_resolue(ctx: ContexteFlux, evol, tk) -> FluxItem:
    """Carte « ticket résolu », avec la durée de résolution."""
    #  🔴 `00j23h54'`, et non un arrondi décimal d'heures (01/09/2026,
    #  demandé à l'écran). « Résolu en 23.9h » n'a de sens nulle part
    #  ailleurs sur le site et se convertit de tête ; le point décimal
    #  était en prime un point sur un site intégralement en français.
    #  Les unités sont portées : `00:00:30` se lisait trente secondes
    #  alors qu'il voulait dire trente minutes.
    #  Le format vit dans `dates_fr.duree_jhm` — une durée EST un format.
    duree = None
    if tk.ferme_le and tk.cree_le:
        duree = duree_jhm(tk.ferme_le - tk.cree_le)
    return FluxItem(
        id=f"tk_{tk.id}",
        type="ticket_resolu",
        date=evol.cree_le,
        cree_le=tk.cree_le,
        titre=tk.titre,
        #  ⚠️ `is not None` et non `if duree`. L'ancien code testait un
        #  FLOAT : une résolution en moins de six minutes s'arrondissait à
        #  `0.0`, donc falsy, et la mention disparaissait — le ticket le
        #  plus vite résolu était le seul à ne pas le dire. `duree_jhm`
        #  rend `None` sur une donnée incohérente, jamais sur un zéro.
        detail=f"Résolu{f' en {duree}' if duree is not None else ''}",
        icon="✅",
        badges=badges_ticket(tk),
        lien="/tickets",
        meta={
            **_meta_ticket(ctx, tk),
            "statut": "résolu",
            #  Le nom dit désormais ce que la valeur EST : plus des heures
            #  décimales, mais `00j23h54'`. Aucun écran ne la lisait — le
            #  renommer maintenant évite qu'un futur lecteur croie à un nombre.
            "duree": duree,
            "cloture_le": tk.ferme_le.isoformat() if tk.ferme_le else None,
            #  Même règle que les trois autres cartes de ticket : une photo
            #  jointe au commentaire de clôture doit se voir.
            **pieces_de_evolution(evol, tk),
        },
    )


def _carte_ouverte(ctx: ContexteFlux, _evol, tk) -> FluxItem:
    """Carte « nouveau ticket » — une affaire récente, sans aucune évolution."""
    return FluxItem(
        id=f"tk_{tk.id}",
        type="ticket_ouvert",
        date=tk.cree_le,
        cree_le=tk.cree_le,
        titre=tk.titre,
        detail="Nouveau ticket",
        icon="🎫",
        badges=badges_ticket(tk),
        lien="/tickets",
        meta={
            **_meta_ticket(ctx, tk),
            "statut": tk.statut,
            "photos_urls": parse_photos(tk.photos_urls),
            "fichiers_urls": parse_photos(tk.fichiers_urls),
        },
    )


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    """Une seule ligne par ticket : la plus récente.

    L'historique complet reste consultable sur la fiche du ticket — le fil n'est
    qu'un résumé « quoi de neuf ».

    🔴 L'entrée retenue se CHOISIT avant que sa carte se construise (#1838). Le
    fil construisait une carte par évolution de la période — propriétaire,
    auteur, extrait du texte — puis n'en gardait qu'une par affaire : 135
    lectures d'utilisateur pour 40 affaires. Chaque candidate est désormais une
    date et une fabrique ; seules les retenues sont fabriquées, et leurs
    personnes sont lues en une requête.
    """
    #  (ticket, date, évolution ou None, ticket, fabrique) — dans l'ordre où
    #  l'ancien code construisait ses cartes : à date égale, la PREMIÈRE vue
    #  l'emporte, comme avant.
    candidates: list[tuple] = []
    vus: set[int] = set()

    # ── Changements d'état ───────────────────────────────────────────────────
    for evol, tk in _evolutions(ctx, "etat"):
        if not ticket_visible(tk, ctx.user):
            continue
        vus.add(tk.id)
        nouveau = evol.nouveau_statut or ""
        if nouveau == "résolu":
            candidates.append((tk.id, evol.cree_le, evol, tk, _carte_resolue))
        elif nouveau in STATUTS_TICKET_ACTIFS:
            fabrique = partial(
                _carte_mise_a_jour,
                ident=f"tk_{tk.id}",
                detail="Réouvert" if nouveau == "ouvert" else "Pris en charge",
                icon="🔧",
                statut=nouveau,
            )
            candidates.append((tk.id, evol.cree_le, evol, tk, fabrique))

    # ── Réponses du CS et commentaires ───────────────────────────────────────
    for type_evolution, prefixe, detail, icon in _MISES_A_JOUR:
        for evol, tk in _evolutions(ctx, type_evolution):
            if not ticket_visible(tk, ctx.user):
                continue
            #  🔴 UNE CORRECTION N'EST PAS UNE NOUVELLE — même règle que les
            #  événements (01/09/2026). Corriger un ticket écrit « Correction :
            #  Périmètre » dans son Historique, et cela n'a rien à faire dans le
            #  fil de la copropriété. `app/utils/corrections.py`.
            if est_correction(evol):
                continue
            vus.add(tk.id)
            fabrique = partial(
                _carte_mise_a_jour,
                ident=f"{prefixe}_{evol.id}",
                detail=detail,
                icon=icon,
                statut=tk.statut,
            )
            candidates.append((tk.id, evol.cree_le, evol, tk, fabrique))

    # ── Tickets récemment créés, sans aucune évolution ───────────────────────
    for tk in ctx.session.exec(
        select(Ticket)
        .where(Ticket.cree_le >= ctx.since, Ticket.categorie != ACTUALITE)
        .order_by(Ticket.cree_le.desc())
    ).all():
        if tk.id in vus or not ticket_visible(tk, ctx.user):
            continue
        candidates.append((tk.id, tk.cree_le, None, tk, _carte_ouverte))

    # Un seul événement par ticket dans le fil : le plus récent.
    retenues: dict[int, tuple] = {}
    for candidate in candidates:
        tid, date = candidate[0], candidate[1]
        if tid not in retenues or date > retenues[tid][1]:
            retenues[tid] = candidate
    #  Les personnes que les cartes nomment, lues d'un coup ; la liste les retient
    #  le temps de la fabrication (`recuperer.precharger`).
    _personnes = precharger(
        ctx.session,
        Utilisateur,
        {
            i
            for _, _, evol, tk, _ in retenues.values()
            for i in (tk.auteur_id, tk.saisi_pour_user_id, evol.auteur_id if evol else None)
        },
    )
    return [fabrique(ctx, evol, tk) for _, _, evol, tk, fabrique in retenues.values()]
