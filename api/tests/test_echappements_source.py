r"""Le français du source s'écrit en clair, jamais en séquences d'échappement.

## Le défaut, tel qu'il était

Le 02/09/2026, **249 séquences `\uXXXX`** dormaient dans 15 fichiers versionnés —
modèles d'e-mail, contenus envoyés en WhatsApp, messages d'erreur rendus à
l'écran, séparateurs de section, docstrings. On y lisait, en toutes lettres :

    'Catégorie : {{ item.categorie }} · Priorité : …'
    raise HTTPException(403, "Vous n'êtes pas associé à ce lot.")

Python et JavaScript les décodent : **rien n'était cassé à l'exécution**. C'est
précisément ce qui rend le défaut durable — aucun test ne pouvait le trouver par
son effet, et il n'a aucun symptôme.

## Ce qu'il coûte

Le seul contrôle qui existe sur un texte envoyé aux résidents est **la
relecture**. Un libellé faux, un lien mort, une faute dans un modèle d'e-mail ne
se voient qu'à l'œil. Un texte écrit en séquences n'est pas relu : il est sauté.
Et la même écriture a déjà produit un défaut **fonctionnel** ici — un `\b` dans
un littéral de gabarit, qui a rendu `lint:titres` incapable de mesurer quoi que
ce soit depuis son écriture.

⚠️ Ces séquences ne viennent pas d'une frappe : elles viennent d'un outillage qui
écrit du source (`ascii()`, `json.dumps` sans `ensure_ascii=False`, un heredoc
qui avale les antislashs). C'est pourquoi une consigne ne suffit pas — la main
qui écrit le fichier ne les voit pas non plus.

## La règle, et pourquoi elle a exactement cette frontière

**Un caractère qu'on peut lire s'écrit en clair. Un caractère qu'on ne peut pas
voir reste échappé.** La frontière est la CATÉGORIE Unicode, jamais une liste :

- `Zs` (espaces insécables) : les écrire en clair les rendrait indiscernables
  d'une espace ordinaire, et la typographie française en dépend ;
- `Mn` (accents combinants, sélecteur de variante) : invisibles isolément, et
  employés ici dans des classes de regex où la forme échappée est la seule
  lisible ;
- `Cc` / `Cf` / `Cs` : non imprimables par définition.

Tout le reste — lettres accentuées, tirets, apostrophes, symboles — est visible,
donc s'écrit visiblement.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

BS = chr(92)

RACINE = Path(__file__).resolve().parents[2]

#: Où le source vit. `scripts/` en fait partie : le défaut y était aussi
#: (`setup-rpi5.sh`), et un contrôle qui ne regarde que `api/` aurait été vert
#: sur un dépôt fautif — « la portée du contrôle fait partie du contrôle ».
ARBRES = ("api", "front/src", "front/scripts", "scripts")
SUFFIXES = (".py", ".ts", ".svelte", ".mjs", ".js", ".sh")
IGNORES = ("node_modules", ".svelte-kit", "__pycache__", "build", "dist")

#: 🔴 AUCUNE EXCEPTION, et ce n'est pas un oubli.
#:
#: La première rédaction en déclarait trois — les fichiers qui PARLENT du
#: défaut et doivent donc le citer. Le contrôle les a refusées : un fichier qui
#: montre la séquence l'écrit forcément avec DEUX antislashs, et le motif
#: ci-dessous ne compte que les séquences réelles. L'exception était superflue
#: avant d'exister.
#:
#: C'est la bonne façon de ne pas avoir de liste : une frontière qui rend
#: l'exception inutile, jamais une liste qu'on cesse de relire.

#: Une séquence réelle : précédée d'un nombre PAIR d'antislashs. Sans cette
#: garde, un antislash littéral suivi de `u2014` serait compté à tort — et trois
#: occurrences de cette forme existent, dans les tests qui parlent du sujet.
_SEQUENCE = re.compile(r"(?<!\\)(?:\\\\)*\\u([0-9a-fA-F]{4})")

#: Les emoji hors du plan de base — `\\U0001f4c5`, huit chiffres — sont couverts
#: depuis le 03/09/2026 (#734) : 73 séquences réécrites en clair dans 18 fichiers
#: vivants, avec la même preuve d'équivalence par AST.
_EMOJI = re.compile(r"(?<!\\)(?:\\\\)*\\U000([0-9a-fA-F]{5})")


def _visible(point: str) -> bool:
    """Un caractère imprimable, qui a donc sa place en clair dans le source."""
    return unicodedata.category(chr(int(point, 16)))[0] not in "ZMC"


def _fichiers():
    for arbre in ARBRES:
        base = RACINE / arbre
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.suffix not in SUFFIXES:
                continue
            if any(part in IGNORES for part in f.parts):
                continue
            yield f


def lignes_fautives(texte: str, court: str = "<texte>") -> list[str]:
    """La décision, PURE : ce qu'un contenu porte de fautif.

    Séparée de la lecture des fichiers exprès — c'est le seul moyen de
    l'éprouver sur un contenu connu, sans écrire sur le disque. Le dépôt a déjà
    payé l'inverse : « je testais la décision, pas le tuyau qui la nourrit ».
    """
    trouves = []
    for ligne_no, ligne in enumerate(texte.splitlines(), 1):
        for m in _SEQUENCE.finditer(ligne):
            if _visible(m.group(1)):
                c = chr(int(m.group(1), 16))
                trouves.append(f"  {court}:{ligne_no} — la lettre « {c} » écrite en séquence")
        for m in _EMOJI.finditer(ligne):
            c = chr(int(m.group(1), 16))
            trouves.append(f"  {court}:{ligne_no} — l'emoji « {c} » écrit en séquence")
    return trouves


def _releve() -> dict[str, list[str]]:
    """Chemin relatif POSIX -> lignes fautives, fichier par fichier."""
    par_fichier: dict[str, list[str]] = {}
    for f in _fichiers():
        court = f.relative_to(RACINE).as_posix()
        fautes = lignes_fautives(f.read_text(encoding="utf-8", errors="replace"), court)
        if fautes:
            par_fichier[court] = fautes
    return par_fichier


def test_aucune_lettre_francaise_ecrite_en_sequence_d_echappement():
    fautifs = [x for lignes in _releve().values() for x in lignes]
    assert not fautifs, (
        f"{len(fautifs)} séquence(s) d'échappement pour des caractères "
        "IMPRIMABLES :\n"
        + "\n".join(fautifs[:40])
        + "\n\nCe texte ne sera pas relu, donc pas vérifié. L'écrire en clair.\n"
        "Si l'outil qui produit le fichier échappe tout seul : "
        "`json.dumps(..., ensure_ascii=False)`, et jamais `ascii()`."
    )


def test_le_controle_regarde_bien_quelque_chose():
    """Cas zéro. Un scan qui ne lit aucun fichier rend la même liste vide.

    C'est la seule façon de distinguer « rien trouvé » de « rien lu » — le faux
    vert que ce dépôt a produit assez de fois pour en faire une règle.
    """
    fichiers = list(_fichiers())
    assert len(fichiers) > 400, (
        f"seulement {len(fichiers)} fichier(s) examiné(s) : le scan ne voit "
        "presque rien, et son verdict ne vaut rien."
    )
    #  Et la décision doit voir une faute quand il y en a une, sans se laisser
    #  prendre par un antislash littéral ni par un invisible légitime.
    assert lignes_fautives("Cat" + BS + "u00e9gorie") != []
    assert lignes_fautives("un antislash " + BS + BS + "u2014 littéral") == []
    assert lignes_fautives("Article" + BS + "u00a0: 3") == []
    assert lignes_fautives("Date " + BS + "U0001f4c5") != []
    assert lignes_fautives("Date " + BS + "U0001f4c5", "api/alembic/versions/x.py") != []


def test_les_invisibles_restent_autorises():
    """L'exception de catégorie est vérifiée, pas supposée.

    Si `_visible` se mettait à refuser l'insécable, 71 lignes de typographie
    française deviendraient fautives d'un coup — et la tentation serait de les
    « corriger » en espaces ordinaires, ce qui casserait le rendu.
    """
    for point in ("00a0", "202f", "0300", "fe0f"):
        assert not _visible(point), point + " devrait rester échappé"
    for point in ("00e9", "2014", "2019", "2500", "20ac"):
        assert _visible(point), point + " devrait s'écrire en clair"


# ── VOLET 2 : le texte ABÎMÉ par un double encodage ─────────────────────────
#
#  Même famille, même porte : un texte qui ne se lit pas n'est pas relu.
#
#  🔴 Relevé le 18/09/2026 : **213 lignes** dans huit fichiers, dont trente dans
#  `routers/idees.py` et dix-huit dans `auth/deps.py` — le module de sécurité
#  central, celui dont les docstrings expliquent QUI a le droit de quoi. On y
#  lisait, en toutes lettres, une phrase où chaque accent était remplacé par deux
#  caractères sans rapport.
#
#  D'où ça vient : un fichier UTF-8 relu en latin-1 — ou en cp1252, qui donne une
#  troisième forme encore —, puis réécrit en UTF-8. Aucun outil ne s'en plaint,
#  Python compile, les tests passent, et le texte devient illisible pour la seule
#  chose qui le vérifie : un œil.
#
#  ⚠️ La réparation se fait par ALLER-RETOUR (réencoder en latin-1 ou cp1252,
#  relire en UTF-8), et il faut parfois l'appliquer deux fois : le dépôt portait
#  des lignes encodées DEUX fois, et d'autres mêlant du sain et de l'abîmé —
#  qu'il faut alors défaire séquence par séquence, et non ligne par ligne.

#: Les têtes de séquence UTF-8 vues comme des caractères d'une table 8 bits,
#: suivies de leurs continuations. Écrites EN CLAIR : c'est la règle de ce
#: fichier, et elle vaut pour son propre code.
_DOUBLE_ENCODAGE = re.compile(
    "[ÃÂ][-¿]"  # Ã©  Â»   texte relu en latin-1
    "|â[-]"  # â      un tiret cadratin
    "|ð"  # ð        un emoji déplié
    "|â[€”†]"  # â€ â” â†  texte relu en cp1252
    "|Ã‰"  # Ã‰       idem, sur une capitale
)

#: Les fichiers qui MONTRENT le défaut, exprès. Le contrôle échoue si l'un d'eux
#: cesse d'en porter un : une exception sans objet se retire.
MONTRENT_LE_DEFAUT = {
    "api/app/routers/acces/parc.py": "explique pourquoi l'export CSV porte un BOM",
    "api/tests/test_export_parc_acces.py": "le test de ce même BOM",
    "api/tests/test_echappements_source.py": "ce fichier-ci, qui en porte le motif",
}


def _releve_abime() -> dict[str, list[int]]:
    """Chemin relatif POSIX -> numéros de lignes abîmées."""
    par_fichier: dict[str, list[int]] = {}
    for f in _fichiers():
        court = f.relative_to(RACINE).as_posix()
        if court in MONTRENT_LE_DEFAUT:
            continue
        lignes = [
            n
            for n, ligne in enumerate(
                f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            )
            if _DOUBLE_ENCODAGE.search(ligne)
        ]
        if lignes:
            par_fichier[court] = lignes
    return par_fichier


def test_aucun_texte_abime_par_un_double_encodage():
    fautifs = _releve_abime()
    assert not fautifs, (
        f"{sum(len(v) for v in fautifs.values())} ligne(s) de texte abîmé "
        f"dans {len(fautifs)} fichier(s) :\n"
        + "\n".join(f"  {f} : lignes {v[:8]}" for f, v in fautifs.items())
        + "\n\nCe texte ne sera pas relu, donc pas vérifié. Réparer par "
        "aller-retour : réencoder la ligne en latin-1 (ou cp1252 si cela "
        "échoue), la relire en UTF-8, et recommencer tant que ça change."
    )


def test_le_motif_reconnait_un_texte_abime_et_epargne_le_francais():
    """Le cas zéro : sans lui, le test ci-dessus serait vert sur n'importe quoi."""
    #  Construits par point de code pour que la démonstration ne dépende pas de
    #  l'encodage de CE fichier — c'est la seule chose qu'on ne peut pas écrire
    #  en clair sans se contredire.
    abime_latin1 = "cat" + chr(0x00C3) + chr(0x00A9) + "gorie"
    abime_cp1252 = "consulte " + chr(0x00E2) + chr(0x20AC) + chr(0x201D) + " 403"
    assert _DOUBLE_ENCODAGE.search(abime_latin1)
    assert _DOUBLE_ENCODAGE.search(abime_cp1252)
    #  Et du français SAIN ne déclenche rien — c'est la moitié qui compte.
    assert not _DOUBLE_ENCODAGE.search("Un compte EXTERNE — il consulte (lève 403)")
    assert not _DOUBLE_ENCODAGE.search("catégorie · priorité « haute » 🔴")
    assert not _DOUBLE_ENCODAGE.search("")


def test_les_demonstrations_montrent_encore_le_defaut():
    """Une exception qui ne sert plus se retire (`standards/04`)."""
    for court, raison in MONTRENT_LE_DEFAUT.items():
        chemin = RACINE / court
        assert chemin.exists(), f"{court} ({raison}) n'existe plus"
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        assert _DOUBLE_ENCODAGE.search(texte), (
            f"{court} ne montre plus de texte abîmé ({raison}) — "
            "retirer son entrée de MONTRENT_LE_DEFAUT."
        )
