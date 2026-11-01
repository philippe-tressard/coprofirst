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
            #  3ᵉ sous Parking ; « Voies de circulation », qui la précède, n'existe
            #  pas dans un bâtiment : elle garde son rang (#2450).
            assert _rangs(session, copie.parent_id).index(copie.code) == 2
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


def _rangs(session: Session, parent_id: int) -> list[str]:
    freres = session.exec(select(Perimetre).where(Perimetre.parent_id == parent_id)).all()
    return [n.code for n in sorted(freres, key=lambda n: (n.ordre, n.code))]


def test_la_copie_prend_la_place_de_la_source_parmi_ses_freres(batiments):
    """Signalé à l'écran (#2450) : « Poubelles », après « Caves » dans le
    bâtiment 1, arrivait en DERNIER dans les autres bâtiments. Elle se range
    après leur « Caves », et la fratrie est renumérotée."""
    with Session(engine) as session:
        admin = compte(session, prefixe="admin")
        bat1, bat2 = (_noeud(session, f"bat:{b}") for b in batiments[:2])
        caves = _noeud(session, f"{bat1.code}/caves")
        #  Même rang que « Caves », départagé par le code : juste après elle.
        source = Perimetre(
            code=f"{bat1.code}/zz-poubelles",
            libelle="Poubelles",
            parent_id=bat1.id,
            ordre=caves.ordre,
        )
        session.add(source)
        session.commit()
        assert (
            _rangs(session, bat1.id).index(source.code)
            == _rangs(session, bat1.id).index(caves.code) + 1
        )

        copier_perimetre(source.id, PerimetreCopie(parents=[bat2.code]), session, admin)

        rangs = _rangs(session, bat2.id)
        assert rangs.index(f"{bat2.code}/zz-poubelles") == rangs.index(f"{bat2.code}/caves") + 1
        ordres = sorted(
            n.ordre
            for n in session.exec(select(Perimetre).where(Perimetre.parent_id == bat2.id)).all()
        )
        assert ordres == list(range(len(rangs)))


def test_sans_voisin_retrouve_la_copie_garde_le_rang_de_la_source():
    """Le frère qui précède est cherché par son nom, puis par la fin de son code ;
    à défaut, la copie garde le rang de la source ; en tête, elle reste en tête."""
    from app.utils.perimetres.branche import fratrie_de_la_copie

    def n(id_, code, libelle, parent_id, ordre):
        return Perimetre(id=id_, code=code, libelle=libelle, parent_id=parent_id, ordre=ordre)

    arbre = [
        n(1, "a", "A", None, 0),
        n(2, "b", "B", None, 1),
        n(10, "a/x", "Hall", 1, 0),
        n(11, "a/y", "Caves", 1, 1),
        n(12, "a/z", "Poubelles", 1, 2),
        n(20, "b/p", "Paliers", 2, 0),
        n(21, "b/q", "Toit", 2, 1),
        n(22, "b/caves-2", "Les caves", 2, 2),
    ]
    copie = Perimetre(id=99, code="b/z", libelle="Poubelles", parent_id=2)
    par_code = {p.code: p for p in arbre}
    #  « Caves » n'existe pas sous B, ni par nom ni par code : même rang (2).
    rangee = fratrie_de_la_copie(par_code["a/z"], arbre, 2, copie)
    assert [p.code for p in rangee] == ["b/p", "b/q", "b/z", "b/caves-2"]
    #  Par le nom : « Hall » précède « Caves » ; le « Hall » de B est retrouvé.
    arbre.append(n(23, "b/entree", "Hall", 2, 3))
    rangee = fratrie_de_la_copie(par_code["a/y"], arbre, 2, copie)
    assert [p.code for p in rangee][-2:] == ["b/entree", "b/z"]
    #  En tête dans la source : en tête dans la cible.
    rangee = fratrie_de_la_copie(par_code["a/x"], arbre, 2, copie)
    assert rangee[0] is copie
