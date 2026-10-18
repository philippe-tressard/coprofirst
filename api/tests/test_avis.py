"""Les avis sur l'application (#2075) — les règles, les droits, l'export.

Ce que ce fichier tient :

- les SEUILS : une remarque sous 3 étoiles, l'accord de l'auteur à partir de
  4, et jamais un accord présumé (`None` refusé, pas lu comme un oui) ;
- ce qui ne sort qu'à l'auteur et au gestionnaire du site (remarque, accord,
  validation), et ce qu'un avis retiré cesse de montrer aux autres ;
- l'EXPORT vers coprofirst.fr : les seuls avis retenus et consentis, « Prénom
  N. » et le rôle, rien qui identifie (ni adresse, ni identifiant) ;
- l'avis part avec le compte (`suppression_compte.CONTENUS_PERSONNELS`).
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.avis import Avis
from app.models.core import ConfigSite, Notification, RoleUtilisateur, StatutUtilisateur
from app.routers.avis import (
    archiver,
    corriger,
    deposer,
    exporter_avis,
    lister,
    repondre,
    retenir,
    supprimer,
)
from app.routers.avis_schemas import AvisCreate, AvisUpdate, PublicationAvis, ReponseAvis
from app.routers.prestataires_archivage import Archivage
from app.utils.avis import exiger_saisie_valide
from app.utils.destinataires import est_gestionnaire_du_site
from app.utils.noms import nom_abrege
from app.utils.roles_libelles import role_signature
from app.utils.suppression_compte import supprimer_compte
from tests.aides_base import compte

DESCRIPTION = "<p>Tout est clair, et le fil d'actualité se lit d'un coup d'œil.</p>"


def _resident(session, prenom="Claire", nom="Durand", **champs):
    champs.setdefault("statut", StatutUtilisateur.copropriétaire_résident)
    return compte(session, prefixe="avis", prenom=prenom, nom=nom, **champs)


def _admin(session):
    return compte(
        session, prefixe="gestion", prenom="Sophie", nom="Martin", role=RoleUtilisateur.admin
    )


def _avis(session, auteur, note=5, consentement=True, remarque=None):
    corps = AvisCreate(
        note=note,
        titre="Enfin un site clair",
        description=DESCRIPTION,
        remarque=remarque,
        consentement_publication=consentement,
    )
    return deposer(corps, session, auteur)


# ── Les règles ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("note", [0, 6, -1])
def test_la_note_va_de_1_a_5(note):
    with pytest.raises(HTTPException) as e:
        exiger_saisie_valide(note, "x", True)
    assert e.value.status_code == 422


@pytest.mark.parametrize("note", [1, 2])
def test_sous_3_etoiles_la_remarque_est_obligatoire(note):
    for vide in (None, "", "   "):
        with pytest.raises(HTTPException):
            exiger_saisie_valide(note, vide, None)
    assert exiger_saisie_valide(note, " lent ", None) == ("lent", None)


def test_a_3_etoiles_ni_remarque_ni_accord_ne_s_enregistrent():
    """Ce que la note n'appelle pas ne s'enregistre pas — sans quoi l'avis dirait ce qu'il ne dit plus."""
    assert exiger_saisie_valide(3, "reste d'une note basse", True) == (None, None)


@pytest.mark.parametrize("note", [4, 5])
def test_a_partir_de_4_l_accord_est_une_reponse_exigee_jamais_presumee(note):
    with pytest.raises(HTTPException) as e:
        exiger_saisie_valide(note, None, None)
    assert e.value.status_code == 422
    assert exiger_saisie_valide(note, None, True) == (None, True)
    assert exiger_saisie_valide(note, None, False) == (None, False)


@pytest.mark.parametrize(
    ("prenom", "nom", "attendu"),
    [
        ("Jean-Baptiste", "fort", "Jean-Baptiste F."),
        ("  Claire ", " durand", "Claire D."),
        ("Claire", "", "Claire"),
        ("", "Durand", "D."),
        (None, None, ""),
    ],
)
def test_le_nom_public_est_le_prenom_et_l_initiale(prenom, nom, attendu):
    assert nom_abrege(prenom, nom) == attendu


def test_le_role_affiche_est_la_signature_courte(session):
    assert role_signature(_resident(session)) == "Copropriétaire"
    loc = _resident(session, prenom="Paul", statut=StatutUtilisateur.locataire)
    assert role_signature(loc) == "Locataire"
    cs = _resident(session, prenom="Luc", roles_json="propriétaire,conseil_syndical")
    assert role_signature(cs) == "Conseil syndical"


# ── Qui gère le site ─────────────────────────────────────────────────────────


def test_le_gestionnaire_designe_seul_sinon_tout_administrateur(session):
    a, b = _admin(session), _admin(session)
    assert est_gestionnaire_du_site(session, a) and est_gestionnaire_du_site(session, b)
    session.add(ConfigSite(cle="site_manager_user_id", valeur=str(a.id)))
    session.commit()
    assert est_gestionnaire_du_site(session, a)
    assert not est_gestionnaire_du_site(session, b)
    assert not est_gestionnaire_du_site(session, _resident(session))


# ── Déposer, lire, corriger ──────────────────────────────────────────────────


def test_un_avis_par_compte(session):
    auteur = _resident(session)
    _avis(session, auteur)
    with pytest.raises(HTTPException) as e:
        _avis(session, auteur)
    assert e.value.status_code == 409


def test_le_syndic_donne_son_avis_mais_pas_un_banni(session):
    """La seule rubrique de la Communauté ouverte au syndic (arbitrage du 18/10/2026)."""
    syndic = _resident(session, prenom="Marc", nom="Roy", statut=StatutUtilisateur.syndic)
    assert _avis(session, syndic).auteur_role == "Syndic"
    banni = _resident(session, prenom="Luc", communaute_interdit=True)
    with pytest.raises(HTTPException) as e:
        _avis(session, banni)
    assert e.value.status_code == 403


def test_un_compte_externe_ne_donne_pas_d_avis(session):
    externe = _resident(session, role=RoleUtilisateur.externe)
    with pytest.raises(HTTPException) as e:
        _avis(session, externe)
    assert e.value.status_code == 403


def test_la_remarque_et_l_accord_ne_sortent_qu_a_l_auteur_et_au_gestionnaire(session):
    auteur, voisin, gestion = _resident(session), _resident(session, prenom="Paul"), _admin(session)
    _avis(
        session, auteur, note=2, consentement=None, remarque="Les notifications arrivent en retard"
    )
    vu_du_voisin = lister(session, voisin).avis[0]
    assert vu_du_voisin.remarque is None and vu_du_voisin.consentement_publication is None
    assert vu_du_voisin.auteur_nom == "Claire D." and vu_du_voisin.auteur_role == "Copropriétaire"
    for proche in (auteur, gestion):
        assert lister(session, proche).avis[0].remarque == "Les notifications arrivent en retard"
    assert lister(session, gestion).gestionnaire and not lister(session, voisin).gestionnaire


def test_seul_l_auteur_corrige_et_la_correction_retire_la_validation(session):
    auteur, gestion = _resident(session), _admin(session)
    avis = _avis(session, auteur)
    retenir(avis.id, PublicationAvis(validee=True), session, gestion)
    with pytest.raises(HTTPException) as e:
        corriger(avis.id, AvisUpdate(titre="Réécrit"), session, gestion)
    assert e.value.status_code == 403
    lu = corriger(avis.id, AvisUpdate(titre="Encore plus clair"), session, auteur)
    assert lu.titre == "Encore plus clair" and not lu.publication_validee


def test_baisser_la_note_sous_4_efface_l_accord(session):
    auteur = _resident(session)
    avis = _avis(session, auteur)
    lu = corriger(avis.id, AvisUpdate(note=3), session, auteur)
    assert lu.consentement_publication is None and not lu.publiable


# ── Retirer, ressortir ───────────────────────────────────────────────────────


def test_un_avis_retire_disparait_pour_les_autres_et_reste_a_son_auteur(session):
    auteur, voisin = _resident(session), _resident(session, prenom="Paul")
    avis = _avis(session, auteur)
    archiver(avis.id, Archivage(archivee=True), session, auteur)
    assert lister(session, voisin).avis == []
    mien = lister(session, auteur)
    assert mien.avis[0].archivee and mien.avis[0].restaurable and mien.mon_avis_id == avis.id
    archiver(avis.id, Archivage(archivee=False), session, auteur)
    assert len(lister(session, voisin).avis) == 1


def test_ce_que_le_gestionnaire_a_retire_l_auteur_ne_le_ressort_pas(session):
    auteur, gestion = _resident(session), _admin(session)
    avis = _avis(session, auteur)
    archiver(avis.id, Archivage(archivee=True), session, gestion)
    assert not lister(session, auteur).avis[0].restaurable
    with pytest.raises(HTTPException) as e:
        archiver(avis.id, Archivage(archivee=False), session, auteur)
    assert e.value.status_code == 403


def test_seuls_l_auteur_et_l_admin_suppriment_et_aux_archives(session):
    auteur, voisin = _resident(session), _resident(session, prenom="Paul")
    avis = _avis(session, auteur)
    with pytest.raises(HTTPException) as e:
        supprimer(avis.id, session, auteur)
    assert e.value.status_code == 400
    archiver(avis.id, Archivage(archivee=True), session, auteur)
    with pytest.raises(HTTPException) as e:
        supprimer(avis.id, session, voisin)
    assert e.value.status_code == 403
    supprimer(avis.id, session, auteur)
    assert session.get(Avis, avis.id) is None


# ── Réponse et publication ───────────────────────────────────────────────────


def test_seul_le_gestionnaire_repond_et_l_auteur_est_prevenu(session):
    auteur, voisin, gestion = _resident(session), _resident(session, prenom="Paul"), _admin(session)
    avis = _avis(session, auteur)
    with pytest.raises(HTTPException) as e:
        repondre(avis.id, ReponseAvis(reponse="Merci"), session, voisin)
    assert e.value.status_code == 403
    lu = repondre(avis.id, ReponseAvis(reponse="Merci pour ce retour !"), session, gestion)
    assert lu.reponse == "Merci pour ce retour !"
    cloche = session.exec(
        select(Notification).where(Notification.destinataire_id == auteur.id)
    ).all()
    assert [n.lien for n in cloche] == [f"/avis#avis-{avis.id}"]
    assert repondre(avis.id, ReponseAvis(reponse="  "), session, gestion).reponse is None


@pytest.mark.parametrize(("note", "accord"), [(5, False), (3, None)])
def test_on_ne_retient_que_ce_que_l_auteur_a_accepte(session, note, accord):
    auteur, gestion = _resident(session), _admin(session)
    avis = _avis(session, auteur, note=note, consentement=accord)
    with pytest.raises(HTTPException) as e:
        retenir(avis.id, PublicationAvis(validee=True), session, gestion)
    assert e.value.status_code == 400


def test_l_export_ne_porte_que_les_avis_retenus_et_rien_qui_identifie(session):
    gestion = _admin(session)
    retenu = _avis(session, _resident(session, prenom="Jean-Baptiste", nom="fort"))
    _avis(session, _resident(session, prenom="Paul"))  # consenti, non retenu
    refuse = _avis(session, _resident(session, prenom="Luc"), consentement=False)
    retenir(retenu.id, PublicationAvis(validee=True), session, gestion)
    with pytest.raises(HTTPException):
        retenir(refuse.id, PublicationAvis(validee=True), session, gestion)

    reponse = exporter_avis(session, gestion)
    assert "attachment" in reponse.headers["content-disposition"]
    contenu = json.loads(reponse.body)
    assert len(contenu["avis"]) == 1
    exporte = contenu["avis"][0]
    assert set(exporte) == {"titre", "texte", "note", "auteur", "role", "date"}
    assert exporte["auteur"] == "Jean-Baptiste F." and exporte["role"] == "Copropriétaire"
    assert "<p>" not in exporte["texte"] and "@" not in json.dumps(contenu)


def test_l_export_est_reserve_au_gestionnaire(session):
    with pytest.raises(HTTPException) as e:
        exporter_avis(session, _resident(session))
    assert e.value.status_code == 403


def test_un_avis_retire_quitte_l_export(session):
    auteur, gestion = _resident(session), _admin(session)
    avis = _avis(session, auteur)
    retenir(avis.id, PublicationAvis(validee=True), session, gestion)
    archiver(avis.id, Archivage(archivee=True), session, auteur)
    archiver(avis.id, Archivage(archivee=False), session, auteur)
    assert json.loads(exporter_avis(session, gestion).body)["avis"] == []


# ── L'avis part avec le compte ───────────────────────────────────────────────


def test_l_avis_part_avec_le_compte(session):
    auteur = _resident(session)
    avis = _avis(session, auteur)
    supprimer_compte(session, auteur.id)
    session.commit()
    assert session.get(Avis, avis.id) is None
