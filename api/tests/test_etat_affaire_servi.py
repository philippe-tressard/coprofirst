"""L'état d'une affaire en clair est SERVI partout où un écran le montre (#2633).

## 🔴 Le défaut

Le site composait le libellé d'un état dans son front (`statutTicketLabel`) pour
les Suites du fil, la ligne du fil (une idée, une annonce), les affaires liées et
les comptes rendus d'un point CS / Syndic — tous servis en CODES. L'app iOS ne
recopie aucune règle du site : elle n'avait que le code. La règle vit désormais
dans `utils/etat_affaire.libelle_etat`, et chaque réponse la sert.

## Sans régression

Le front gardait la table de ses libellés (`STATUT_TICKET_LABELS`) pour ses
options ; le premier test exige qu'elle dise, libellé par libellé, ce que le
serveur sert — `test_statuts_tickets.py` ne comparait que les CLÉS.
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime

import pytest

from app.models.tickets import StatutTicket
from app.routers.points_conseil_schemas import CrRead
from app.schemas_tickets import TicketEvolutionRead
from app.utils.etat_affaire import STATUT_LABELS, libelle_etat

_TICKETS_TS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "tickets.ts"


def _libelles_du_front() -> dict[str, str]:
    """Les libellés de `#lib/tickets.ts` : le cycle, l'historique, le sans-cycle."""
    src = _TICKETS_TS.read_text(encoding="utf-8")
    bloc = re.search(r"export const STATUTS_TICKET\s*:[^=]*=\s*\[(.*?)\];", src, re.S)
    assert bloc, "STATUTS_TICKET introuvable dans front/src/lib/tickets.ts"
    cycle = re.findall(r"value:\s*'([^']+)',\s*label:\s*'([^']+)'", bloc.group(1))
    autres = re.findall(r"^\t(\w+|'[^']+'):\s*\{\s*label:\s*'([^']+)'", src, re.M)
    return {**dict(cycle), **{k.strip("'"): v for k, v in autres}}


def test_le_front_dit_chaque_etat_comme_le_serveur():
    front = _libelles_du_front()
    #  Cas zéro : une lecture qui ne trouve rien conclurait au vert (`standards/04` §2).
    assert len(front) >= len(StatutTicket), f"libellés du front mal lus : {front}"
    assert front == STATUT_LABELS


@pytest.mark.parametrize(
    "statut, attendu",
    [
        (StatutTicket.en_cours, "Chez le syndic"),
        ("en_ag", "À l’AG"),
        ("fermé", "Fermé"),
        ("publie", "Publiée"),
        #  L'état d'une idée ou d'une annonce, que la table ne connaît pas : brut.
        ("en_attente", "en_attente"),
        (None, ""),
        ("", ""),
    ],
)
def test_libelle_etat(statut, attendu):
    """Ce que rendait `statutTicketLabel` : la table, la valeur brute à défaut, vide sans état."""
    assert libelle_etat(statut) == attendu


def test_une_suite_sert_l_etat_qu_elle_donne():
    lue = TicketEvolutionRead(
        id=1, ticket_id=1, type="etat", nouveau_statut="résolu", cree_le=datetime(2026, 11, 1)
    )
    assert lue.model_dump()["nouveau_statut_libelle"] == "Résolu"
    commentaire = TicketEvolutionRead(
        id=2, ticket_id=1, type="commentaire", cree_le=datetime(2026, 11, 1)
    )
    assert commentaire.model_dump()["nouveau_statut_libelle"] == ""


@pytest.mark.parametrize(
    "cible, attendu", [("chez_prestataire", "Chez le prestataire"), (None, "")]
)
def test_un_compte_rendu_sert_l_etat_decide(cible, attendu):
    cr = CrRead(
        ticket_id=1,
        contenu="",
        brouillon=False,
        conseil_seul=False,
        etat_cible=cible,
        mis_a_jour_le=datetime(2026, 11, 1),
    )
    assert cr.model_dump()["etat_cible_libelle"] == attendu


def test_une_affaire_liee_sert_son_etat():
    from app.models.core import Ticket
    from app.utils.affaires_liees import _lue

    lue = _lue(Ticket(id=1, numero="TK-1", titre="Fuite", statut="en_cours"))
    assert (lue["statut"], lue["statut_libelle"]) == ("en_cours", "Chez le syndic")


def test_la_ligne_du_fil_porte_les_libelles_d_etat():
    from app.routers.flux.commun import CHAMPS_PASTILLES

    assert {"statut_libelle", "suivi_actualite_libelle"} <= set(CHAMPS_PASTILLES)
