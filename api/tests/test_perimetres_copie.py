"""Copier un périmètre sous d'autres parents, mêmes paramètres (01/11/2026).

Demandé à l'écran : *« dupliquer un périmètre sur plusieurs autres catégories,
avec les mêmes paramètres »*. Les gestes passent par la route elle-même, sur
l'arbre semé de la fixture `batiments`.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.routers.patrimoine import lister_perimetres
from app.routers.patrimoine_branche import PerimetreCopie, copier_perimetre
from app.utils.acces_choix import fixer_acces, types_fixes_par_code
from app.utils.types_acces import TYPES_ACCES
from tests.aides_base import compte


def _noeud(session: Session, code: str) -> Perimetre:
    return session.exec(select(Perimetre).where(Perimetre.code == code)).one()


def _codes(session: Session) -> set[str]:
    return {n.code for n in session.exec(select(Perimetre)).all()}


def test_une_feuille_se_copie_sous_plusieurs_parents_avec_ses_parametres(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, "parking/portail")
        source.icone, source.privatif, source.description = "door-open", True, "Le portail"
        session.add(source)
        fixer_acces(session, source.code, list(TYPES_ACCES))
        session.commit()
        cibles = [f"bat:{batiments[0]}", f"bat:{batiments[1]}"]

        lus = copier_perimetre(source.id, PerimetreCopie(parents=cibles), session, admin)

        assert [lu.code for lu in lus] == [f"{c}/portail" for c in cibles]
        assert [lu.parent for lu in lus] == cibles
        fixes = types_fixes_par_code(session)
        for lu in lus:
            copie = _noeud(session, lu.code)
            assert (copie.libelle, copie.icone, copie.privatif, copie.description) == (
                source.libelle,
                "door-open",
                True,
                "Le portail",
            )
            assert copie.batiment_id is None, "le bâtiment s'hérite du nouveau parent"
            assert sorted(fixes[copie.code]) == sorted(TYPES_ACCES)
            freres = [
                n.ordre
                for n in session.exec(select(Perimetre)).all()
                if n.parent_id == copie.parent_id
            ]
            assert copie.ordre == max(freres), "la copie se range en dernier"
        assert _noeud(session, source.code).parent_id is not None, "la source n'a pas bougé"


def test_une_branche_se_copie_avec_ses_descendants(batiments):
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, "parking")
        enfants = {
            n.code for n in session.exec(select(Perimetre)).all() if n.parent_id == source.id
        }
        cible = f"bat:{batiments[2]}"

        copier_perimetre(source.id, PerimetreCopie(parents=[cible]), session, admin)

        attendus = {c.replace("parking", f"{cible}/parking", 1) for c in enfants}
        assert attendus <= _codes(session)
        assert _noeud(session, f"{cible}/parking").portee_globale is source.portee_globale


def test_un_code_deja_pris_refuse_toute_la_copie(batiments):
    """Tout ou rien : le hall existe déjà dans le bâtiment 2, rien n'est posé au 3."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, f"bat:{batiments[0]}/hall")
        avant = _codes(session)
        with pytest.raises(HTTPException) as refus:
            copier_perimetre(
                source.id,
                PerimetreCopie(parents=["parking", f"bat:{batiments[1]}"]),
                session,
                admin,
            )
        assert refus.value.status_code == 422 and "rien n'a été copié" in refus.value.detail
        session.rollback()
        assert _codes(session) == avant


def test_un_batiment_ne_se_copie_pas_ailleurs(batiments):
    """🔴 Le lien au bâtiment décide QUI LIT : recopié, il ouvrirait la copie aux
    résidents du bâtiment source."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        lus = {n.code: n for n in lister_perimetres(session, admin)}
        assert lus[f"bat:{batiments[0]}"].copiable is False
        assert lus["batiments"].copiable is False, "sa branche contient des bâtiments"
        assert lus["parking/portail"].copiable is True
        with pytest.raises(HTTPException) as refus:
            copier_perimetre(
                _noeud(session, f"bat:{batiments[0]}").id,
                PerimetreCopie(parents=["parking"]),
                session,
                admin,
            )
        assert "bâtiment" in refus.value.detail


def test_les_parents_impossibles_sont_refuses(batiments):
    """Lui-même, son parent actuel, un de ses descendants, un code inconnu, rien."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        source = _noeud(session, "parking")
        for parents, motif in (
            (["parking"], "ne peut pas recevoir"),
            (["parking/places"], "ne peut pas recevoir"),
            (["inconnu"], "inconnu"),
            ([" "], "au moins un"),
        ):
            with pytest.raises(HTTPException) as refus:
                copier_perimetre(source.id, PerimetreCopie(parents=parents), session, admin)
            assert refus.value.status_code == 422 and motif in refus.value.detail, parents
        hall = _noeud(session, f"bat:{batiments[0]}/hall")
        with pytest.raises(HTTPException) as refus:
            copier_perimetre(
                hall.id, PerimetreCopie(parents=[f"bat:{batiments[0]}"]), session, admin
            )
        assert "ne peut pas recevoir" in refus.value.detail
