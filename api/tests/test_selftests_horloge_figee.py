"""Un self-test ne mesure pas une durée à 5 s près sur l'horloge réelle (#2236).

`scripts/lib/lib-apt.sh --selftest` posait `now=$(date +%s)`, faisait dire à un
`systemctl` simulé « démarré il y a 36000 s », puis exigeait `36000 ≤ âge ≤ 36005`.
Seul sur un poste calme : 50 PASS. Sous un rejeu complet en couloirs parallèles,
la collecte réelle dépassait la fenêtre — un rouge sur deux rejeux de suite, cinq à
dix minutes perdues à chaque fois, pour un lot qui n'y touchait pas.

Une assertion dont la valeur dépend du temps qui passe est un contrôle qui ment
selon la charge de la machine (`standards/04`). Le remède est de **figer** l'horloge
— une fonction `date` simulée dans le test — et d'asserter l'égalité ; élargir la
fenêtre ne fait que déplacer la charge qui la dépasse.

Ce test lit les self-tests des scripts et refuse les deux formes de la fenêtre
étroite : une durée `…_s` bornée par moins de 100 s, et un couple `-ge X … -le Y`
qui encadre une durée de moins de 60 s.
"""

import re

from tests.conftest import racine_depot, scripts_shell_versionnes

RACINE = racine_depot()

#: Une durée en secondes (champ `…_s`) bornée par un petit nombre : `-le 5`.
BORNE_PETITE = re.compile(r'_s\)?"? +-(?:le|lt) +\d{1,2}\b')
#: Un encadrement `[ "$a" -ge X ] && [ "$a" -le Y ]`.
ENCADREMENT = re.compile(r'-ge +(\d+) *\] *&& *\[ *"[^"]*" +-le +(\d+)')
LARGEUR_MINIMALE_S = 60

#: Fenêtres étroites déclarées, chacune avec sa raison. Ne fait que baisser.
DECLAREES: dict[str, str] = {}


def fenetres_etroites(texte: str) -> list[tuple[int, str]]:
    """(n° de ligne, ligne) des assertions `t "…"` qui encadrent un temps de trop près."""
    trouvees = []
    for n, ligne in enumerate(texte.splitlines(), start=1):
        if 't "' not in ligne or ligne.lstrip().startswith("#"):
            continue
        etroite = bool(BORNE_PETITE.search(ligne))
        for bas, haut in ENCADREMENT.findall(ligne):
            etroite = etroite or int(haut) - int(bas) < LARGEUR_MINIMALE_S
        if etroite:
            trouvees.append((n, ligne.strip()))
    return trouvees


def test_le_detecteur_voit_la_fenetre_etroite_et_laisse_le_reste():
    """Cas zéro : les deux formes du défaut, et ce qui ne doit pas être refusé."""
    etroite_bornee = (
        """t "vu à l'instant" oui eval '[ "$(champ apt_secu_vu_s)" -le 5 ] && echo oui'"""
    )
    etroite_encadree = (
        """t "début du passage" oui eval 'a=$(champ apt_passage_s); """
        """[ "$a" -ge 36000 ] && [ "$a" -le 36005 ] && echo oui'"""
    )
    assert fenetres_etroites(etroite_bornee)
    assert fenetres_etroites(etroite_encadree)

    # Horloge figée : l'égalité ne dépend pas de la charge.
    assert not fenetres_etroites("""t "vu à l'instant" 0 champ apt_secu_vu_s""")
    # Une fenêtre large (la minute) laisse la marge qu'il faut.
    assert not fenetres_etroites(
        """t "ancien" oui eval '[ "$a" -ge 36000 ] && [ "$a" -le 36300 ] && echo oui'"""
    )
    # Un compte n'est pas une durée : `-le 3` sans `_s` ne dit rien du temps.
    assert not fenetres_etroites(
        """t "trois lignes" oui eval '[ "$(wc -l < f)" -le 3 ] && echo oui'"""
    )
    # Un commentaire qui cite l'ancienne forme n'est pas une assertion.
    assert not fenetres_etroites("""    # t "x" eval '[ "$(champ y_s)" -le 5 ]'""")


def test_aucun_self_test_ne_mesure_une_duree_sur_l_horloge_reelle_a_quelques_secondes():
    fautifs = []
    for chemin in scripts_shell_versionnes():
        relatif = chemin.relative_to(RACINE).as_posix()
        for n, ligne in fenetres_etroites(chemin.read_text(encoding="utf-8")):
            if f"{relatif}:{n}" in DECLAREES:
                continue
            fautifs.append(f"{relatif}:{n}  {ligne[:110]}")
    assert not fautifs, (
        "Assertion à fenêtre étroite sur une durée : sous charge elle échoue au hasard. "
        "Figer l'horloge (`date() { echo \"$MAINTENANT\"; }`) et asserter l'égalité :\n"
        + "\n".join(fautifs)
    )


def test_une_fenetre_declaree_sert_encore():
    """Une exception qui ne sert plus fait échouer : la liste ne fait que baisser."""
    vues = {
        f"{chemin.relative_to(RACINE).as_posix()}:{n}"
        for chemin in scripts_shell_versionnes()
        for n, _ in fenetres_etroites(chemin.read_text(encoding="utf-8"))
    }
    assert set(DECLAREES) <= vues, f"déclarée mais absente : {sorted(set(DECLAREES) - vues)}"
