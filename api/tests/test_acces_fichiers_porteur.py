"""Un fichier servi en direct se lit si son objet PORTEUR se lit (#2154).

La règle vit dans `utils/visibility/fichiers` ; ce fichier l'éprouve par cas, sur
les deux portes qui l'appellent (Caddy par `/auth/verifier-acces`, l'installation
commune par sa route), et vérifie que toute colonne qui cite un fichier a son
porteur déclaré — une table neuve qui joint des pièces n'y échappe pas.

Avant #2154, `/auth/verifier-acces` ne jugeait que la session : la pièce jointe
d'une affaire confidentielle se lisait par tout compte qui en avait l'adresse.
`test_une_session_valide_ne_suffit_plus` est le cas fautif, vu en échec avant le
correctif (la route rendait 204).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, select

from app.models.core import RoleUtilisateur, Utilisateur
from app.models.fichiers_recus import FichierRecu
from app.models.tickets import MessageTicket, Ticket
from app.utils import photos
from app.utils.visibility import fichiers as regle
from tests.aides_base import compte
from tests.aides_http import base_http, client_http


def _cle(dossier: str = "fichiers") -> str:
    return f"{dossier}/{uuid.uuid4().hex}_photo.jpg"


def _affaire(session: Session, auteur, *cles: str, **champs) -> Ticket:
    t = Ticket(
        numero=f"T-{uuid.uuid4().hex[:8]}",
        titre="Fuite au sous-sol",
        description="<p>Constat</p>",
        auteur_id=auteur.id,
        photos_urls=json.dumps([f"/uploads/{c}" for c in cles]),
        **champs,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture()
def monde(session):
    """Un auteur, un voisin, un membre du conseil — et une affaire confidentielle."""
    auteur = compte(session, prefixe="auteur")
    voisin = compte(session, prefixe="voisin")
    conseil = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    cle = _cle()
    affaire = _affaire(session, auteur, cle, confidentiel=True)
    return session, auteur, voisin, conseil, cle, affaire


def test_le_porteur_decide(monde):
    session, auteur, voisin, conseil, cle, _ = monde
    assert regle.fichier_lisible(session, auteur, cle)
    assert regle.fichier_lisible(session, conseil, cle)
    assert not regle.fichier_lisible(session, voisin, cle), (
        "le voisin lit une affaire confidentielle"
    )


def test_un_porteur_lisible_suffit(monde):
    """Le même fichier cité par deux objets : il se lit si l'UN d'eux se lit."""
    session, _, voisin, _, cle, _ = monde
    _affaire(session, voisin, cle)
    assert regle.fichier_lisible(session, voisin, cle)


def test_une_adresse_PROCHE_n_est_pas_une_citation(monde):
    """Le porteur cite l'adresse exacte : un préfixe commun ne suffit pas."""
    session, _, voisin, _, cle, _ = monde
    _affaire(session, voisin, cle + "x")
    assert not regle.fichier_lisible(session, voisin, cle)


def test_le_message_interne_garde_ses_pieces_au_conseil(session):
    resident = compte(session, prefixe="resident")
    conseil = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    affaire = _affaire(session, resident)
    cle = _cle()
    session.add(
        MessageTicket(
            ticket_id=affaire.id,
            auteur_id=conseil.id,
            contenu="Note",
            interne=True,
            fichiers_urls=json.dumps([f"/uploads/{cle}"]),
        )
    )
    session.commit()
    assert not regle.fichier_lisible(session, resident, cle), "la pièce d'une note interne fuit"
    assert regle.fichier_lisible(session, conseil, cle)


def test_sans_porteur_l_auteur_seul(session):
    """La photo d'un formulaire pas encore enregistré (arbitrage du 23/10/2026)."""
    auteur = compte(session, prefixe="auteur")
    autre = compte(session, prefixe="autre")
    conseil = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    cle = _cle()
    session.add(FichierRecu(cle=cle, auteur_id=auteur.id))
    session.commit()
    assert regle.fichier_lisible(session, auteur, cle)
    assert not regle.fichier_lisible(session, autre, cle)
    assert not regle.fichier_lisible(session, conseil, cle), "l'auteur connu est le SEUL lecteur"


def test_sans_porteur_ni_auteur_le_conseil(session):
    """Un fichier reçu avant #2154, ou d'un compte supprimé."""
    resident = compte(session, prefixe="resident")
    conseil = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    cle = _cle()
    assert not regle.fichier_lisible(session, resident, cle)
    assert regle.fichier_lisible(session, conseil, cle)


@pytest.mark.parametrize("dossier", sorted(regle.TOUTE_SESSION))
def test_les_dossiers_de_toute_session(session, dossier):
    assert regle.fichier_lisible(session, compte(session), _cle(dossier))


@pytest.mark.parametrize("dossier", ["prive", "annonces-hall"])
def test_les_dossiers_jamais_servis(session, dossier):
    conseil = compte(session, prefixe="cs", roles_json=RoleUtilisateur.admin.value)
    assert not regle.fichier_lisible(session, conseil, _cle(dossier))


def test_toute_colonne_qui_cite_un_fichier_a_son_porteur():
    """Une colonne de `photos.COLONNES_DE_FICHIERS` sans porteur serait lue « orpheline »."""
    citees = {
        (table.name, nom)
        for table in SQLModel.metadata.tables.values()
        for nom in photos.COLONNES_DE_FICHIERS
        if nom in table.c
    }
    declarees = {(p.modele.__tablename__, p.colonne) for p in regle.PORTEURS}
    assert len(citees) >= 9, f"le relevé ne voit que {len(citees)} colonne(s)"
    assert citees == declarees, (
        f"sans porteur : {sorted(citees - declarees)} ; "
        f"porteur sans colonne : {sorted(declarees - citees)}"
    )


# ── La porte de Caddy ───────────────────────────────────────────────────────


def _cle_confidentielle(moteur, auteur_id: int) -> str:
    cle = _cle()
    with Session(moteur) as s:
        _affaire(s, s.get(Utilisateur, auteur_id), cle, confidentiel=True)
    return cle


def test_une_session_valide_ne_suffit_plus():
    with base_http() as moteur:
        auteur, auteur_id = client_http(moteur, RoleUtilisateur.résident)
        voisin, _ = client_http(moteur, RoleUtilisateur.résident)
        conseil, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        anonyme, _ = client_http(moteur, None)
        cle = _cle_confidentielle(moteur, auteur_id)

        def code(http, uri=f"/uploads/{cle}"):
            return http.get("/auth/verifier-acces", headers={"X-Forwarded-Uri": uri}).status_code

        assert code(voisin) == 404, "une session valide lit le fichier d'une affaire confidentielle"
        assert code(auteur) == 204
        assert code(conseil) == 204
        assert code(conseil, f"/uploads/{cle}?v=2") == 204, "la chaîne de requête compte"
        assert code(anonyme) == 401
        assert conseil.get("/auth/verifier-acces").status_code == 404, "sans adresse, rien à ouvrir"


def test_la_porte_des_televersements_note_l_auteur(session, monkeypatch):
    """Un fichier écrit dans un dossier servi note son auteur — et l'exige."""
    from app.utils import fichiers

    monkeypatch.setattr(fichiers, "stockage", lambda: type("S", (), {"ecrire": lambda *_: None})())
    pdf = b"%PDF-1.4\n%%EOF\n"
    with pytest.raises(ValueError, match="note son auteur"):
        fichiers.enregistrer_fichier_recu(pdf, "a.pdf", "application/pdf", "document", "fichiers")
    auteur = compte(session)
    nom = fichiers.enregistrer_fichier_recu(
        pdf, "a.pdf", "application/pdf", "document", "fichiers", user=auteur, session=session
    )
    (recu,) = session.exec(select(FichierRecu)).all()
    assert recu.cle == f"fichiers/{nom}" and recu.auteur_id == auteur.id


def test_les_deux_portes_appellent_la_regle():
    """Caddy (`verifier-acces`) et l'installation commune : la même règle, jamais une copie."""
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "app"
    for porte in ("routers/auth.py", "installation_commune/fichiers.py"):
        source = (app / porte).read_text(encoding="utf-8")
        assert "exiger_fichier_lisible(session, user," in source, f"{porte} ne juge pas le fichier"
