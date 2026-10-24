"""La synthèse d'une affaire close, de la clôture au carnet (#1643).

Les garde-fous du ticket, sur une base en mémoire et par les vraies fonctions
du routeur `routers/tickets/synthese` et du fil (`get_evolutions`) :

- une clôture inscrit UNE demande, quelle que soit la catégorie (21/10/2026) ;
- la file attend son délai de grâce, puis produit une Suite `synthese` en
  brouillon — vide, avec son motif, quand l'assistant est coupé ;
- **un seul courriel par production** : ni une seconde passe de la file, ni une
  relance n'en renvoient ;
- **une Suite non validée est invisible d'un lecteur ordinaire**, dans le fil
  comme dans la synthèse ; validée, elle se lit, et entre au carnet ;
- une réouverture puis une nouvelle clôture remplacent la synthèse validée ;
- un résident n'a aucun geste.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import RoleUtilisateur, StatutUtilisateur, Ticket, TicketEvolution
from app.models.synthese import ANNULEE, BROUILLON, VALIDEE, SyntheseAffaire, TentativeSynthese
from app.routers.tickets import evolutions
from app.routers.tickets import synthese as routes
from app.routers.tickets.commun import ticket_read
from app.routers.tickets.synthese_schemas import SyntheseModification
from app.utils import horloge, llm
from app.utils.carnet_entretien import construire_carnet
from app.utils.synthese_affaire.file import DELAI_DE_GRACE, inscrire_si_eligible, traiter_file
from app.utils.synthese_affaire.production import produire
from tests.aides_base import compte


@pytest.fixture()
def envois(monkeypatch):
    """Les courriels « Synthèse à valider » partis — comptés, jamais envoyés."""
    partis = []

    async def faux(code, to_recipients, context, session=None, **_):
        partis.append((code, [e for _, e in to_recipients], context))

    monkeypatch.setattr("app.utils.email.send_email_group", faux)
    return partis


@pytest.fixture()
def assistant(monkeypatch):
    """Un assistant prêt, qui rédige ; `assistant.consignes` garde ce qu'il a reçu."""
    consignes = []

    def config(session, usage=None):
        return SimpleNamespace(pret=True, prompt="PROMPT", verifier=lambda **_: None)

    async def demander(session, *, usage, message, consigne=None, **_):
        consignes.append(consigne)
        texte = json.dumps(
            {"synthese": "<p>Récit</p>", "difficultes": "<p>Attente</p>", "amelioration": ""}
        )
        return SimpleNamespace(texte=texte, jetons_entree=1000, jetons_sortie=200, jetons_cache=0)

    monkeypatch.setattr(llm, "config_llm", config)
    monkeypatch.setattr(llm, "demander", demander)
    return SimpleNamespace(consignes=consignes)


def _personnes(session):
    resident = compte(session, prefixe="res", statut=StatutUtilisateur.copropriétaire_résident)
    cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    return resident, cs


def _close(session, auteur, *, categorie="panne", equipement="ascenseur", n=1):
    maintenant = horloge.maintenant()
    ticket = Ticket(
        numero=f"TK-SYN{n:03d}",
        titre="Ascenseur en panne",
        description="<p>Bloqué au 3e.</p>",
        categorie=categorie,
        equipement=equipement,
        statut="résolu",
        auteur_id=auteur.id,
        cree_le=maintenant - timedelta(days=12),
        ferme_le=maintenant,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def _vieillir(session, demande):
    demande.cree_le = horloge.maintenant() - DELAI_DE_GRACE - timedelta(minutes=1)
    session.add(demande)
    session.commit()


def _produite(session, ticket):
    demande = inscrire_si_eligible(session, ticket, statut_avant="en_cours")
    session.commit()
    _vieillir(session, demande)
    traiter_file(session)
    session.refresh(demande)
    return demande


def test_une_cloture_du_carnet_inscrit_une_seule_demande(session):
    resident, _ = _personnes(session)
    ticket = _close(session, resident)
    assert inscrire_si_eligible(session, ticket, statut_avant="en_cours")
    session.commit()
    assert not inscrire_si_eligible(session, ticket, statut_avant="ouvert")
    #  Une simple correction d'une affaire déjà close n'inscrit rien.
    autre = _close(session, resident, n=2)
    assert not inscrire_si_eligible(session, autre, statut_avant="résolu")


def test_hors_carnet_une_demande_aussi_et_l_equipement_n_est_pas_exige(session):
    """Toute affaire close est éligible (21/10/2026 ; « du carnet » jusque-là),
    avec ou sans équipement (signalé à l'écran le 03/10/2026, v2.99.2)."""
    resident, _ = _personnes(session)
    question = _close(session, resident, categorie="question", equipement=None)
    assert inscrire_si_eligible(session, question, statut_avant="ouvert")
    sans = _close(session, resident, equipement=None, n=2)
    assert inscrire_si_eligible(session, sans, statut_avant="en_cours")


def test_la_file_attend_le_delai_de_grace(session, envois):
    resident, _ = _personnes(session)
    demande = inscrire_si_eligible(session, _close(session, resident), statut_avant="en_cours")
    session.commit()
    assert traiter_file(session)["produites"] == 0
    _vieillir(session, demande)
    assert traiter_file(session)["produites"] == 1


def test_sans_assistant_la_suite_nait_vide_et_l_avis_part_une_fois(session, envois):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    demande = _produite(session, ticket)
    assert demande.statut == BROUILLON
    assert not demande.synthese and demande.motif_vide
    evol = session.get(TicketEvolution, demande.evolution_id)
    assert evol.type == "synthese" and evol.contenu is None
    assert [code for code, _, _ in envois] == ["synthese_a_valider"]
    assert cs.email in envois[0][1]
    assert envois[0][2]["synthese"]["vide"] is True
    #  Une seconde passe de la file n'en renvoie pas.
    traiter_file(session)
    assert len(envois) == 1


def test_l_assistant_redige_et_la_relance_ne_renvoie_pas_de_courriel(session, envois, assistant):
    resident, cs = _personnes(session)
    demande = _produite(session, _close(session, resident))
    assert demande.synthese == "<p>Récit</p>" and demande.assiste_ia
    assert json.loads(demande.metriques_json)["issue"] == "résolu"
    resultat = asyncio.run(produire(session, demande, auteur_id=cs.id, complement="Plus court"))
    assert resultat.redigee and not resultat.a_aviser and resultat.tentative_id
    assert "Plus court" in assistant.consignes[-1]
    tentatives = session.exec(
        select(TentativeSynthese).where(TentativeSynthese.synthese_id == demande.id)
    ).all()
    assert len(tentatives) == 2  # l'historique garde chaque production
    assert len(envois) == 1


def test_une_relance_propose_et_rien_ne_change_sans_appliquer(session, envois, assistant):
    """03/10/2026, demandé à l'écran : « il manque une option Annuler si on veut
    sortir sans sauvegarder ». Relancer PROPOSE ; « Annuler » est de ne pas appliquer."""
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    demande = _produite(session, ticket)
    routes.modifier_synthese(
        ticket.id, SyntheseModification(synthese="<p>Relu</p>"), session=session, user=cs
    )
    resultat = asyncio.run(produire(session, demande, auteur_id=cs.id, complement="Plus court"))
    session.refresh(demande)
    assert demande.synthese == "<p>Relu</p>" and demande.prompt_complement is None
    lue = routes.appliquer_proposition(ticket.id, resultat.tentative_id, session=session, user=cs)
    assert lue.synthese == "<p>Récit</p>" and lue.prompt_complement == "Plus court"
    #  « Recommencer » propose sans complément ; l'appliquer l'efface.
    recommence = asyncio.run(produire(session, demande, auteur_id=cs.id, complement=None))
    lue = routes.appliquer_proposition(ticket.id, recommence.tentative_id, session=session, user=cs)
    assert lue.prompt_complement is None
    with pytest.raises(HTTPException) as refus:
        routes.appliquer_proposition(ticket.id, 999_999, session=session, user=cs)
    assert refus.value.status_code == 404


def test_une_correction_d_etat_est_une_etape_de_la_frise(session, envois):
    """L'état changé par la fiche n'écrit pas d'étape, mais sa correction le dit :
    la frise ne prête plus toute l'attente à l'état d'après (03/10/2026)."""
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    debut = ticket.cree_le
    for jours, evol in (
        (
            2,
            TicketEvolution(
                type="commentaire", contenu="Correction : État : Ouvert → Chez le syndic"
            ),
        ),
        (5, TicketEvolution(type="etat", ancien_statut="en_cours", nouveau_statut="résolu")),
    ):
        evol.ticket_id, evol.auteur_id, evol.cree_le = (
            ticket.id,
            cs.id,
            debut + timedelta(days=jours),
        )
        session.add(evol)
    session.commit()
    demande = _produite(session, ticket)
    met = json.loads(demande.metriques_json)
    assert [e["statut"] for e in met["etapes"]] == ["ouvert", "en_cours"]
    assert [j["statut"] for j in met["chronologie"][:2]] == ["ouvert", "en_cours"]


def test_un_brouillon_est_invisible_d_un_lecteur_ordinaire(session, envois, assistant):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    demande = _produite(session, ticket)

    def fil(user):
        return [e.type for e in evolutions.get_evolutions(ticket.id, session=session, user=user)]

    assert "synthese" not in fil(resident)
    assert routes.lire_synthese(ticket.id, session=session, user=resident).synthese is None
    assert "synthese" in fil(cs)
    assert routes.lire_synthese(ticket.id, session=session, user=cs).synthese.statut == BROUILLON
    #  L'aperçu de la carte du carnet : la demande, tant que rien n'est validé.
    assert not construire_carnet(session, lecteur=cs)[0]["synthese"]
    assert construire_carnet(session, lecteur=cs)[0]["extrait"] == "<p>Bloqué au 3e.</p>"

    routes.valider_synthese(ticket.id, session=session, user=cs)
    session.refresh(demande)
    assert demande.statut == VALIDEE and demande.validee_par_id == cs.id
    assert "synthese" in fil(resident)
    lue = routes.lire_synthese(ticket.id, session=session, user=resident).synthese
    assert lue.synthese == "<p>Récit</p>" and lue.metriques["duree_totale"] >= 0
    ligne = construire_carnet(session, lecteur=cs)[0]
    assert ligne["synthese"]["statut"] == VALIDEE
    #  …puis « Ce qui s'est passé », une fois la synthèse validée (24/10/2026).
    assert ligne["extrait"] == "<p>Récit</p>"


def test_la_carte_dit_la_synthese_validee_seulement(session, envois, assistant):
    """🧾 La pastille « Synthèse » de la carte repliée (maquette A, 15/10/2026).

    Validée seulement : un brouillon ne se lit que du conseil, et la pastille
    parle à tous ceux qui lisent l'affaire.
    """
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    _produite(session, ticket)

    def pastille():
        return ticket_read(ticket, session, resident).synthese_validee

    assert not pastille()
    routes.valider_synthese(ticket.id, session=session, user=cs)
    assert pastille()


def test_une_synthese_validee_se_corrige_et_se_supprime(session, envois, assistant):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    demande = _produite(session, ticket)
    routes.valider_synthese(ticket.id, session=session, user=cs)

    lue = routes.modifier_synthese(
        ticket.id, SyntheseModification(synthese="<p>Corrigé</p>"), session=session, user=cs
    )
    assert lue.statut == VALIDEE and lue.synthese == "<p>Corrigé</p>"
    with pytest.raises(HTTPException) as vide:
        routes.modifier_synthese(
            ticket.id, SyntheseModification(synthese=""), session=session, user=cs
        )
    assert vide.value.status_code == 422
    with pytest.raises(HTTPException) as refus:
        routes.supprimer_synthese(ticket.id, session=session, user=resident)
    assert refus.value.status_code == 403

    evol_id = demande.evolution_id
    routes.supprimer_synthese(ticket.id, session=session, user=cs)
    session.refresh(demande)
    assert demande.statut == ANNULEE and demande.evolution_id is None
    assert session.get(TicketEvolution, evol_id) is None
    etat = routes.lire_synthese(ticket.id, session=session, user=cs)
    assert etat.synthese is None and etat.produisible
    assert not construire_carnet(session, lecteur=cs)[0]["synthese"]


def test_une_nouvelle_cloture_remplace_la_synthese_validee(session, envois, assistant):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    premiere = _produite(session, ticket)
    routes.valider_synthese(ticket.id, session=session, user=cs)
    ticket.ferme_le = horloge.maintenant() + timedelta(minutes=5)  # rouverte puis close
    session.add(ticket)
    session.commit()
    seconde = _produite(session, ticket)
    session.refresh(premiere)
    assert premiere.statut == ANNULEE and seconde.statut == BROUILLON
    assert routes.lire_synthese(ticket.id, session=session, user=cs).synthese.id == seconde.id


def test_une_demande_perimee_est_annulee(session, envois):
    resident, _ = _personnes(session)
    ticket = _close(session, resident)
    demande = inscrire_si_eligible(session, ticket, statut_avant="en_cours")
    ticket.statut = "en_cours"  # rouverte pendant le délai de grâce
    session.add(ticket)
    session.commit()
    _vieillir(session, demande)
    assert traiter_file(session)["perimees"] == 1
    session.refresh(demande)
    assert demande.statut == ANNULEE and not envois


def test_un_resident_n_a_aucun_geste(session, envois):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    _produite(session, ticket)
    with pytest.raises(HTTPException) as refus:
        routes.modifier_synthese(
            ticket.id, SyntheseModification(synthese="x"), session=session, user=resident
        )
    assert refus.value.status_code == 403
    with pytest.raises(HTTPException) as vide:
        routes.valider_synthese(ticket.id, session=session, user=cs)
    assert vide.value.status_code == 422  # une synthèse vide ne se valide pas
    routes.modifier_synthese(
        ticket.id, SyntheseModification(synthese="<p>Rédigée</p>"), session=session, user=cs
    )
    assert routes.valider_synthese(ticket.id, session=session, user=cs).statut == VALIDEE


def test_produire_une_affaire_d_avant_la_mise_en_service(session, envois):
    resident, cs = _personnes(session)
    ticket = _close(session, resident)
    etat = routes.lire_synthese(ticket.id, session=session, user=cs)
    assert etat.produisible and etat.synthese is None
    assert not routes.lire_synthese(ticket.id, session=session, user=resident).produisible
    session.add(SyntheseAffaire(ticket_id=ticket.id, statut=BROUILLON, synthese="<p>x</p>"))
    session.commit()
    assert not routes.lire_synthese(ticket.id, session=session, user=cs).produisible


# ── Les rendus du fil ──────────────────────────────────────────────────────

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"
#: Les fils d'affaire qui n'ont pas à porter la synthèse — avec leur raison.
#: Une exception qui ne sert plus fait échouer.
_FILS_SANS_SYNTHESE = {
    #  Le fil d'une actualité de la liste vit dans `FilActualiteEnListe`, chargé
    #  au dépliage depuis le 13/10/2026 (#1861) — c'était `ActualiteEnListe`.
    "FilActualiteEnListe.svelte": "une actualité n'a pas de cycle de vie : jamais close, "
    "jamais de synthèse (`StatutTicket.publie`)",
}


def test_chaque_fil_d_affaire_monte_la_synthese():
    """🔴 v2.99.0 : la synthèse et « Produire » n'étaient câblés que dans la fiche.

    La carte dépliée de la liste monte son propre fil (`RubriqueHistorique` +
    `SuiteAffaire`) : le bouton y manquait, et la Suite y paraissait VIDE —
    trouvé à l'écran par l'utilisateur. Tout fil d'affaire monte `SyntheseFil`.
    """
    fils = {
        p.name: p.read_text(encoding="utf-8")
        for p in _FRONT.rglob("*.svelte")
        if "<RubriqueHistorique" in p.read_text(encoding="utf-8")
        and "<SuiteAffaire" in p.read_text(encoding="utf-8")
    }
    assert len(fils) >= 2, f"cas zéro : {sorted(fils)} — la lecture ne voit plus les fils"
    oublis = [n for n, src in fils.items() if "<SyntheseFil" not in src]
    assert sorted(oublis) == sorted(_FILS_SANS_SYNTHESE), (
        f"fils d'affaire sans `SyntheseFil` : {sorted(set(oublis) - set(_FILS_SANS_SYNTHESE))} ; "
        f"exceptions qui ne servent plus : {sorted(set(_FILS_SANS_SYNTHESE) - set(oublis))}"
    )
