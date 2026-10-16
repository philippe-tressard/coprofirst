"""Garde-fou : appariement des badges Vigik et télécommandes aux résidents.

**Ce mécanisme n'était couvert par aucun test depuis son ouverture** — 1 203
lignes réparties sur `auto_match_service.py`, `import_vigiks.py` et
`import_telecommandes.py`. Rien ne signalait une régression, ni un effet de bord
d'une évolution voisine. Constat du 03/08/2026, à la demande de l'utilisateur.

Ce que ces tests couvrent : les fonctions **pures** de rapprochement de noms,
qui sont le cœur de la décision et la partie la plus fragile — un fichier
d'import contient des noms saisis à la main par le syndic, avec titres,
accents, apostrophes, occupants multiples dans une même cellule.

Ce qu'ils ne couvrent PAS, faute de base de test dans ce projet : la création
effective des liens (`_create_user_vigiks`, `_auto_match_tc`) et les lecteurs de
fichiers Excel. C'est une limite assumée, pas un oubli — cf.
`standards/04-fiabilite-des-controles.md` §12.

Ce sont des tests de **caractérisation** : ils figent le comportement observé,
y compris ses arbitrages discutables (voir `test_le_prenom_seul_ne_matche_pas`).
Les faire échouer n'est donc pas nécessairement un défaut — c'est un changement
de règle qui doit être conscient.
"""

import pytest

from app.utils.rapprochement_noms import (
    _matches_user,
    _cle_de_nom,
    _split_name_candidates,
    _tokens,
    _user_keys,
)


# ── Normalisation ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("DUPONT", "dupont"),
        ("  Dupont  ", "dupont"),
        ("Éric", "eric"),
        ("MÜLLER", "muller"),
        ("D'ARTAGNAN", "d artagnan"),
        ("Saint-Exupéry", "saint exupery"),
        ("de La Fontaine", "de la fontaine"),
        ("M. DUPONT", "m dupont"),
        (None, ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalisation(brut, attendu):
    """Accents, casse, ponctuation et espaces multiples se neutralisent."""
    assert _cle_de_nom(brut) == attendu


# ── Découpage des cellules multi-occupants ───────────────────────────────────


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("DUPONT Jean", ["DUPONT Jean"]),
        ("DUPONT; MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT / MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT | MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT & MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT + MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT ET MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT et MARTIN", ["DUPONT", "MARTIN"]),
        ("DUPONT OU MARTIN", ["DUPONT", "MARTIN"]),
        ("", []),
        (None, []),
    ],
)
def test_decoupage_multi_occupants(brut, attendu):
    """Une cellule d'import contient souvent plusieurs occupants d'un même lot."""
    assert _split_name_candidates(brut) == attendu


def test_le_decoupage_ne_casse_pas_un_nom_contenant_et():
    """« ET » n'est un séparateur qu'entouré d'espaces — pas dans « GAETAN »."""
    assert _split_name_candidates("GAETAN DUPONT") == ["GAETAN DUPONT"]


# ── Clés de recherche d'un résident ──────────────────────────────────────────


def test_les_cles_couvrent_les_deux_ordres_et_les_variantes_compactes():
    cles = _user_keys("Dupont", "Jean")
    for attendu in ("dupont", "dupont jean", "jean dupont", "dupontjean", "jeandupont"):
        assert attendu in cles, attendu


def test_le_prenom_seul_ne_matche_pas():
    """Arbitrage volontaire, documenté dans le code : sans lui, un prénom
    courant apparierait un homonyme au badge d'un autre copropriétaire."""
    cles = _user_keys("Dupont", "Philippe")
    assert "philippe" not in cles
    assert not _matches_user("PHILIPPE", cles)


def test_un_nom_compose_reste_apparie():
    cles = _user_keys("de La Fontaine", "Jean")
    assert _matches_user("DE LA FONTAINE", cles)
    assert _matches_user("de la fontaine Jean", cles)


# ── Correspondance — les cas réels des fichiers du syndic ────────────────────


@pytest.mark.parametrize(
    "saisie",
    [
        "DUPONT Jean",
        "Jean DUPONT",
        "dupont jean",
        "DUPONT  JEAN",  # espaces multiples
        "M. DUPONT JEAN",  # civilité en préfixe
        "DUPONT",  # nom seul
        "Mme DUPONT",
        "DUPONT-Jean",  # trait d'union
    ],
)
def test_correspondances_attendues(saisie):
    assert _matches_user(saisie, _user_keys("Dupont", "Jean")), saisie


@pytest.mark.parametrize(
    "saisie",
    [
        "MARTIN Pierre",
        "",
        "   ",
        "SCI DU PARC",
    ],
)
def test_non_correspondances(saisie):
    assert not _matches_user(saisie, _user_keys("Dupont", "Jean")), saisie


def test_un_occupant_est_trouve_dans_une_cellule_partagee():
    """Cas courant : deux noms dans la même cellule d'un lot en indivision."""
    cles = _user_keys("Caron", "Christophe")
    assert _matches_user("ABEL; CARON", cles)
    assert _matches_user("DUPONT ET CARON", cles)
    assert _matches_user("ABEL CARON", cles)


def test_un_homonyme_de_prenom_n_est_pas_apparie():
    """Le risque le plus grave : donner à un résident le badge d'un autre.

    « Philippe MARTIN » ne doit pas récupérer le badge de « Philippe DUPONT ».
    """
    cles_dupont = _user_keys("Dupont", "Philippe")
    assert not _matches_user("MARTIN Philippe", cles_dupont)
    assert not _matches_user("Philippe MARTIN", cles_dupont)


# ── Tokens significatifs ─────────────────────────────────────────────────────


def test_les_mots_courts_sont_ecartes():
    """Un seuil trop bas apparierait sur « de », « la », « du »."""
    assert _tokens("de la fontaine") == ["fontaine"]
    assert _tokens("M. DUPONT") == ["dupont"]


# ── La chaîne d'appel doit rester branchée ───────────────────────────────────


def test_l_appariement_est_declenche_a_la_validation_d_un_compte():
    """Sans ces points d'appel, un nouveau résident n'obtient jamais ses badges.

    C'est la partie que les tests unitaires ne peuvent pas voir : la logique
    peut être parfaite et n'être appelée par personne.
    """
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[2]
    appelants = {
        "api/app/routers/auth.py": "inscription / validation d'e-mail",
        #  Chemin suivi au découpage de `admin.py` en paquet (06/08/2026). Un test
        #  qui cite un fichier en dur casse au premier déplacement — c'est le prix
        #  d'un contrôle de point d'appel, et il vaut mieux le payer ici qu'ignorer
        #  que l'appariement puisse disparaître sans erreur visible.
        "api/app/routers/admin/comptes.py": "activation d'un compte par un administrateur",
    }
    for chemin, contexte in appelants.items():
        source = (racine / chemin).read_text(encoding="utf-8")
        assert "auto_match_pour_utilisateur" in source, (
            f"{chemin} n'appelle plus l'appariement ({contexte}) : les badges "
            "ne seront plus rattachés automatiquement, sans aucune erreur visible."
        )


# ── Ce que l'appariement accepte volontairement, et ses conséquences ─────────
#
# Les tests ci-dessous NE SONT PAS des validations : ils figent un comportement
# à risque pour qu'il soit visible et surveillé. Les faire échouer signifierait
# que la règle a changé — ce qui serait une bonne nouvelle, mais doit être
# conscient.


def test_le_prenom_de_l_import_n_ecarte_jamais():
    """VOULU : le prénom ajoute des clés, il n'en exclut jamais.

    Confirmé par l'utilisateur le 03/08/2026 : **un foyer partage ses accès**.
    Conjoint et enfants disposant d'un compte doivent retrouver les badges du
    lot, alors que le fichier du syndic ne nomme souvent qu'un seul occupant.
    L'appariement sur le nom de famille seul est donc la règle, pas une
    approximation à corriger.

    ⚠️ NE PAS « corriger » en exigeant le prénom, ni en supprimant
    l'auto-résolution des correspondances par nom seul : ce sont exactement les
    cas de famille ci-dessus. Ce test existe pour empêcher ce faux correctif.

    Cas résiduel, non traitable par le code : deux foyers SANS LIEN portant le
    même nom de famille, dans des lots différents. Les fichiers d'import ne
    portent aucune colonne de lot (télécommandes : propriétaire, locataire,
    référence — Vigik : idem), donc le nom est la seule clé disponible. Seul un
    fichier plus riche fourni par le syndic lèverait l'ambiguïté.
    """
    cles = _user_keys("Martin", "Jean")
    for saisie in ("MARTIN Pierre", "MARTIN Sophie", "Pierre MARTIN"):
        assert _matches_user(saisie, cles), (
            f"« {saisie} » n'est plus apparié à Martin Jean — si c'est voulu, "
            "retirer ce test ; la correction attendue est côté auto-résolution."
        )


def test_les_noms_de_famille_courts_echappent_a_cet_elargissement():
    """Asymétrie NON VOULUE : effet de bord du seuil « mot > 3 caractères ».

    Puisque le partage familial est la règle (cf. test ci-dessus), un résident
    nommé Roy, Gay ou Cot en est privé : son conjoint ne récupère PAS les badges
    du lot si le fichier ne nomme que lui. C'est le seul des trois constats du
    03/08/2026 qui soit un vrai défaut — un patronyme court ne devrait pas
    changer la règle.

    Non corrigé : abaisser le seuil rouvrirait les appariements sur « de »,
    « la », « du ». La correction juste compare le mot aux clés NOM sans seuil
    de longueur, le seuil ne servant qu'à écarter les mots vides.
    """
    cles = _user_keys("Roy", "Jean")
    assert _matches_user("ROY", cles), "le nom seul reste apparié"
    assert not _matches_user("ROY Pierre", cles), (
        "les noms de 3 caractères ou moins ne s'apparient pas par le nom seul"
    )


def test_une_societe_portant_le_nom_du_coproprietaire_est_appariee():
    """« SCI DUPONT ET FILS » est apparié à Dupont Jean.

    Souvent souhaitable — le gérant de la SCI est le résident — mais c'est un
    appariement d'une personne morale à une personne physique, sans contrôle.
    """
    assert _matches_user("SCI DUPONT ET FILS", _user_keys("Dupont", "Jean"))


#  🔴 `test_l_auto_resolution_cree_le_badge_sans_revue` est parti dans
#  `test_acces_existants_apparies.py` le 18/09/2026, et il a changé de nature.
#
#  Il cherchait ici la chaîne « session.add(tc) » dans le fichier source, en se
#  disant contraint : « la logique est trop couplée à la base pour être exercée
#  ici ». Elle ne l'était pas — une base de test jetable suffit. Le contrôle
#  statique a d'ailleurs cassé au premier renommage de variable, sans que rien
#  ne soit cassé dans le produit : il lisait le TEXTE d'une fonction, pas son
#  comportement (`standards/04` §14).
#
#  Le remplaçant crée une ligne d'import, lance la résolution et regarde
#  l'accès produit — sur les DEUX types.


def test_le_cs_voit_les_imports_auto_resolus():
    """Le filet de sécurité du mécanisme est la revue manuelle du CS.

    L'appariement large est volontaire (partage familial) et l'auto-résolution
    crée les badges sans validation préalable : la sécurité repose donc
    entièrement sur le fait que le CS **voie** ce qui a été résolu tout seul, et
    par qui. Un écran qui ne montrerait que les lignes en attente rendrait ce
    filet inexistant — sans que rien ne le signale.

    Trois conditions, vérifiées ici parce qu'aucune n'est évidente à la lecture :
      1. l'endpoint de liste ne filtre pas par défaut ;
      2. il enrichit chaque ligne du résident lié, sans quoi « résolu » ne dit
         pas à QUI ;
      3. l'écran d'administration propose le statut « résolu » au filtrage.
    """
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[2]
    #  🔴 `acces.py` est devenu un PAQUET le 06/09/2026 (#805). Le contrôle lit
    #  tous ses modules : il cherchait un fichier, il cherche un domaine.
    paquet = racine / "api" / "app" / "routers" / "acces"
    fichiers = sorted(paquet.glob("*.py"))
    assert fichiers, f"{paquet} ne porte aucun module : le contrôle ne peut pas conclure"
    acces = "\n".join(f.read_text(encoding="utf-8") for f in fichiers)

    assert "statut: str = Query(None)" in acces, (
        "Le filtre de statut n'est plus optionnel : le CS risque de ne plus voir "
        "l'ensemble des imports d'un coup d'œil."
    )
    assert '"proprietaire"' in acces, (
        "Les lignes ne sont plus enrichies du résident lié : « résolu » ne dit "
        "plus à qui le badge a été attribué."
    )

    #  L’écran a quitté sa route le 19/08/2026 : les sept écrans autonomes de
    #  l’administration sont devenus des ONGLETS de `admin/+page.svelte`, pour
    #  qu’on n’en sorte plus (donc plus de bouton « ← Retour »).
    #
    #  Puis il a FUSIONNÉ avec celui des badges Vigik le 27/08/2026 (#453) : les
    #  deux étaient identiques à 87 %, et il n'y a plus qu'un écran piloté par un
    #  modèle. Le fichier a déménagé deux fois, la capacité vérifiée ici n'a pas
    #  bougé — et c'est bien ce que ce test doit continuer de dire.
    #
    #  ⚠️ Ce test lit un fichier PAR SON CHEMIN : il a échoué en `FileNotFoundError`
    #  au moment de la fusion, ce qui est la bonne façon d'échouer. Un contrôle qui
    #  aurait cherché le filtre « ailleurs dans le front » serait resté vert sur un
    #  écran disparu.
    ecran = (
        racine / "front" / "src" / "lib" / "components" / "OngletImportAcces.svelte"
    ).read_text(encoding="utf-8")
    assert "'resolu'" in ecran, (
        "L'écran d'import ne propose plus le filtre « résolu » : les appariements "
        "automatiques deviennent invisibles à la revue du CS."
    )
