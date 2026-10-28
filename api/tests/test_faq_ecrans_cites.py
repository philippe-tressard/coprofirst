"""La FAQ ne cite que des écrans qui existent (#1037).

## Pourquoi ce contrôle

Le seed de la FAQ nommait **quatre** écrans renommés ou supprimés : la rubrique
« Gouvernance » (redirigée vers Résidence), la section « Historique de mes
tickets » (renommée « 🗂️ Archives » le 20/08/2026), le traitement des tickets
« dans l'Espace CS » (il se fait depuis la page Tickets), et une « messagerie »
qui n'a jamais existé.

🔴 **C'est le défaut le plus coûteux qu'une FAQ puisse porter** : elle est lue
*au moment où l'on ne sait pas*, donc par quelqu'un qui n'a aucun moyen de
corriger ce qu'il lit. Un résident qui suit le texte cherche un écran absent et
en conclut que c'est lui qui se trompe.

Rien ne le signalait : la FAQ vit en base, son seed est un fichier Python, et les
libellés d'écran vivent dans un fichier TypeScript. Aucun contrôle ne traversait
les deux.

## Ce que ce contrôle vérifie, et ce qu'il ne peut pas vérifier

**Il ne relit pas la FAQ servie** — elle est en base, et l'ouvrir depuis un
process tiers est interdit (règle d'or). Il lit le **seed**, c'est-à-dire ce que
toute installation neuve recevra, et ce que les migrations de correction
recopient.

Il n'essaie pas non plus de deviner tous les noms d'écran cités : un texte de
FAQ est de la prose, et une extraction générique produirait des faux positifs à
chaque phrase. Il refuse une **liste nommée de termes morts**, chacun daté avec
ce qui l'a remplacé — c'est un contrôle de non-régression, pas un analyseur.

⚠️ Ajouter un terme ici est le **geste qui accompagne un renommage d'écran** :
c'est ce qui empêche l'ancien nom de revenir dans un texte, un an plus tard, par
une reformulation faite de mémoire.
"""

from __future__ import annotations

import pathlib
import re

from app.seed.faq import FAQ_COMPLEMENTAIRE, FAQ_INITIALE

_API = pathlib.Path(__file__).resolve().parents[1] / "app"
_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"

#: Termes qui ne doivent plus apparaître dans un texte servi aux résidents,
#: avec ce qui les remplace. La clé est cherchée **sans** tenir compte de la
#: casse, mais telle quelle : un mot ordinaire n'y a pas sa place.
TERMES_MORTS = {
    "rubrique Gouvernance": "l'écran redirige vers /residence depuis #516 — dire « rubrique Résidence »",
    "Historique de mes tickets": "renommé « 🗂️ Archives » le 20/08/2026 (#516)",
    "messagerie": "il n'y a aucune messagerie dans le produit — citer documents ou calendrier",
    "Mon profil > Sécurité": "le bloc s'appelle « Modifier le mot de passe » (#1025)",
    "Admin → Patrimoine": "l'onglet s'appelle « Périmètres » (#1025)",
    "Signalements & tickets": "le libellé de la page est « Tickets » (pages.ts)",
    #  #1594 (v2.93.3) : deux réponses avaient gardé le mot du modèle.
    "commentaire de suivi": "la section s'appelle « Suivi », le geste « Ajouter une suite »",
    "section Saisi pour": "la section s'appelle « Au nom de » (#lib/entites/types.ts) ; "
    "« Saisi pour » est le champ",
}


def _motif(terme: str) -> re.Pattern[str]:
    """Le terme, les mots séparés par des blancs OU par une balise en ligne.

    La FAQ est du HTML : « section <strong>Saisi pour</strong> » se lit
    « section Saisi pour », et un motif littéral ne l'aurait jamais vu.
    """
    entre = r"(?:\s|</?\w+>)+"
    return re.compile(entre.join(map(re.escape, terme.split())), re.I)


def _textes_servis() -> dict[str, str]:
    """Les fichiers dont le contenu part vers un résident, par chemin lisible."""
    fichiers = {
        "seed/faq.py": _API / "seed" / "faq.py",
        "lib/pages.ts": _FRONT / "lib" / "pages.ts",
        "lib/pages-roles.ts": _FRONT / "lib" / "pages-roles.ts",
    }
    return {
        nom: chemin.read_text(encoding="utf-8")
        for nom, chemin in fichiers.items()
        if chemin.exists()
    }


def test_le_controle_lit_bien_les_textes():
    """Cas zéro de la portée : trois fichiers manquants se liraient « aucun écart »."""
    textes = _textes_servis()
    assert len(textes) == 3, (
        f"seulement {sorted(textes)} lu(s) — le contrôle a perdu sa portée "
        "(fichier déplacé ou renommé) et rendrait un vert sur rien"
    )
    assert "FAQ_INITIALE" in textes["seed/faq.py"], "le seed de la FAQ a changé de forme"


def test_aucun_ecran_mort_n_est_cite():
    """Le défaut exact : quatre écrans nommés qui n'existent plus sous ce nom."""
    fautes = []
    for nom, texte in _textes_servis().items():
        for terme, remede in TERMES_MORTS.items():
            for trouve in _motif(terme).finditer(texte):
                ligne = texte[: trouve.start()].count("\n") + 1
                fautes.append(f"  {nom}:{ligne} — « {terme} » : {remede}")

    assert not fautes, (
        "Des textes servis aux résidents citent un écran qui n'existe plus sous "
        "ce nom :\n" + "\n".join(fautes) + "\n\n"
        "Une FAQ est lue au moment où l'on ne sait pas : un nom d'écran faux y "
        "envoie chercher ce qui n'existe pas."
    )


def test_un_terme_mort_est_vu_a_travers_une_balise():
    """Le texte semé en v2.93.2 (#1594) : un motif littéral le laissait passer."""
    ancien = "Le formulaire porte alors une section <strong>Saisi pour</strong>, et"
    assert _motif("section Saisi pour").search(ancien)
    assert not _motif("section Saisi pour").search("une section <strong>Au nom de</strong>")


def test_la_question_du_prix_d_un_badge_existe_et_repond_a_son_lien():
    """🔴 Deux écrans renvoyaient vers une ancre morte.

    Les onglets Badges et Télécommandes de « Mes lots & accès » portent un lien
    `/faq#badge-prix`, et le manuel le documente. Le résolveur de la page FAQ
    (`estQuestionPrixBadge`, `#lib/faq`) cherche la question par **libellé** — l'identifiant
    variant d'une instance à l'autre. Or **aucune question du seed ne contenait
    « prix »** : le lien n'aboutissait que si le conseil syndical avait créé la
    question à la main.

    Le contrôle lit le motif **dans le résolveur**, il ne le recopie pas : deux
    expressions qui se recopient divergent au premier ajustement.
    """
    #  Le résolveur vit dans `#lib/faq` depuis le 26/09/2026 (#1329,
    #  `estQuestionPrixBadge`) : il était écrit dans la page.
    page = (_FRONT / "lib" / "faq.ts").read_text(encoding="utf-8")

    motif_lu = re.search(r"/([^/]+)/i\.test\(question\)", page)
    assert motif_lu, (
        "le résolveur de `#badge-prix` a changé de forme dans #lib/faq.ts : "
        "ce contrôle ne sait plus quel libellé la page attend"
    )
    motif = re.compile(motif_lu.group(1), re.I)

    #  Les DONNÉES du seed, pas son texte : une regex exigeait une catégorie écrite
    #  entre guillemets, et la constante `CATEGORIE_APPLICATION` (#1725) la rendait
    #  aveugle aux questions de cette rubrique.
    questions = [q for _, q, _, _ in (*FAQ_INITIALE, *FAQ_COMPLEMENTAIRE)]
    assert questions, "aucune question lue dans le seed — portée perdue"

    assert any(motif.search(q) for q in questions), (
        "Aucune question du seed ne satisfait le motif du résolveur "
        f"({motif_lu.group(1)}) : le lien `/faq#badge-prix` des onglets Badges et "
        "Télécommandes n'aboutit nulle part.\n"
        "Questions lues : " + ", ".join(questions[:5]) + "…"
    )


def test_le_lien_badge_prix_est_encore_appele():
    """Le pendant : si plus personne n'appelle l'ancre, la question n'a plus de raison.

    Une exception, une question ou un raccourci qui ne sert plus finit par être
    entretenu pour rien — ou pire, par masquer autre chose.
    """
    pages = (_FRONT / "lib" / "pages.ts").read_text(encoding="utf-8")
    assert "/faq#badge-prix" in pages, (
        "plus aucun descriptif n'appelle `/faq#badge-prix` : si le raccourci a "
        "été retiré, retirer aussi son résolveur dans #lib/faq et la "
        "vérification du test précédent"
    )
