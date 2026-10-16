"""L'arborescence des périmètres ne change **aucun** verdict d'accès.

Le périmètre décide qui voit une actualité ou un événement
(`utils/visibility.perimetre_visible`) et qui reçoit un e-mail
(`utils/destinataires.batiments_du_perimetre`). Le remplacer par un arbre en base
change la nature de la règle : une comparaison de chaînes devient une question
d'ascendance. Ce fichier est ce qui autorise ce changement.

Le contrôle central n'est pas « la nouvelle règle est-elle correcte ? » — cette
question ne se vérifie pas — mais **« rend-elle exactement les mêmes verdicts que
l'ancienne ? »**. L'ancienne implémentation est donc recopiée ici, telle qu'elle
était avant le remplacement, et rejouée contre la nouvelle sur tous les couples
(périmètre × utilisateur). Un écart fait échouer la suite.

Deux comportements changent **volontairement**, et sont testés comme tels :

1. une donnée illisible **refuse** au lieu d'élargir (`_codes_json_pour_acces`) ;
2. un arbre vide ou inconnu ne restreint rien, ce qui permet de servir une autre
   copropriété sans qu'aucun code de périmètre existe dans le code.
"""

import itertools

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.models.core import (
    Ticket,
    Utilisateur,
)
from app.seed.patrimoine import GABARIT_BATIMENT, poser_arborescence
from app.utils import perimetres as P
from tests.conftest import vider_patrimoine
from app.utils.destinataires import batiments_du_perimetre
from app.utils.visibility import actualite_visible, perimetre_visible
from tests.aides_purge import etat_invalide


# ── L'ancienne implémentation, recopiée telle quelle ──────────────────────────

#: `utils/visibility.SCOPES_RESIDENCE`, supprimée par ce lot.
ANCIENS_SCOPES = frozenset({"résidence", "parking", "cave", "aful"})


def ancien_perimetre_visible(
    perimetres: list[str], roles: list[str], batiment_id: int | None
) -> bool:
    """`utils/visibility.perimetre_visible` d'avant le remplacement."""
    if "admin" in roles or "conseil_syndical" in roles:
        return True
    if not perimetres:
        return True
    perims_lower = {p.lower() for p in perimetres}
    if perims_lower & ANCIENS_SCOPES:
        return True
    if batiment_id is None:
        return True
    return f"bat:{batiment_id}" in perims_lower


def ancien_batiments_du_perimetre(perimetres: list[str]) -> set[int] | None:
    """`utils/destinataires.batiments_du_perimetre` d'avant le remplacement."""
    if not perimetres:
        return None
    ids: set[int] = set()
    for p in perimetres:
        p = p.lower()
        if p in ANCIENS_SCOPES:
            return None
        if p.startswith("bat:"):
            ident = p.split(":", 1)[1]
            if ident.isdigit():
                ids.add(int(ident))
    return ids or None


#: Les libellés que produisait la table en dur (`PERIMETRE_LABELS`), pour les codes
#: réellement en service. Le seed doit les reproduire à l'identique : ils
#: s'affichent sur des contenus déjà publiés.
ANCIENS_LIBELLES = {
    "résidence": "Copropriété entière",
    "parking": "Parking",
    "cave": "Cave",
    "aful": "AFUL",
}


# ── Montage ───────────────────────────────────────────────────────────────────

#  Le montage (quatre bâtiments + arbre semé) et la purge vivent dans
#  `conftest.py` depuis le 14/08/2026 : ils étaient écrits à l'identique ici et
#  dans `test_perimetres_router.py`, et leurs deux `_vider` avaient déjà divergé.
#  La fixture `batiments` est donc injectée sans être déclarée dans ce fichier.
_vider = vider_patrimoine


def utilisateur(roles: str, batiment_id: int | None) -> Utilisateur:
    return Utilisateur(
        nom="X",
        prenom="Y",
        email=f"{roles}-{batiment_id}@test.fr",
        roles_json=roles,
        batiment_id=batiment_id,
        actif=True,
    )


PROFILS = ["résident", "propriétaire", "conseil_syndical", "admin"]


def _auteur(session: Session) -> int:
    """Un utilisateur persisté — `Publication.auteur_id` et `Evenement.auteur_id`
    sont NOT NULL, et un contenu sans auteur ne s'écrit pas."""
    existant = session.exec(
        select(Utilisateur).where(Utilisateur.email == "auteur@test.fr")
    ).first()
    if existant:
        return existant.id
    u = Utilisateur(nom="A", prenom="B", email="auteur@test.fr", actif=True)
    session.add(u)
    session.commit()
    return u.id


# ── Le contrôle central : aucun verdict ne change ─────────────────────────────


def test_equivalence_stricte_sur_les_codes_en_service(batiments):
    """Personne ne gagne ni ne perd un accès. C'est ce qui autorise le changement."""
    codes = list(ANCIENS_SCOPES) + [f"bat:{i}" for i in batiments]
    #  Combinaisons de 0, 1 et 2 périmètres : le cas à deux est celui qui distingue
    #  une intersection d'ensembles d'une remontée d'arbre.
    cibles = [[]] + [[c] for c in codes] + [list(p) for p in itertools.combinations(codes, 2)]
    #  `batiments[-1] + 1` : un utilisateur rattaché à un bâtiment qui n'a pas de
    #  nœud, pour vérifier que l'absence ne devient pas une autorisation.
    rattachements = [None] + batiments + [batiments[-1] + 1]

    ecarts = []
    for cible, roles, batiment_id in itertools.product(cibles, PROFILS, rattachements):
        attendu = ancien_perimetre_visible(cible, [roles], batiment_id)
        obtenu = perimetre_visible(cible, utilisateur(roles, batiment_id))
        if attendu != obtenu:
            ecarts.append((cible, roles, batiment_id, attendu, obtenu))

    #  🔴 UN SEUL écart est voulu, depuis le 02/09/2026 : le compte SANS bâtiment,
    #  qui voyait tout et ne voit plus rien. Le reste du tableau doit être
    #  rigoureusement identique — c'est ce qui prouve que la fermeture du repli
    #  n'a pas déplacé une frontière au passage.
    voulus = [e for e in ecarts if e[2] is None and e[3] is True and e[4] is False]
    autres = [e for e in ecarts if e not in voulus]

    assert not autres, (
        f"{len(autres)} verdict(s) de visibilité modifié(s) HORS du changement "
        f"déclaré : {autres[:5]}\n"
        "  Quelqu'un gagne ou perd un accès sans que ce soit l'objet du lot."
    )
    #  ⚠️ La dérogation ne survit pas à son objet : si plus aucun compte sans
    #  bâtiment ne change de verdict, c'est que le repli est revenu — ou que
    #  `rattachements` ne contient plus `None`, et ce test ne mesure plus le cas
    #  qu'il prétend couvrir.
    assert voulus, (
        "Aucun compte sans bâtiment ne change de verdict : soit le repli permissif "
        "est de retour, soit ce test a cessé d'éprouver le cas `batiment_id=None`. "
        "Dans les deux cas, INCONNU — pas OK."
    )


def test_equivalence_des_destinataires(batiments):
    """Les mêmes membres du conseil syndical sont notifiés, pour les mêmes ciblages."""
    codes = list(ANCIENS_SCOPES) + [f"bat:{i}" for i in batiments]
    cibles = [[]] + [[c] for c in codes] + [list(p) for p in itertools.combinations(codes, 2)]

    ecarts = []
    for cible in cibles:
        attendu = ancien_batiments_du_perimetre(cible)
        obtenu = batiments_du_perimetre(cible)
        if attendu != obtenu:
            ecarts.append((cible, attendu, obtenu))
    assert not ecarts, f"{len(ecarts)} verdict(s) de notification modifié(s) : {ecarts}"


def test_libelles_des_codes_en_service_inchanges(batiments):
    """Un libellé qui change, c'est un changement visible sur du contenu publié."""
    for code, libelle in ANCIENS_LIBELLES.items():
        assert P.perimetre_label_un(code) == libelle

    #  ⚠️ Les bâtiments font exception depuis le 14/08/2026, et c'est un changement
    #  VOULU, pas une dérive : le seed remplissait `libelle` et `libelle_court` à
    #  l'identique (« Bât. {id} »), ce qui rendait le second inutile et imposait
    #  l'abréviation jusque sur le document imprimé remis aux arrivants. Le long
    #  sert aux documents et aux e-mails, l'abrégé aux badges contraints.
    #
    #  Ce test garde tout son sens : il continue d'interdire qu'un libellé bouge
    #  SANS qu'on l'ait décidé — il fallait venir l'éditer ici pour que le lot
    #  passe, et c'est exactement ce qu'on lui demande de faire.
    #  Migration correspondante : `0143_libelle_long_des_batiments`.
    for identifiant in batiments:
        assert P.perimetre_label_un(f"bat:{identifiant}") == f"Bâtiment {identifiant}"
        noeud = P.arbre()[f"bat:{identifiant}"]
        assert noeud.libelle_court == f"Bât. {identifiant}", (
            "l'abrégé doit rester court : c'est lui que lisent le calendrier et le "
            "sélecteur de périmètre, où la place est contrainte"
        )
    #  Le séparateur du rendu multiple ne bouge pas non plus.
    assert P.perimetre_label(["bat:1", "parking"]) == "Bâtiment 1 · Parking"


# ── Le repli permissif est FERMÉ (02/09/2026) — épinglé fermé ────────────────


def test_utilisateur_sans_aucun_batiment_ne_voit_rien(batiments):
    """*« Un utilisateur sans bâtiment ne doit rien voir car il n'est pas résident. »*

    🔴 Ce test disait exactement le contraire jusqu'au 02/09/2026, et il le disait
    à dessein : le repli permissif rendait `True`, et l'épingler empêchait qu'on
    le corrige *par inadvertance*. La correction est venue, décidée — le test
    change donc de sens, pas de raison d'être.
    """
    sans_batiment = utilisateur("résident", None)
    assert perimetre_visible([f"bat:{batiments[0]}"], sans_batiment) is False


def test_un_batiment_ne_donne_pas_acces_aux_autres(batiments):
    """Le corollaire, qui n'était pas éprouvé isolément.

    Fermer sur l'ensemble vide ne dit rien de l'intersection : une implémentation
    qui rendrait `True` dès que l'utilisateur a UN bâtiment quelconque passerait
    le test ci-dessus.
    """
    du_premier = utilisateur("résident", batiments[0])
    assert perimetre_visible([f"bat:{batiments[0]}"], du_premier) is True
    assert perimetre_visible([f"bat:{batiments[1]}"], du_premier) is False
    #  Ciblage multiple : il suffit qu'UN des périmètres visés soit le sien.
    assert perimetre_visible([f"bat:{batiments[1]}", f"bat:{batiments[0]}"], du_premier) is True


# ── Ce qui change volontairement : la donnée abîmée refuse ────────────────────


def _actualite(perimetre_cible) -> Ticket:
    """Une actualité — une affaire de catégorie « Actualité » depuis le 23/09/2026."""
    return Ticket(
        numero="TK-A1",
        titre="T",
        description="C",
        categorie="actualite",
        statut="publie",
        perimetre_cible=perimetre_cible,
        public_cible='["résidents"]',
    )


@pytest.mark.parametrize(
    "cible_corrompue",
    [
        "ceci n'est pas du json",
        '{"pas": "une liste"}',
        "[",
        '"résidence"',
    ],
)
def test_ciblage_illisible_refuse_au_lieu_delargir(batiments, cible_corrompue):
    """Une donnée abîmée élargissait la visibilité : elle la refuse désormais."""
    publication = _actualite(cible_corrompue)
    assert actualite_visible(publication, utilisateur("résident", batiments[0])) is False


def test_ciblage_illisible_reste_visible_du_conseil_syndical(batiments):
    """Sans quoi personne ne pourrait plus corriger la publication abîmée."""
    publication = _actualite("[")
    assert actualite_visible(publication, utilisateur("conseil_syndical", None)) is True


def test_perimetre_absent_reste_permissif(batiments):
    """Champ vide ≠ champ corrompu : l'absence de ciblage n'a jamais rien restreint."""
    publication = _actualite(None)
    assert actualite_visible(publication, utilisateur("résident", batiments[0])) is True


# ── Échec fermé sur un arbre abîmé ───────────────────────────────────────────


def test_code_inconnu_naccorde_rien(batiments):
    """Un contenu qui cite un nœud supprimé n'ouvre aucun accès."""
    assert (
        perimetre_visible(["periscope-imaginaire"], utilisateur("résident", batiments[0])) is False
    )


def test_cycle_de_parente_ne_suspend_pas_et_refuse(batiments):
    """Une boucle dans l'arbre doit rendre la main, et ne rien accorder."""
    with Session(engine) as session:
        a = Perimetre(code="cycle-a", libelle="A")
        b = Perimetre(code="cycle-b", libelle="B")
        session.add(a)
        session.add(b)
        session.flush()
        a.parent_id, b.parent_id = b.id, a.id
        session.add(a)
        session.add(b)
        session.commit()
    P.invalider_cache()

    assert P.a_portee_globale(["cycle-a"]) is False
    assert P.batiments_cibles(["cycle-a"]) == set()
    assert perimetre_visible(["cycle-a"], utilisateur("résident", batiments[0])) is False


def test_parent_orphelin_ne_suspend_pas_et_refuse(batiments):
    """Un `parent_id` qui ne pointe sur rien arrête la remontée sans lever."""
    #  🔴 L'état corrompu est le SUJET de ce test : il faut donc le fabriquer,
    #  et avec les clés vérifiées la base le refuse (#546). La porte est locale et
    #  nommée — supprimer le test aurait retiré le contrôle qui protège d'une
    #  corruption au moment même où l'on active le mécanisme censé la prévenir.
    with Session(engine) as session, etat_invalide(session):
        session.add(Perimetre(code="orphelin", libelle="Orphelin", parent_id=999_999))
        session.commit()
    P.invalider_cache()

    assert P.a_portee_globale(["orphelin"]) is False
    assert perimetre_visible(["orphelin"], utilisateur("résident", batiments[0])) is False


# ── L'arbre vide : servir une autre copropriété ──────────────────────────────


def test_arbre_vide_ne_leve_aucune_erreur(arbre_vide):
    """Aucun périmètre configuré est un état valide, pas une panne.

    C'est le contrôle qui prouve qu'aucun code de périmètre n'est en dur : une
    copropriété qui repart de zéro ne doit obtenir ni 500 ni exception.
    """
    assert P.arbre() == {}
    assert P.code_par_defaut() is None
    assert P.parse_perimetres(None) == []
    assert P.parse_json_perimetres(None) == []
    assert P.a_portee_globale(["quoi-que-ce-soit"]) is False
    assert P.batiments_cibles(["quoi-que-ce-soit"]) == set()
    #  Un contenu sans périmètre reste visible : c'est le sens de « rien ne casse ».
    assert perimetre_visible([], utilisateur("résident", 1)) is True
    #  Et le libellé ne sort jamais un code brut illisible.
    assert P.perimetre_label_un("bat:7") == "Bât. 7"


def test_arbre_vide_naccorde_rien_sur_un_code_cite(arbre_vide):
    """Un arbre vide ou illisible n'est **pas** une autorisation.

    Première écriture de `perimetre_visible` : un court-circuit à `True` dès que
    l'arbre était vide. `tests/test_documents_acces.py` l'a attrapé — une pièce
    jointe ciblée sur un autre bâtiment devenait lisible dès que la table manquait.
    Un contrôle qui ne peut pas s'exécuter ne renvoie jamais OK (`standards/04`).
    """
    resident = utilisateur("résident", 1)
    assert perimetre_visible(["bat:1"], resident) is False
    assert perimetre_visible(["résidence"], resident) is False
    assert batiments_du_perimetre(["bat:1"]) is None

    #  Le conseil syndical et l'administration gardent l'accès : sans quoi personne
    #  ne pourrait reconstruire l'arborescence.
    assert perimetre_visible(["bat:1"], utilisateur("conseil_syndical", None)) is True
    assert perimetre_visible(["bat:1"], utilisateur("admin", None)) is True


def test_perimetre_par_defaut_vient_des_donnees(batiments):
    """La valeur par défaut est une donnée, pas la chaîne « résidence » en dur."""
    assert P.code_par_defaut() == "résidence"
    assert P.parse_perimetres(None) == ["résidence"]

    #  Renommer le nœud par défaut ne casse rien : le repli suit les données.
    with Session(engine) as session:
        racine = session.exec(select(Perimetre).where(Perimetre.code == "résidence")).one()
        racine.libelle = "Toute la copro"
        session.add(racine)
        session.commit()
    P.invalider_cache()
    assert P.perimetre_label_un("résidence") == "Toute la copro"
    assert P.parse_perimetres(None) == ["résidence"]


# ── La cave relève d'un bâtiment, sans casser l'historique ───────────────────


def test_cave_retiree_de_la_saisie_mais_toujours_rendue(batiments):
    """Historique préservé, pastille retirée : le seul compromis qui ne coûte rien."""
    with Session(engine) as session:
        cave = session.exec(select(Perimetre).where(Perimetre.code == "cave")).one()
        assert cave.selectionnable is False, "la cave ne doit plus être proposée à la saisie"
        assert cave.portee_globale is True, "les contenus déjà publiés gardent leur visibilité"

    #  Une actualité déjà publiée sur « cave » reste visible de tous, et affichée.
    assert perimetre_visible(["cave"], utilisateur("résident", batiments[1])) is True
    assert P.perimetre_label_un("cave") == "Cave"

    #  Et la façon normale de cibler une cave est désormais celle du bâtiment.
    code_bat = f"bat:{batiments[0]}"
    assert f"{code_bat}/caves" in P.arbre()


def test_espace_profond_concerne_son_batiment(batiments):
    """« Bât. 2 › Hall d'entrée » concerne le bâtiment 2, et lui seul.

    C'est la remontée d'arbre : le hall ne porte pas de `batiment_id`, il l'hérite.
    """
    premier, second = batiments[0], batiments[1]
    hall = f"bat:{second}/hall"

    assert P.batiments_cibles([hall]) == {second}
    assert perimetre_visible([hall], utilisateur("résident", second)) is True
    assert perimetre_visible([hall], utilisateur("résident", premier)) is False
    #  Les destinataires suivent la même remontée.
    assert batiments_du_perimetre([hall]) == {second}
    #  Et le libellé du parent n'écrase pas celui de l'espace.
    #  🔴 Le libellé QUALIFIE l'espace par son bâtiment depuis le 18/08/2026 : le
    #  gabarit pose le même « Hall d'entrée » sous chaque bâtiment, et un ticket
    #  visant deux d'entre eux affichait « Hall d'entrée · Hall d'entrée ».
    assert P.perimetre_label_un(hall) == f"Bât. {second} › Hall d'entrée"


def test_enfant_dun_perimetre_global_est_global(batiments):
    """« Parking › Portail d'accès » concerne tout le monde, sans le redire."""
    assert P.a_portee_globale(["parking/portail"]) is True
    assert perimetre_visible(["parking/portail"], utilisateur("résident", batiments[0])) is True
    assert batiments_du_perimetre(["parking/portail"]) is None


def test_regroupement_batiments_ne_se_cible_pas(batiments):
    """Un nœud d'organisation n'est pas une cible : on choisit un bâtiment."""
    with Session(engine) as session:
        groupe = session.exec(select(Perimetre).where(Perimetre.code == "batiments")).one()
        assert groupe.selectionnable is False
        assert groupe.portee_globale is False, (
            "un regroupement de bâtiments à portée globale rendrait tous les espaces "
            "de tous les bâtiments visibles de tous les résidents"
        )


# ── Le seed ───────────────────────────────────────────────────────────────────


def test_seed_idempotent_et_respectueux(batiments):
    """Le seed pose ce qui manque et ne réécrit jamais ce qui existe."""
    with Session(engine) as session:
        avant = len(session.exec(select(Perimetre)).all())
        renomme = session.exec(select(Perimetre).where(Perimetre.code == "aful")).one()
        renomme.libelle = "Parking public (AFUL)"
        session.add(renomme)
        session.commit()

        assert poser_arborescence(session) == 0
        session.commit()
        assert len(session.exec(select(Perimetre)).all()) == avant

        toujours = session.exec(select(Perimetre).where(Perimetre.code == "aful")).one()
        assert toujours.libelle == "Parking public (AFUL)", (
            "le seed a écrasé une personnalisation faite depuis l'administration"
        )


def test_un_noeud_par_batiment_reel(batiments):
    """Les bâtiments sont lus en base, jamais énumérés par une constante.

    L'implémentation précédente générait `bat:1` à `bat:9` depuis `_BATIMENTS = 9`,
    sans rapport avec le contenu de la table — et le front s'arrêtait à `bat:4`.
    """
    arbre = P.arbre()
    for identifiant in batiments:
        assert f"bat:{identifiant}" in arbre
        for suffixe, _, _ in GABARIT_BATIMENT:
            assert f"bat:{identifiant}/{suffixe}" in arbre
    #  Aucun bâtiment inventé au-delà de ce que la base contient.
    assert f"bat:{batiments[-1] + 1}" not in arbre


# ── Ce que ce fichier NE couvre plus ─────────────────────────────────────────
#
#  Les deux contrôles STATIQUES — « aucune liste de périmètres ne réapparaît » —
#  vivent dans `test_perimetres_liste_en_dur.py` depuis le 02/09/2026. Ils ne
#  montent aucune base et ne dépendent d'aucune fixture : la couture est réelle,
#  ce n'est pas la ligne où le compteur a dépassé.
