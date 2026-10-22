"""Le courriel d'une affaire dit ses AFFAIRES LIÉES (05/10/2026, migration 0266).

Demandé : quand une affaire est liée à une autre, l'historique du courriel trace
le lien ; puis, **sous** l'historique, chaque affaire liée apparaît avec le sien,
de la plus ancienne à la plus récente.

Ce que ce fichier éprouve, du plus coûteux au moins coûteux :

1. une affaire liée **réservée au conseil** n'est NI nommée dans la trace NI
   reprise dans le bloc — le destinataire est le syndic, hors de la copropriété ;
2. le courriel RENDU porte le bloc, après l'historique, dans l'ordre de création
   des affaires — pas dans celui des liens ;
3. la migration 0266 produit sur une base existante le texte du seed ;
4. sans lien, rien ne change.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from markupsafe import escape
from sqlmodel import Session

from app.models.affaires_liees import AffaireLiee
from app.models.core import StatutTicket, Ticket, TicketEvolution
from app.models.exploitation import ModeleEmail
from app.routers.tickets.courriels import contexte_ticket_syndic
from app.routers.tickets.historique_courriel import (
    affaires_liees_du_courriel,
    lignes_historique,
)
from app.seed.emails.tickets import MODELES
from app.utils import horloge
from app.utils.email import _contexte_rendu, composer_email
from tests.aides_base import compte, moteur_de_test


def _affaire(session, auteur, titre, *, cree_le, confidentiel=False) -> Ticket:
    t = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6]}",
        titre=titre,
        description="…",
        categorie="panne",
        auteur_id=auteur.id,
        statut=StatutTicket.ouvert,
        confidentiel=confidentiel,
        cree_le=cree_le,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _lier(session, a: Ticket, b: Ticket, *, le) -> None:
    petit, grand = sorted((a.id, b.id))
    session.add(AffaireLiee(affaire_id=petit, liee_id=grand, cree_le=le))
    session.commit()


def _rendre(session, code, sujet, corps, ctx) -> str:
    """Le courriel tel qu'il part : le contexte complété par `_contexte_rendu`, comme l'aperçu."""
    complet, site_nom, site_url, pied = _contexte_rendu(session, ctx)
    modele = ModeleEmail(code=code, libelle="x", sujet=sujet, corps_html=corps)
    return composer_email(modele, complet, site_nom=site_nom, site_url=site_url, email_footer=pied)[
        1
    ]


def _monde():
    """Une affaire, et trois autres posées dans le désordre de leur création."""
    session = Session(moteur_de_test())
    cs = compte(session, prefixe="cs", roles_json="conseil_syndical")
    maintenant = horloge.maintenant()
    jour = timedelta(days=1)
    principale = _affaire(session, cs, "Fuite au 3e", cree_le=maintenant - 10 * jour)
    recente = _affaire(session, cs, "Tache au plafond", cree_le=maintenant - 2 * jour)
    ancienne = _affaire(session, cs, "Colonne d'eau", cree_le=maintenant - 20 * jour)
    secrete = _affaire(
        session, cs, "Litige de voisinage", cree_le=maintenant - 5 * jour, confidentiel=True
    )
    #  Liées dans l'ordre INVERSE de leur création : l'ordre du lien ne doit rien dicter.
    _lier(session, principale, recente, le=maintenant - 1 * jour)
    _lier(session, principale, secrete, le=maintenant - 1 * jour)
    _lier(session, principale, ancienne, le=maintenant)
    session.add(
        TicketEvolution(
            ticket_id=ancienne.id,
            type="commentaire",
            contenu="Le plombier passe lundi",
            auteur_id=cs.id,
            cree_le=maintenant - 15 * jour,
        )
    )
    session.commit()
    return session, cs, principale, ancienne, recente, secrete


def test_les_liees_se_rangent_par_creation_de_l_affaire_et_la_secrete_n_en_est_pas():
    session, cs, principale, ancienne, recente, secrete = _monde()
    ctx = contexte_ticket_syndic(principale, cs, session, pieces_jointes=[])

    assert [a["titre"] for a in ctx["affaires_liees"]] == [ancienne.titre, recente.titre]
    #  🔴 Ni le bloc, ni la trace ne nomment l'affaire réservée au conseil.
    texte = repr(ctx)
    assert secrete.titre not in texte and secrete.numero not in texte


def test_l_historique_trace_le_lien_et_chaque_liee_porte_le_sien():
    session, cs, principale, ancienne, recente, _s = _monde()
    ctx = contexte_ticket_syndic(principale, cs, session, pieces_jointes=[])

    traces = [h["label"] for h in ctx["historique"] if h["label"].startswith("Liée à")]
    assert traces == [
        f"Liée à l’affaire #{recente.numero} — {recente.titre}",
        f"Liée à l’affaire #{ancienne.numero} — {ancienne.titre}",
    ]
    #  La création reste la première ligne, le lien le plus récent la dernière.
    assert ctx["historique"][0]["label"] == "Création du ticket"
    assert (
        ctx["historique"][-1]["label"].startswith("Liée à")
        and ancienne.titre in (ctx["historique"][-1]["label"])
    )

    historique_ancienne = ctx["affaires_liees"][0]["historique"]
    assert [h["label"] for h in historique_ancienne] == [
        "Création du ticket",
        "Commentaire : Le plombier passe lundi",
    ]


def test_le_courriel_rendu_place_les_liees_apres_l_historique():
    session, cs, principale, ancienne, recente, secrete = _monde()
    ctx = contexte_ticket_syndic(principale, cs, session, pieces_jointes=[])
    code, _l, sujet, corps, _d = next(m for m in MODELES if m[0] == "ticket_syndic")
    html = _rendre(session, code, sujet, corps, ctx)

    assert html.index("Historique") < html.index("Affaires liées")
    #  Ordre de CRÉATION des affaires, pas du lien : l'ancienne d'abord.
    bloc = html[html.index("Affaires liées") :]
    #  Le corps s'échappe (#2150) : « Colonne d'eau » s'écrit « Colonne d&#39;eau ».
    assert bloc.index(escape(ancienne.titre)) < bloc.index(escape(recente.titre))
    assert "Le plombier passe lundi" in bloc
    assert secrete.titre not in html


def test_sans_lien_rien_ne_change():
    session = Session(moteur_de_test())
    cs = compte(session, prefixe="cs", roles_json="conseil_syndical")
    seule = _affaire(session, cs, "Seule", cree_le=horloge.maintenant())
    ctx = contexte_ticket_syndic(seule, cs, session, pieces_jointes=[])
    code, _l, sujet, corps, _d = next(m for m in MODELES if m[0] == "ticket_syndic")
    html = _rendre(session, code, sujet, corps, ctx)
    assert ctx["affaires_liees"] == []
    assert "Affaires liées" not in html


def test_historique_courriel_les_liees_montrables_et_l_ordre_des_lignes():
    """`historique_courriel` en direct : qui est montrable, et comment les lignes se rangent."""
    session, _cs, principale, ancienne, recente, secrete = _monde()

    liees = affaires_liees_du_courriel(session, principale)
    assert [t.id for t, _le in liees] == [ancienne.id, recente.id]
    assert secrete.id not in [t.id for t, _le in liees]

    #  Un lien posé AVANT une évolution se range avant elle : le tri suit le temps.
    evolution = TicketEvolution(
        ticket_id=principale.id,
        type="commentaire",
        contenu="Visite du syndic",
        auteur_id=principale.auteur_id,
        cree_le=horloge.maintenant() - timedelta(hours=12),
    )
    labels = [h["label"] for h in lignes_historique(principale, [evolution], liees)]
    assert labels[0] == "Création du ticket"
    assert labels[1].startswith("Liée à") and recente.titre in labels[1]
    assert labels[2].startswith("Commentaire")
    assert labels[3].startswith("Liée à") and ancienne.titre in labels[3]

    #  Un ticket non persisté (aperçu d'une création) n'a aucun lien.
    neuf = Ticket(numero="TK-neuf", titre="t", description="d", auteur_id=principale.auteur_id)
    assert affaires_liees_du_courriel(session, neuf) == []
