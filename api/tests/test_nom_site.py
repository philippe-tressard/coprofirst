"""Le nom du site se lit par `nom_site()`, et le nom de CETTE copropriété n'est
écrit nulle part dans le code.

## 🔴 Ce que ce test empêche (14/09/2026, #779)

« 5Hostachy » était écrit **dix-sept fois** dans `api/app/`, en repli de
`site_nom`, plus une dix-huitième sous une autre valeur (« Ma Résidence », dans
le moteur d'envoi). Deux défauts, dont un silencieux :

1. **C'est un nom propre.** Le produit doit servir une autre copropriété — le
   dépôt le répète (« ni AFUL, ni quatre bâtiments »). Sa configuration vide, ses
   résidents auraient lu le nom de celle-ci en pied de courriel.
2. **Sept des dix-huit écritures ne se repliaient pas.** `cfg.get(cle, defaut)`
   ne rend le défaut que si la clé est **absente** : une `site_nom` présente et
   vide — ce qu'un champ de configuration effacé produit — passait telle quelle,
   et le courriel annonçait une résidence sans nom.

⚠️ La divergence était **invisible à la lecture** : les deux formes se
ressemblent, et chaque fichier était cohérent avec lui-même.
"""

import ast
import re
from pathlib import Path

import pytest

from app.utils.liens import NOM_SITE_PAR_DEFAUT, nom_site
from tests.aides_sources import chaines_du_code, modules_app

APP = Path(__file__).resolve().parents[1] / "app"

#: Le fichier qui a le droit de nommer le repli : celui qui le définit.
_SOURCE = APP / "utils" / "liens.py"


#: Ce qui a le droit d'écrire « hostachy » dans un littéral de `app/` :
#: chemin → (nombre exact d'occurrences, raison). Une exception qui cesse de
#: servir — ou qui sert davantage — fait échouer le contrôle.
#:
#: `utils/plateforme.py` n'y est plus depuis le 09/10/2026 (#1772) : le dépôt
#: porte le nom du logiciel, et son adresse ne nomme plus la résidence.
EXCEPTIONS_HOSTACHY: dict[str, tuple[int, str]] = {
    "utils/backup.py": (
        1,
        "`hostachy_backup_` : le préfixe des archives DÉJÀ sur disque, que la rotation "
        "et la restauration reconnaissent",
    ),
    "utils/whatsapp.py": (
        1,
        "`hostachy_whatsapp` : le nom du CONTENEUR du bridge (`container_name` du "
        "compose), l'une des deux adresses admises pour le joindre (#2151)",
    ),
}

#: Un nom de journal (`logging.getLogger("hostachy.llm")`) est un espace de noms
#: technique, jamais affiché : les filtres d'exploitation le lisent.
_NOM_DE_JOURNAL = re.compile(r"hostachy\.[a-z_]+")


def occurrences_hostachy(source: str) -> int:
    """Le nombre de littéraux de ce source qui écrivent « hostachy », en toute casse.

    Docstrings et commentaires exclus — ils racontent l'histoire et doivent
    pouvoir la nommer (la leçon de `lint:html`) —, noms de journal aussi. PURE.
    """
    return sum(
        1
        for n in chaines_du_code(ast.parse(source))
        if "hostachy" in n.value.casefold() and not _NOM_DE_JOURNAL.fullmatch(n.value)
    )


@pytest.mark.parametrize(
    "source,attendu",
    [
        ('X = "5Hostachy"\n', 1),
        #  🔴 Le motif d'origine — `"5Hostachy"` ENTRE GUILLEMETS — ne voyait aucun
        #  de ces trois-là, et les trois étaient dans le code le 07/10/2026 (#1725).
        ('footer = f"— Conseil Syndical 5Hostachy"\n', 1),
        ('titre = "Bienvenue — 5Hostachy"\n', 1),
        ('url = "5hostachy.fr"\n', 1),
        ('"""La docstring peut nommer 5Hostachy."""\n', 0),
        ("# un commentaire aussi : 5Hostachy\n", 0),
        ('logger = logging.getLogger("hostachy.llm")\n', 0),
        ('X = "rien à signaler"\n', 0),
    ],
)
def test_le_controle_reconnait_le_nom_ecrit(source, attendu):
    assert occurrences_hostachy(source) == attendu


def test_aucun_nom_de_copropriete_en_dur():
    """Le nom de cette copropriété ne s'écrit pas dans le code (#1725).

    Le nom de la RÉSIDENCE se lit dans la configuration (`nom_site`), celui de la
    PLATEFORME dans `utils/plateforme` — le logiciel s'appelle CoproFirst
    (`specs/architecture/multi-coproprietes.md`, D9).
    """
    fautes = []
    for m in modules_app():
        n = occurrences_hostachy(m.source)
        attendu = EXCEPTIONS_HOSTACHY.get(m.rel, (0, ""))[0]
        if n != attendu:
            fautes.append(f"{m.rel} : {n} littéral(aux), {attendu} déclaré(s)")
    assert not fautes, (
        "« hostachy » est écrit dans le code :\n  "
        + "\n  ".join(fautes)
        + "\n→ la résidence : `nom_site(cfg.get('site_nom'))` (`app.utils.liens`) ;"
        "\n  la plateforme : `app.utils.plateforme.NOM_PLATEFORME`."
        "\n  Une exception se déclare dans EXCEPTIONS_HOSTACHY, avec sa raison."
    )


def test_aucun_repli_de_nom_recopie():
    """Le repli lui-même ne se recopie pas — c'est ainsi qu'il a divergé."""
    fautifs = []
    for m in modules_app():
        if m.chemin == _SOURCE:
            continue
        for numero, ligne in enumerate(m.lignes, 1):
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            #  ⚠️ On vise le REPLI, pas la clé : `("site_nom", "site_url")` est une
            #  liste de clés à lire, et la première version du motif la comptait —
            #  dix faux positifs, tous légitimes. Un contrôle qui crie sur du code
            #  juste se fait désarmer.
            if re.search(r"""get\(\s*["']site_nom["']\s*,\s*["']""", ligne) or re.search(
                r"""get\(\s*["']site_nom["']\s*\)\s*or\s*["']""", ligne
            ):
                fautifs.append(f"{m.chemin.relative_to(APP)}:{numero}")
    assert not fautifs, (
        "Un repli de nom de site est recopié :\n  "
        + "\n  ".join(fautifs)
        + "\n→ `nom_site(...)` porte le repli, et lui seul."
    )


@pytest.mark.parametrize(
    "valeurs,attendu",
    [
        (("Les Quatre Saisons",), "Les Quatre Saisons"),
        #  L'espace de fin n'est pas une valeur différente — même règle que `base_site`.
        (("  Résidence du Parc  ",), "Résidence du Parc"),
        #  🔴 LE CAS QUI ÉTAIT FAUX SEPT FOIS : présente, et vide.
        (("",), NOM_SITE_PAR_DEFAUT),
        (("   ",), NOM_SITE_PAR_DEFAUT),
        ((None,), NOM_SITE_PAR_DEFAUT),
        ((), NOM_SITE_PAR_DEFAUT),
        #  La cascade : une configuration spécifique passe avant la générale.
        ((None, "Générale"), "Générale"),
        (("Spécifique", "Générale"), "Spécifique"),
        (("", "Générale"), "Générale"),
    ],
)
def test_nom_site(valeurs, attendu):
    assert nom_site(*valeurs) == attendu


def test_le_repli_ne_nomme_aucune_copropriete_reelle():
    """Un repli doit être NEUTRE : il s'affiche chez quelqu'un d'autre."""
    assert "hostachy" not in NOM_SITE_PAR_DEFAUT.lower()
