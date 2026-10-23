"""Une pièce jointe ne désigne que les dossiers des pièces jointes (#2157).

## 🔴 Pourquoi

`photos_internes()` gardait toute adresse « des nôtres » — `prive/` compris. Une
clé glissée dans `fichiers_urls` à la création d'une affaire partait en copie par
courriel (Caddy et `document_visible` contournés), et la conservation retirait du
disque, à l'échéance de l'affaire, un fichier qui appartenait à un autre objet.

## Ce que ces tests tiennent

1. La règle : `prive/`, `annonces-hall/`, `logo/`, `avatars/` et la racine sont
   écartés ; les dossiers des pièces jointes, anciens compris, sont gardés.
2. Le contrat : chaque dossier où l'application ÉCRIT une pièce jointe est dans
   la liste — sinon une photo neuve serait écartée sans un mot.
3. La conservation : un fichier qu'un autre objet cite encore part dans l'archive
   et reste sur le disque.
"""

from __future__ import annotations

import ast
from datetime import date, datetime

import pytest
from sqlmodel import Session

from app.models.core import ConfigSite, Ticket
from app.utils.conservation_application import appliquer_conservation
from app.utils.photos import DOSSIERS_DES_PIECES_JOINTES, cles_citees, photos_internes
from app.utils.services import SERVICE_CONSERVATION, cle_actif
from tests.aides_sources import modules_app

ECHUE = date(2036, 1, 2)
MAINTENANT = datetime(2036, 1, 2, 4, 45)


@pytest.mark.parametrize(
    "url",
    [
        "/uploads/prive/pv.pdf",
        "/uploads/annonces-hall/a.pdf",
        "/uploads/logo/logo.png",
        "/uploads/avatars/x.jpg",
        "/uploads/racine.pdf",
        "https://tiers.example/x.jpg",
    ],
)
def test_une_adresse_hors_des_pieces_jointes_est_ecartee(url):
    assert photos_internes([url]) == []


@pytest.mark.parametrize("dossier", sorted(DOSSIERS_DES_PIECES_JOINTES))
def test_les_dossiers_des_pieces_jointes_sont_gardes(dossier):
    url = f"/uploads/{dossier}/abc_devis.pdf"
    assert photos_internes([url]) == [url]


#: Les dossiers ÉCRITS par l'application qui ne sont PAS des pièces jointes.
ECRITS_HORS_PIECES_JOINTES = {"avatars": "la photo de profil, jamais jointe à un objet"}


def test_chaque_dossier_ecrit_pour_une_piece_jointe_est_dans_la_liste():
    ecrits = set()
    for m in modules_app("routers"):
        for n in ast.walk(m.arbre):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_save_image":
                if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    ecrits.add(n.args[1].value)
    assert {"fichiers", "annonces"} <= ecrits, f"relevé trop pauvre : {ecrits}"
    oublies = ecrits - DOSSIERS_DES_PIECES_JOINTES - set(ECRITS_HORS_PIECES_JOINTES)
    assert not oublies, f"dossier(s) de pièces jointes hors de la liste : {oublies}"


def _affaire(session: Session, numero: str, ferme_le: datetime, photo: str) -> Ticket:
    t = Ticket(
        numero=numero,
        titre=f"Affaire {numero}",
        description="d",
        categorie="etude_travaux",
        statut="résolu",
        ferme_le=ferme_le,
        photos_urls=f'["{photo}"]',
        perimetre_cible='["résidence"]',
    )
    session.add(t)
    session.commit()
    return t


def test_la_conservation_garde_un_fichier_qu_un_autre_objet_cite(session, disque_jetable):
    (disque_jetable / "fichiers").mkdir(exist_ok=True)
    (disque_jetable / "fichiers" / "commune.jpg").write_bytes(b"commune")
    (disque_jetable / "fichiers" / "seule.jpg").write_bytes(b"seule")
    #  L'échue cite deux fichiers ; une affaire récente reprend l'un des deux.
    echue = _affaire(session, "TK-1", datetime(2025, 5, 2, 9), "/uploads/fichiers/commune.jpg")
    echue.fichiers_urls = '["/uploads/fichiers/seule.jpg"]'
    session.add(echue)
    _affaire(session, "TK-2", datetime(2035, 12, 1, 9), "/uploads/fichiers/commune.jpg")
    session.merge(ConfigSite(cle=cle_actif(SERVICE_CONSERVATION), valeur="1"))
    session.commit()

    rendu = appliquer_conservation(session, aujourd_hui=ECHUE, maintenant=MAINTENANT)

    assert rendu["echecs"] == 0 and rendu["groupes"], rendu
    assert not (disque_jetable / "fichiers" / "seule.jpg").exists(), "témoin : rien n'a été retiré"
    assert (disque_jetable / "fichiers" / "commune.jpg").is_file(), (
        "un fichier cité par une autre affaire a été retiré du disque"
    )
    assert "fichiers/commune.jpg" in cles_citees(session)
