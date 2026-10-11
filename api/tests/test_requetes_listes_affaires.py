"""Les deux écrans les plus ouverts ne font pas une requête par affaire (#1838).

`GET /tickets` (Affaires) et `GET /flux` (Accueil) répondaient en 300 à 470 ms
en production : `ticket_read` relisait, POUR CHAQUE affaire, son auteur, son
bâtiment, son prestataire, son contrat, ses relances et — faute de pièce
propre — tout son fil ; le fil construisait une carte par évolution avant d'en
garder une par affaire. Sous PostgreSQL, chaque requête coûte ~50 ms de plus
qu'en SQLite : N affaires, N fois ce prix.

## Ce que ces tests tiennent

Le NOMBRE de requêtes SQL d'une lecture ne dépend pas du nombre d'affaires :
le même compte pour 5 et pour 40. Un plafond absolu dirait seulement « pas
trop » ; l'égalité dit « pas une de plus par affaire », ce qui est le défaut.
La prochaine colonne dérivée qui relirait sa table affaire par affaire fait
échouer ce test, pas la production. Le module qui groupe ces lectures est
`app/routers/tickets/lecture_groupee`.

Les affaires sont VARIÉES — chaque champ dérivé de `ticket_read` y a sa
source : auteur à bâtiment, « saisi pour » un inscrit, prestataire, contrat,
relances, pièce portée par le fil seulement, affaire fusionnée, affaire liée.
Une affaire uniforme laisserait un chemin de lecture sans mesure.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlalchemy import event
from sqlmodel import Session

from app.models.copropriete import Copropriete
from app.models.affaires_liees import AffaireLiee
from app.models.core import Batiment, RoleUtilisateur, Ticket, TicketEvolution
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils import horloge
from tests.aides_base import compte
from tests.aides_http import base_http, client_http


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@contextmanager
def _compteur(moteur):
    """Le nombre de requêtes émises sur ce moteur pendant le bloc."""
    vues: list[str] = []

    def _noter(_conn, _curseur, instruction, *_args):
        vues.append(instruction)

    event.listen(moteur, "before_cursor_execute", _noter)
    try:
        yield vues
    finally:
        event.remove(moteur, "before_cursor_execute", _noter)


def _peupler(moteur, n: int, *, auteur_id: int) -> None:
    """`n` affaires, chacune avec TOUTES les sources d'un champ dérivé."""
    maintenant = horloge.maintenant()
    veille = maintenant - timedelta(days=1)
    with Session(moteur) as s:
        copro = Copropriete(nom="Témoin", adresse="1 rue Témoin")
        s.add(copro)
        s.flush()
        tickets: list[Ticket] = []
        for i in range(n):
            bat = Batiment(copropriete_id=copro.id, numero=str(i + 1))
            presta = Prestataire(nom=f"Presta {i}", specialite="plomberie")
            s.add(bat)
            s.add(presta)
            s.flush()
            contrat = ContratEntretien(
                copropriete_id=copro.id, prestataire_id=presta.id, libelle=f"Contrat {i}"
            )
            s.add(contrat)
            s.flush()
            redacteur = compte(s, prefixe=f"redacteur{i}", batiment_id=bat.id)
            beneficiaire = compte(s, prefixe=f"beneficiaire{i}")
            t = Ticket(
                numero=f"TK-{i:06d}",
                titre=f"Affaire {i}",
                description="<p>Une fuite.</p>",
                auteur_id=redacteur.id if i % 2 else auteur_id,
                saisi_pour_user_id=beneficiaire.id if i % 3 == 0 else None,
                prestataire_id=presta.id,
                contrat_id=contrat.id,
                cree_le=maintenant,
            )
            s.add(t)
            s.flush()
            tickets.append(t)
            for type_evolution, contenu, fichiers, quand in (
                ("commentaire", "Constat initial.", '["/uploads/ancien.jpg"]', veille),
                ("relance", "Relance syndic", None, maintenant),
                (
                    "commentaire",
                    "Le plombier passe demain.",
                    '["/uploads/constat.jpg"]',
                    maintenant,
                ),
                ("etat", None, None, maintenant),
            ):
                s.add(
                    TicketEvolution(
                        ticket_id=t.id,
                        type=type_evolution,
                        contenu=contenu,
                        fichiers_urls=fichiers,
                        ancien_statut="ouvert" if type_evolution == "etat" else None,
                        nouveau_statut="en_cours" if type_evolution == "etat" else None,
                        auteur_id=redacteur.id,
                        cree_le=quand,
                    )
                )
        #  Une fusion et un lien : leurs lectures passent aussi par la liste.
        tickets[1].fusionnee_dans_id = tickets[0].id
        s.add(tickets[1])
        s.commit()
        s.add(AffaireLiee(affaire_id=tickets[0].id, liee_id=tickets[2].id))
        s.commit()


def _requetes(route: str, n: int, role: RoleUtilisateur) -> list[str]:
    with base_http() as moteur:
        http, ident = client_http(moteur, role)
        _peupler(moteur, n, auteur_id=ident)
        with _compteur(moteur) as vues:
            reponse = http.get(route)
        assert reponse.status_code == 200, reponse.text
        return vues


def _repetees(vues: list[str]) -> str:
    """Les requêtes les plus répétées — celles qui se font affaire par affaire."""
    compte = Counter(" ".join(v.split())[:120] for v in vues)
    return "\n".join(f"  {n} × {sql}" for sql, n in compte.most_common(6))


#  L'administrateur lit tout ; le propriétaire passe par la règle de lecture
#  complète (`ticket_visible`), et lit au moins ses propres affaires — la moitié.
@pytest.mark.usefixtures("arbre_vide")
@pytest.mark.parametrize("role", [RoleUtilisateur.admin, RoleUtilisateur.propriétaire])
@pytest.mark.parametrize("route", ["/tickets", "/flux"])
def test_le_compte_de_requetes_ne_croit_pas_avec_les_affaires(route, role):
    peu, beaucoup = _requetes(route, 5, role), _requetes(route, 40, role)
    assert len(peu) == len(beaucoup), (
        f"{route} : {len(peu)} requêtes pour 5 affaires, {len(beaucoup)} pour 40 — une "
        "lecture se fait affaire par affaire. La grouper (une requête pour toute la "
        f"liste, #1838). Les plus répétées, pour 40 :\n{_repetees(beaucoup)}"
    )


@pytest.mark.usefixtures("arbre_vide")
def test_la_liste_rend_ce_que_rend_la_fiche():
    """Lue en groupe, chaque affaire est celle que rend sa fiche — champ pour champ.

    Et les champs dérivés sont justes : la pièce de repli est celle de l'entrée
    de fil la plus RÉCENTE (#464), une relance se compte, le prestataire, le
    contrat, la fusion et le lien se lisent.
    """
    with base_http() as moteur:
        http, ident = client_http(moteur, RoleUtilisateur.admin)
        _peupler(moteur, 6, auteur_id=ident)
        liste = http.get("/tickets").json()
        assert len(liste) == 6
        for affaire in liste:
            assert http.get(f"/tickets/{affaire['id']}").json() == affaire, affaire["numero"]
    par_numero = {a["numero"]: a for a in liste}
    premiere, absorbee = par_numero["TK-000000"], par_numero["TK-000001"]
    assert premiere["apercu_pieces"] == ["/uploads/constat.jpg"]
    assert premiere["relance_count"] == 1
    assert premiere["prestataire_nom"] == "Presta 0"
    assert premiere["contrat"]["libelle"] == "Contrat 0"
    assert [lie["numero"] for lie in premiere["affaires_liees"]] == ["TK-000002"]
    assert absorbee["fusionnee_dans"]["numero"] == "TK-000000"
    assert absorbee["auteur_batiment_nom"]
