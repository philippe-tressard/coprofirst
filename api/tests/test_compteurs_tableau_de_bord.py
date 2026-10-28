"""Un compteur annonce-t-il ce que son écran contient vraiment ?

C'est le seul contrôle qui vaille sur une pastille, et c'est celui qui manquait :
les trois compteurs de la rangée du tableau de bord étaient chacun cohérents avec
eux-mêmes, aucun avec sa destination (#399). Ils ne pouvaient donc pas se
contredire à la relecture — il fallait ouvrir l'écran pour voir l'écart.

Chaque test prend la **sortie de l'API** que l'écran reçoit (`GET /sondages`,
`GET /tickets`, la file de `/admin`) et compte ce que l'écran en tirera, puis
compare au nombre annoncé par `flux.sante`. Aucun test ne rappelle la règle qu'il
vérifie : la refaire des deux côtés reviendrait à comparer une fonction à
elle-même.

Ce que ce fichier attrape, et que rien n'attrapait :

  • (b) le compteur des sondages ignorait le ciblage — périmètre ET public ;
  • (c) il ignorait aussi la date de clôture, ne regardant que `cloture_forcee` ;
  • (d) « comptes en attente » comptait tout compte inactif, refus et
        désactivations volontaires compris ;
  • (a) le compteur des tickets se calculait côté client sur le fil filtré, donc
        sur une portée que le serveur ne connaissait même pas.

Il attrape aussi une divergence qui n'existe pas encore : `GET /tickets` filtre en
**SQL** (`auteur_id` ou `saisi_pour_user_id`) là où `flux.sante` filtre en Python
via `ticket_visible`. Deux écritures de la même règle, gardées séparées parce que
l'une doit filtrer en base — le jour où l'une bougera sans l'autre, c'est ici que
ça tombera.
"""

from datetime import timedelta

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    CommandeAcces,
    Copropriete,
    DemandeModificationProfil,
    Lot,
    Sondage,
    StatutCommande,
    Ticket,
    Utilisateur,
)
from app.routers.admin.comptes import comptes_en_attente
from app.routers.flux.commun import ContexteFlux
from app.routers.flux.sante import calculer
from app.routers.sondages.crud import list_sondages
from app.routers.tickets.crud import list_tickets
from app.utils import perimetres as P
from app.utils.horloge import maintenant
from app.seed.patrimoine import poser_arborescence
from tests.conftest import vider_patrimoine

MODELES_ECRITS = (
    DemandeModificationProfil,
    CommandeAcces,
    Ticket,
    Sondage,
    Lot,
    Utilisateur,
)


@pytest.fixture()
def base():
    """Copropriété de deux bâtiments, arbre semé, tables vides pour le reste."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session, MODELES_ECRITS)
        copro = Copropriete(nom="Test compteurs", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        poser_arborescence(session)
        session.commit()
        P.invalider_cache()
        yield session
        vider_patrimoine(session, MODELES_ECRITS)
    P.invalider_cache()


def _batiments(session: Session) -> list[int]:
    return list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())


def _utilisateur(session: Session, email: str, roles: str, batiment_id=None) -> Utilisateur:
    u = Utilisateur(
        nom="N",
        prenom=email.split("@")[0],
        email=email,
        roles_json=roles,
        actif=True,
        batiment_id=batiment_id,
        decision_compte_le=maintenant(),
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _contexte(session: Session, user: Utilisateur) -> ContexteFlux:
    now = maintenant()
    return ContexteFlux(session=session, user=user, now=now, since=now - timedelta(days=377))


def _sondage(session: Session, auteur_id: int, **kw) -> Sondage:
    s = Sondage(question="Q", auteur_id=auteur_id, **kw)
    session.add(s)
    session.commit()
    return s


#: Ce que l'écran retient comme clos — c'est-à-dire **le champ que l'API lui
#: envoie**, plus aucune règle.
#:
#: Cette fonction réécrivait `estCloture()`, la règle que la page des sondages
#: portait en JavaScript, parce qu'elle ne pouvait pas être importée (les
#: contextes de build sont `./api` et `./front`, rien de la racine n'entre dans
#: les images). C'était le seul moyen de vérifier que les deux côtés
#: s'accordaient.
#:
#: Depuis #468, **le front ne calcule plus rien** : `GET /sondages` expose
#: `cloture`, rempli par la même `sondage_clos()` que la fiche et le fil. Garder
#: la copie ici reviendrait à vérifier une règle qui n'existe plus d'un côté —
#: un contrôle qui ment, exactement la classe de défaut que ce fichier traque.
def _clos_pour_l_ecran(sondage_lu) -> bool:
    return bool(sondage_lu.cloture)


# ── Sondages — (b) le ciblage, (c) la clôture ────────────────────────────────


def test_le_compteur_sondages_egale_ce_que_l_ecran_montre(base):
    """Pour chaque profil : la pastille annonce ce que `/sondages` rendra d'ouvert."""
    bat1, bat2 = _batiments(base)
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    resident = _utilisateur(base, "resident@test.fr", "résident", batiment_id=bat1)

    _sondage(base, cs.id)  # ouvert, sans ciblage → visible de tous
    _sondage(base, cs.id, perimetre_cible=f'["bat:{bat2}"]')  # autre bâtiment
    _sondage(base, cs.id, cloture_le=maintenant() - timedelta(days=1))  # échéance passée
    _sondage(base, cs.id, cloture_forcee=True)  # clos à la main

    for user in (resident, cs):
        annonce = calculer(_contexte(base, user)).sondages_actifs
        a_l_ecran = [s for s in list_sondages(session=base, user=user) if not _clos_pour_l_ecran(s)]
        assert annonce == len(a_l_ecran), (
            f"{user.email} : pastille {annonce}, écran {len(a_l_ecran)}"
        )


def test_un_sondage_cible_ailleurs_ne_gonfle_pas_la_pastille_du_resident(base):
    """(b) — le cas le plus visible : « Sondages 1 » et un écran vide."""
    _bat1, bat2 = _batiments(base)
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    resident = _utilisateur(base, "resident@test.fr", "résident", batiment_id=_bat1)
    _sondage(base, cs.id, perimetre_cible=f'["bat:{bat2}"]')

    assert calculer(_contexte(base, resident)).sondages_actifs == 0
    assert calculer(_contexte(base, cs)).sondages_actifs == 1  # le CS voit tout


def test_une_echeance_passee_clot_le_sondage_pour_le_compteur(base):
    """(c) — `~cloture_forcee` n'excluait que la clôture manuelle."""
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    _sondage(base, cs.id, cloture_le=maintenant() - timedelta(minutes=1))

    assert calculer(_contexte(base, cs)).sondages_actifs == 0


# ── Tickets — (a) la portée du décompte ──────────────────────────────────────


def test_le_compteur_tickets_egale_ce_que_l_ecran_montre(base):
    """La pastille compte les tickets ouverts que l'utilisateur peut ouvrir.

    ⚠️ Les valeurs attendues ont changé le 02/09/2026 avec l'ouverture par
    périmètre (#710) — et c'est le TEST qui avait tort, pas la règle : il
    encodait « chacun ne voit que les siens », qui n'est plus la règle du site.

    Ce que l'invariant vérifie n'a pas bougé : **la pastille et l'écran comptent
    la même chose**. Un décompte plus large que la liste annonce des tickets
    qu'on ne trouve pas ; plus étroit, il en cache.

    Les tickets portent ici des périmètres DIFFÉRENTS, sans quoi l'ouverture les
    rendrait tous visibles de tout le monde et le test ne distinguerait plus rien
    — il resterait vert en ayant cessé de mesurer.
    """
    bat1, bat2 = _batiments(base)[:2]
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    resident = _utilisateur(base, "resident@test.fr", "résident", batiment_id=bat1)
    autre = _utilisateur(base, "autre@test.fr", "résident", batiment_id=bat2)

    #  (auteur, périmètre) — qui le voit se lit dans la colonne de droite.
    lot = [
        (resident, f'["bat:{bat1}"]'),  # resident (auteur+bât.), cs
        (autre, f'["bat:{bat2}"]'),  # autre (auteur+bât.), cs
        (autre, '["résidence"]'),  # tout le monde : portée globale
    ]
    for i, (auteur, perimetre) in enumerate(lot):
        base.add(
            Ticket(
                numero=f"T{i}",
                titre="T",
                description="D",
                #  Une catégorie que le périmètre RESTREINT : une Panne, lue de
                #  tous les copropriétaires depuis le 30/09/2026, ne distinguerait
                #  plus les deux bâtiments — le test resterait vert sans mesurer.
                categorie="espaces_verts",
                auteur_id=auteur.id,
                perimetre_cible=perimetre,
            )
        )
    base.commit()

    for user, attendu in ((resident, 2), (autre, 2), (cs, 3)):
        annonce = calculer(_contexte(base, user)).tickets_ouverts
        ouverts_a_l_ecran = [
            t for t in list_tickets(session=base, user=user) if t.statut in ("ouvert", "en_cours")
        ]
        assert annonce == len(ouverts_a_l_ecran) == attendu, (
            f"{user.email} : pastille {annonce}, écran {len(ouverts_a_l_ecran)}, attendu {attendu}"
        )


# ── Validations — (d) ce qu'est un compte « en attente » ─────────────────────


def _compte_inactif(session: Session, email: str, decide: bool) -> Utilisateur:
    u = Utilisateur(
        nom="N",
        prenom="P",
        email=email,
        actif=False,
        decision_compte_le=maintenant() if decide else None,
    )
    session.add(u)
    session.commit()
    return u


def test_le_compteur_validations_egale_la_file_de_l_ecran(base):
    """La pastille Espace CS annonce exactement son onglet « Comptes & accès »."""
    bat1, _bat2 = _batiments(base)
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    lot = Lot(batiment_id=bat1, numero="A1")
    base.add(lot)
    base.commit()
    base.refresh(lot)

    _compte_inactif(base, "attente@test.fr", decide=False)
    base.add(CommandeAcces(user_id=cs.id, lot_id=lot.id, type="vigik"))
    base.commit()

    annonce = calculer(_contexte(base, cs)).validations_cs
    a_l_ecran = len(comptes_en_attente(session=base)) + len(
        base.exec(
            select(CommandeAcces).where(CommandeAcces.statut == StatutCommande.en_attente)
        ).all()
    )
    assert annonce == a_l_ecran == 2


def test_un_compte_refuse_ou_desactive_quitte_la_file(base):
    """(d) — `actif == False` ne veut pas dire « en attente ».

    Le compte refusé est le cas qui ne pouvait pas se voir : le refus n'écrivait
    aucun état, donc rien ne le distinguait d'une inscription du jour, et il
    revenait à chaque chargement de l'écran.
    """
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    _compte_inactif(base, "attente@test.fr", decide=False)
    _compte_inactif(base, "refuse@test.fr", decide=True)
    _compte_inactif(base, "desactive@test.fr", decide=True)

    assert calculer(_contexte(base, cs)).validations_cs == 1
    assert [u.email for u in comptes_en_attente(session=base)] == ["attente@test.fr"]


def test_la_pastille_admin_somme_les_trois_files_de_son_ecran(base):
    """Comptes + demandes d'accès + demandes de profil — la troisième manquait."""
    bat1, _bat2 = _batiments(base)
    admin = _utilisateur(base, "admin@test.fr", "admin")
    lot = Lot(batiment_id=bat1, numero="A1")
    base.add(lot)
    base.commit()
    base.refresh(lot)

    _compte_inactif(base, "attente@test.fr", decide=False)
    base.add(CommandeAcces(user_id=admin.id, lot_id=lot.id, type="vigik"))
    base.add(DemandeModificationProfil(utilisateur_id=admin.id, motif="M"))
    base.commit()

    sante = calculer(_contexte(base, admin))
    assert sante.validations_admin == 3
    #  L'Espace CS n'en montre que deux : les demandes de profil ne se traitent
    #  que depuis /admin. Les deux pastilles annoncent chacune SON écran.
    assert sante.validations_cs == 2


# ── Cohérence visibilité / compteur ──────────────────────────────────────────


def test_un_compteur_reserve_vaut_zero_pour_qui_ne_voit_pas_sa_pastille(base):
    """L'autre moitié de la règle : ne pas calculer ce qui ne s'affichera pas.

    La condition de visibilité vit côté front (`#lib/raccourcis.ts`), la décision
    de calculer vit ici. Les deux doivent dire la même chose : une pastille
    masquée dont le serveur remplit le compteur, c'est du travail inutile ; une
    pastille visible dont le compteur vaut 0 faute de droit, c'est un mensonge à
    l'écran.
    """
    bat1, _bat2 = _batiments(base)
    resident = _utilisateur(base, "resident@test.fr", "résident", batiment_id=bat1)
    cs = _utilisateur(base, "cs@test.fr", "conseil_syndical")
    _compte_inactif(base, "attente@test.fr", decide=False)

    #  Le résident ne voit ni Espace CS ni Admin.
    sante_resident = calculer(_contexte(base, resident))
    assert sante_resident.validations_cs == 0
    assert sante_resident.validations_admin == 0
    assert sante_resident.tickets_relance_syndic == 0

    #  Le CS voit Espace CS, pas Admin — /admin est fermé au CS non-admin.
    sante_cs = calculer(_contexte(base, cs))
    assert sante_cs.validations_cs == 1
    assert sante_cs.validations_admin == 0
