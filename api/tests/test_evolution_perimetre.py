"""Le périmètre d'un ticket se PRÉCISE par le fil, sans jamais s'élargir tout seul.

## Pourquoi ce garde-fou (#497, 19/08/2026)

Demandé sur un cas réel : *« le périmètre de la fuite pourrait être précisé et
évolue »*. Un ticket se signale avec ce qu'on sait au moment où on le signale —
donc souvent le périmètre le plus large, parce qu'on ignore d'où ça vient. Puis
on cherche, et « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ».

L'arbitrage retenu : **l'évolution porte son périmètre**, et le périmètre courant
du ticket est celui de la dernière évolution qui en déclare un.

🔴 **Le risque que ce fichier couvre est l'inverse du besoin.** Le besoin est
qu'un périmètre déclaré s'applique ; le risque est qu'un commentaire ordinaire —
il y en a des dizaines par ticket, et aucun ne parle de périmètre — vienne
écraser un périmètre patiemment resserré. Une valeur par défaut mal placée, un
`[]` envoyé au lieu d'un `None`, et le ticket repart à « toute la résidence »
sans que personne ne comprenne pourquoi. C'est ce que vérifie le premier test, et
c'est pour cette raison que la colonne 0154 n'a **pas** de `server_default`.

⚠️ Ces tests vérifient **le fait** en relisant la base après l'appel, pas le code
de retour de l'endpoint (`standards/04` §14 — observer la chose, pas son
enregistrement).
"""

from __future__ import annotations


import json
import uuid

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    Ticket,
    TicketEvolution,
)
from app.routers.tickets.evolutions import add_evolution
from app.schemas import TicketEvolutionCreate, TicketEvolutionUpdate

#  🔴 La purge passe par le code de PRODUCTION : supprimer une ligne sans ce
#  qui la référence est ce que les clés étrangères refusent (#546).
from tests.aides_fil import cs  # noqa: F401 — fixture importée par son nom (#2950)
from tests.aides_purge import purger_ligne

BAT_2 = ["bat:2"]
PRECIS = ["bat:2", "cave"]


def _ticket(session: Session, auteur_id: int, perimetre: list[str]) -> Ticket:
    t = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6].upper()}",
        titre="Fuite d'eau",
        description="<p>De l'eau coule dans la cage d'escalier.</p>",
        categorie="panne",
        statut="ouvert",
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(perimetre, ensure_ascii=False),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _nettoyer(session: Session, ticket_id: int) -> None:
    for e in session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket_id)
    ).all():
        session.delete(e)
    purger_ligne(session, Ticket, ticket_id)
    session.commit()


def test_un_commentaire_ordinaire_ne_touche_pas_au_perimetre(cs):
    """🔴 Le cas qui casserait tout : la dizaine de commentaires sans périmètre.

    Aucun ne parle de périmètre. Si l'un d'eux le remettait à sa valeur par
    défaut, le resserrement obtenu au commentaire précédent serait perdu — et
    l'auteur du commentaire n'aurait rien fait de mal.
    """
    with Session(engine) as session:
        ticket = _ticket(session, cs.id, BAT_2)

        add_evolution(
            ticket.id,
            TicketEvolutionCreate(type="commentaire", contenu="<p>Le plombier passe demain.</p>"),
            BackgroundTasks(),
            session,
            cs,
        )

        apres = session.get(Ticket, ticket.id)
        assert json.loads(apres.perimetre_cible) == BAT_2, (
            "Un commentaire qui ne parle pas du périmètre ne doit RIEN y changer : "
            f"trouvé {apres.perimetre_cible}."
        )
        evol = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).first()
        assert evol.perimetre_cible is None, (
            "L'entrée ne doit déclarer AUCUN périmètre — `None`, et surtout pas "
            f"une liste vide : trouvé {evol.perimetre_cible!r}."
        )
        _nettoyer(session, ticket.id)


def test_une_liste_vide_ne_vaut_pas_declaration(cs):
    """`[]` arrive quand un sélecteur est ouvert puis refermé sans rien choisir.

    Ce n'est pas « plus aucun périmètre » : c'est « je n'ai rien dit ». Un ticket
    sans périmètre n'existe pas, et le front n'envoie donc jamais `[]` — mais un
    appel direct à l'API, lui, le peut.
    """
    with Session(engine) as session:
        ticket = _ticket(session, cs.id, BAT_2)

        add_evolution(
            ticket.id,
            TicketEvolutionCreate(type="commentaire", contenu="<p>RAS.</p>", perimetre_cible=[]),
            BackgroundTasks(),
            session,
            cs,
        )

        assert json.loads(session.get(Ticket, ticket.id).perimetre_cible) == BAT_2
        _nettoyer(session, ticket.id)


def test_un_perimetre_declare_devient_celui_du_ticket(cs):
    """Le besoin lui-même : on a trouvé d'où venait la fuite."""
    with Session(engine) as session:
        ticket = _ticket(session, cs.id, BAT_2)

        add_evolution(
            ticket.id,
            TicketEvolutionCreate(
                type="commentaire",
                contenu="<p>La fuite vient de la cave.</p>",
                perimetre_cible=PRECIS,
            ),
            BackgroundTasks(),
            session,
            cs,
        )

        assert json.loads(session.get(Ticket, ticket.id).perimetre_cible) == PRECIS
        evol = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).first()
        assert json.loads(evol.perimetre_cible) == PRECIS, (
            "L'entrée doit GARDER ce qu'elle a déclaré : c'est tout l'historique "
            "du resserrement, et c'est ce qu'on a demandé à voir."
        )
        _nettoyer(session, ticket.id)


def test_le_dernier_perimetre_declare_l_emporte(cs):
    """« Le périmètre courant est celui de la DERNIÈRE évolution qui en déclare un. »

    Et les entrées muettes intercalées ne comptent pas — c'est la combinaison des
    deux règles qui fait le comportement attendu, pas chacune isolément.
    """
    with Session(engine) as session:
        ticket = _ticket(session, cs.id, ["résidence"])

        for corps in (
            TicketEvolutionCreate(
                type="commentaire", contenu="<p>Signalé.</p>", perimetre_cible=BAT_2
            ),
            TicketEvolutionCreate(type="commentaire", contenu="<p>Le plombier cherche.</p>"),
            TicketEvolutionCreate(
                type="commentaire", contenu="<p>Trouvé : la cave.</p>", perimetre_cible=PRECIS
            ),
            TicketEvolutionCreate(type="commentaire", contenu="<p>Réparé.</p>"),
        ):
            add_evolution(ticket.id, corps, BackgroundTasks(), session, cs)

        assert json.loads(session.get(Ticket, ticket.id).perimetre_cible) == PRECIS

        declares = [
            json.loads(e.perimetre_cible) if e.perimetre_cible else None
            for e in session.exec(
                select(TicketEvolution)
                .where(TicketEvolution.ticket_id == ticket.id)
                .order_by(TicketEvolution.id)
            ).all()
        ]
        assert declares == [BAT_2, None, PRECIS, None], (
            f"Le fil doit garder qui a déclaré quoi, et qui n'a rien dit : trouvé {declares}."
        )
        _nettoyer(session, ticket.id)


def test_le_perimetre_SE_CORRIGE_sur_une_entree():
    """🔴 DÉCISION ROUVERTE le 01/09/2026, et écrite ici.

    Ce test affirmait l'inverse — « une correction ne peut pas réécrire un
    périmètre déclaré » — et il disait déjà quoi faire le jour où l'on
    changerait d'avis : *« ce n'est pas ce test qu'il faut changer, c'est la
    décision de #497 qu'il faut rouvrir, et l'écrire »*.

    Elle est rouverte, à l'écran :

    > *« L'édition peut modifier le périmètre (correction d'erreur
    > d'affectation d'un périmètre) »*

    Le motif d'origine — un périmètre déclaré est un fait daté — vaut pour un
    RESSERREMENT, pas pour une faute de clic. Et la faute coûte cher : le
    périmètre d'une entrée écrase celui du ticket, donc une erreur
    d'affectation reclasse tout le ticket.
    """
    assert "perimetre_cible" in TicketEvolutionUpdate.model_fields, (
        "Le champ a disparu du schéma : le formulaire proposerait un périmètre "
        "que Pydantic ignorerait en silence, et le PATCH rendrait 200 sans rien "
        "faire. C'est le pire des deux mondes."
    )


def test_corriger_une_ANCIENNE_entree_ne_defait_pas_une_precision_recente():
    """⚠️ La subtilité de la règle, et la seule qui se perde.

    Trois commentaires resserrent le périmètre ; on corrige le PREMIER. Le
    ticket doit garder ce que le DERNIER a dit — sinon corriger une vieille
    faute de frappe reclasserait le ticket sur un périmètre abandonné depuis,
    ce qui ne se verrait que sur une liste filtrée.

    La décision est pure et vit dans `app/utils/perimetre_fil.py`, avec son
    `--selftest`. Ce test-ci vérifie qu'elle est bien CÂBLÉE : une fonction
    juste que personne n'appelle ne protège de rien.
    """
    import json as _json

    from app.utils.perimetre_fil import doit_propager

    class _E:
        def __init__(self, id, cible):
            self.id = id
            self.perimetre_cible = _json.dumps(cible) if cible else None

    ancienne, muette, recente = _E(1, BAT_2), _E(2, None), _E(3, PRECIS)
    fil = [ancienne, muette, recente]
    assert not doit_propager(ancienne, fil), (
        "Corriger la PREMIÈRE entrée ne doit pas défaire ce que la dernière a précisé."
    )
    assert doit_propager(recente, fil)
    #  Et le cas zéro : une entrée qui ne dit plus rien n'impose rien.
    assert not doit_propager(muette, fil)
