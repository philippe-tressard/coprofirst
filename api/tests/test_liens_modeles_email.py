"""Les URL écrites dans les MODÈLES d'e-mail mènent quelque part.

## Le trou que ce test bouche (11/09/2026, demandé à l'écran)

`test_liens_front.py` vérifie les liens que le code Python **fabrique**
(`lien_element`, `lien=`, `lien_path=`). Il ne voit pas ceux qui sont écrits
**dans le HTML des modèles** — des chaînes de `app/seed/emails/*.py` que rien ne
relisait. C'est par là qu'est passé le défaut signalé : un bouton « Consulter le
ticket » pointant sur `https://5hostachy.fr//tickets/34`, **404**.

La cause de celui-là était ailleurs (`site_url` non normalisé, cf.
`test_base_site.py`) — mais personne ne pouvait le savoir, puisque **aucun
contrôle ne regardait les liens des e-mails**. Un e-mail part chez le syndic, un
prestataire, un résident : c'est le seul endroit du produit où un lien mort ne se
corrige pas après coup.

## Ce qu'il vérifie, et pourquoi chaque règle

| Règle | Ce qu'elle évite |
|---|---|
| le lien est **absolu** | un `/tickets/34` dans un e-mail n'ouvre rien : il n'y a pas de page courante |
| pas de **double barre** | exactement le 404 signalé |
| le chemin **existe côté front** | le défaut de 2026-07 (`/documents`), qui n'a jamais existé — tenu par `test_liens_front.py::test_les_liens_ecrits_dans_les_modeles_email_existent`, qui lit les mêmes liens dans les modèles rendus |
| pas de **domaine en dur** | une adresse figée survit au changement de nom de domaine, et pointe alors chez quelqu'un d'autre |

⚠️ Une variable de lien (`{{ reponse.lien }}`) est **déclarée** avec l'endroit qui
la remplit. Le test ne peut pas la suivre tout seul — mais il peut exiger qu'elle
soit nommée, et qu'à cet endroit-là une URL absolue soit construite. Une variable
non déclarée échoue : c'est la seule façon d'empêcher qu'un futur modèle emporte
un chemin nu sans que personne le voie.

Chaque règle est UN contrôle qui balaie tous les liens et nomme tous ses écarts
d'un coup — pas un test par lien, qui s'arrêterait sur le premier cas et
noierait le rapport sous soixante lignes vertes.

Les adresses viennent de `aides_liens_email` (#1496), qui lit les modèles
COMPOSÉS : ce fichier relisait les sources, et avait dû apprendre la forme
`bouton(…)` après la factorisation #959 — un voisin ne l'avait pas apprise, et
ne voyait plus aucun bouton. Une extraction, trois contrôles.
"""

from __future__ import annotations

import pathlib
import re

from tests.aides_liens_email import BASE, liens_des_modeles_email

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Les variables de lien employées sans `{{ app.url }}`, et le fichier qui les
#: remplit — il DOIT y construire une URL absolue.
#:
#: 🔴 Déclarer ne suffit pas : `test_les_variables_de_lien_sont_ABSOLUES` ouvre
#: chacun de ces fichiers et exige qu'une base de site y soit concaténée. Sans
#: cela, cette table serait une liste de dérogations, c'est-à-dire un endroit où
#: ranger les défauts.
VARIABLES_ABSOLUES = {
    "{{ lien }}": "routers/auth.py",
    "{{ idee.lien }}": "utils/reponses.py",
    "{{ reponse.lien }}": "utils/reponses.py",
}


def test_il_y_a_bien_des_liens_a_verifier():
    """⚠️ Le cas zéro (`standards/04` §2). Si l'extraction cesse de fonctionner —
    les modèles déplacés, le HTML réécrit autrement —, tous les contrôles de ce
    fichier passeraient au vert en ne mesurant rien. Le plancher vit dans l'aide
    (`PLANCHER_LIENS`) : on l'y exerce, et on exige qu'elle voie les BOUTONS —
    ce que la lecture des sources a cessé de faire à la factorisation #959."""
    liens = liens_des_modeles_email()
    assert any(lien.adresse == f"{BASE}/calendrier" for lien in liens), (
        "le bouton de `calendrier_evenement_cree` n'est plus extrait — les ancres "
        "composées par `fragments.bouton()` échappent à l'extraction"
    )


def test_chaque_lien_de_modele_est_absolu():
    """Un chemin nu dans un e-mail n'ouvre rien : il n'y a pas de page courante."""
    fautifs = [
        f"  {lien.modele} : « {lien.adresse} »"
        for lien in liens_des_modeles_email()
        if not lien.adresse.startswith(("mailto:", BASE)) and lien.adresse not in VARIABLES_ABSOLUES
    ]
    assert not fautifs, (
        f"Liens ni préfixés par `{BASE}` ni déclarés dans VARIABLES_ABSOLUES avec le "
        "fichier qui les remplit :\n" + "\n".join(fautifs)
    )


def test_aucun_lien_ne_porte_de_double_barre():
    """Le défaut signalé : `{{ app.url }}` vaut déjà `https://…` sans barre
    finale (`utils/liens.base_site`) ; en écrire une seconde ici la ramènerait."""
    fautifs = []
    for lien in liens_des_modeles_email():
        adresse = lien.adresse
        apres = adresse[len(BASE) :] if adresse.startswith(BASE) else adresse
        if "//" in apres:
            fautifs.append(f"  {lien.modele} : « {adresse} »")
    assert not fautifs, "Double barre dans le chemin :\n" + "\n".join(fautifs)


def test_aucun_domaine_ecrit_en_dur():
    """Une adresse figée survit au changement de nom de domaine, et pointe alors
    chez quelqu'un d'autre — un e-mail déjà parti ne se corrige pas."""
    fautifs = [
        f"  {lien.modele} : « {lien.adresse} »"
        for lien in liens_des_modeles_email()
        if re.match(r"https?://", lien.adresse)
    ]
    assert not fautifs, f"Domaine écrit en dur — employer `{BASE}` :\n" + "\n".join(fautifs)


def test_les_variables_de_lien_sont_ABSOLUES_a_leur_point_d_appel():
    """🔴 Déclarer une variable ne la rend pas absolue. On ouvre le fichier qui
    la remplit et on exige qu'une base de site y soit concaténée."""
    fautifs = []
    for variable, fichier in VARIABLES_ABSOLUES.items():
        f = APP / fichier
        if not f.exists():
            fautifs.append(f"{variable} → {fichier} : le fichier a disparu")
            continue
        src = f.read_text(encoding="utf-8")
        if "adresse_du_site(" not in src:
            fautifs.append(
                f"{variable} → {fichier} : aucune base de site n'y est construite, "
                "le lien partirait en chemin nu"
            )
    assert not fautifs, "Variables de lien non absolues :\n  " + "\n  ".join(fautifs)
