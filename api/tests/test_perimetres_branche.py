"""Une branche de l'arborescence — dupliquée ou supprimée d'un bloc (13/10/2026).

Les gestes passent par les fonctions de route elles-mêmes (`patrimoine_branche`,
`patrimoine`) sur l'arbre semé de la fixture `batiments` : quatre bâtiments
`bat:N`, chacun avec le gabarit d'espaces du seed sous lui.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.models.core import Batiment, Copropriete
from app.models.perimetre import Perimetre
from app.routers.patrimoine import lister_perimetres, supprimer_perimetre
from app.routers.patrimoine_branche import PerimetreDuplication, dupliquer_perimetre
from app.utils.perimetres.branche import code_copie
from tests.aides_base import compte


def _noeud(session: Session, code: str) -> Perimetre:
    return session.exec(select(Perimetre).where(Perimetre.code == code)).one()


def _enfants(session: Session, noeud: Perimetre) -> list[Perimetre]:
    return list(
        session.exec(
            select(Perimetre).where(Perimetre.parent_id == noeud.id).order_by(Perimetre.ordre)
        ).all()
    )


def _nouveau_batiment(session: Session) -> int:
    copro = session.exec(select(Copropriete)).first()
    batiment = Batiment(copropriete_id=copro.id, numero="5")
    session.add(batiment)
    session.commit()
    return batiment.id


def test_dupliquer_un_batiment_recopie_ses_espaces_sous_le_nom_donne(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[0]}")
        espaces = _enfants(session, source)
        assert espaces, "le gabarit du seed doit poser des espaces sous le bâtiment"
        nouveau = _nouveau_batiment(session)

        lu = dupliquer_perimetre(
            source.id,
            PerimetreDuplication(
                code="bat:nouveau", libelle="Bâtiment 5", description="Le 5", batiment_id=nouveau
            ),
            session,
            admin,
        )

        copie = _noeud(session, "bat:nouveau")
        assert (lu.libelle, copie.description, copie.batiment_id) == ("Bâtiment 5", "Le 5", nouveau)
        assert copie.parent_id == source.parent_id
        assert copie.libelle_court is None, "« Bât. 1 » ne nomme pas le nouveau bâtiment"
        copies = _enfants(session, copie)
        assert [(c.libelle, c.icone, c.ordre) for c in copies] == [
            (e.libelle, e.icone, e.ordre) for e in espaces
        ]
        assert all(c.batiment_id is None for c in copies)
        assert {c.code for c in copies} == {
            e.code.replace(source.code, "bat:nouveau", 1) for e in espaces
        }
        #  La source n'a pas bougé.
        assert len(_enfants(session, source)) == len(espaces)


def test_la_copie_d_un_batiment_ne_garde_jamais_son_batiment(batiments):
    """🔴 Le lien au bâtiment décide QUI LIT : recopié, il ouvrirait la copie aux
    résidents du bâtiment source."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[0]}")
        corps = {"code": "bat:x", "libelle": "X"}
        for batiment_id, motif in (
            (None, "Choisissez le bâtiment"),
            (batiments[0], "déjà son périmètre"),
            (batiments[1], "déjà son périmètre"),
        ):
            with pytest.raises(HTTPException) as refus:
                dupliquer_perimetre(
                    source.id,
                    PerimetreDuplication(**corps, batiment_id=batiment_id),
                    session,
                    admin,
                )
            assert refus.value.status_code == 422 and motif in refus.value.detail


def test_une_branche_qui_contient_des_batiments_ne_se_duplique_pas(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        regroupement = _noeud(session, "batiments")
        lus = {n.code: n for n in lister_perimetres(session, admin)}
        assert lus["batiments"].dupliquable is False
        assert lus[f"bat:{batiments[0]}"].dupliquable is True
        with pytest.raises(HTTPException) as refus:
            dupliquer_perimetre(
                regroupement.id,
                PerimetreDuplication(code="bis", libelle="Bis"),
                session,
                admin,
            )
        assert "un par un" in refus.value.detail


def test_un_code_deja_pris_refuse_toute_la_copie(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[0]}")
        avant = len(session.exec(select(Perimetre)).all())
        with pytest.raises(HTTPException) as refus:
            dupliquer_perimetre(
                source.id,
                PerimetreDuplication(
                    code=f"bat:{batiments[1]}",
                    libelle="Doublon",
                    batiment_id=_nouveau_batiment(session),
                ),
                session,
                admin,
            )
        assert "déjà utilisé" in refus.value.detail
        assert len(session.exec(select(Perimetre)).all()) == avant


def test_code_copie_prolonge_le_parent_ou_garde_le_dernier_segment():
    assert code_copie("bat:1", "bat:5", "bat:1/hall") == "bat:5/hall"
    assert code_copie("bat:1", "bat:5", "bat:1/hall/porte") == "bat:5/hall/porte"
    assert code_copie("bat:1", "bat:5", "cave-du-1") == "bat:5/cave-du-1"


def test_supprimer_une_branche_exige_le_consentement_puis_emporte_les_descendants(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[2]}")
        lu = next(n for n in lister_perimetres(session, admin) if n.id == source.id)
        assert lu.nb_descendants == len(_enfants(session, source)) > 0

        with pytest.raises(HTTPException) as refus:
            supprimer_perimetre(source.id, False, session, admin)
        assert refus.value.status_code == 409 and "sous-périmètre" in refus.value.detail

        supprimer_perimetre(source.id, True, session, admin)
        restants = {n.code for n in session.exec(select(Perimetre)).all()}
        assert not any(c == source.code or c.startswith(f"{source.code}/") for c in restants)
        assert "batiments" in restants


def test_une_branche_dont_un_descendant_est_cite_ne_se_supprime_pas(batiments):
    """Le contenu publié garde son libellé : on désactive, on ne supprime pas."""
    from app.models.core import Ticket
    from tests.conftest import vider_patrimoine

    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[3]}")
        espace = _enfants(session, source)[0]
        session.add(
            Ticket(
                numero="TK-BRANCHE",
                titre="T",
                description="C",
                categorie="actualite",
                statut="publie",
                auteur_id=admin.id,
                perimetre_cible=f'["{espace.code}"]',
            )
        )
        session.commit()
        try:
            with pytest.raises(HTTPException) as refus:
                supprimer_perimetre(source.id, True, session, admin)
            assert refus.value.status_code == 409 and espace.libelle in refus.value.detail
            assert session.get(Perimetre, source.id) is not None
        finally:
            vider_patrimoine(session, (Ticket,))
