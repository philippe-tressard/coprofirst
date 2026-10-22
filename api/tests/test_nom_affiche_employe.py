"""Le nom d'une personne passe par `nom_affiche` — la règle est-elle EMPLOYÉE ?

## 🔴 Le trou que ce fichier bouche (14/09/2026, #779)

La règle « Prénom NOM », arbitrée à l'écran le 31/08/2026, avait déjà :

* son implémentation unique (`app/utils/noms.nom_affiche`) ;
* son pendant côté front (`front/src/lib/noms.ts`) ;
* et un contrôle — `npm run lint:noms` — qui vérifie que **les deux
  implémentations donnent le même résultat**.

Il manquait exactement ce qui compte : **que quelqu'un s'en serve**. Rien ne
regardait les points d'APPEL. L'écran de télémétrie composait donc le nom à la
main, `f"{prenom} {nom}"`, en **trois** endroits — et affichait « Jean-Baptiste
ForT » là où tout le reste du site écrit « Jean-Baptiste FORT ». Une
notification d'accès faisait de même.

⚠️ C'est le motif que ce dépôt connaît le mieux, sous une forme nouvelle : le
contrôle existait, il mesurait la bonne chose, mais pas au bon endroit. Vérifier
que deux implémentations concordent ne dit rien de ce qui les contourne — c'est
« la portée du contrôle fait partie du contrôle » (`standards/05` §9).
"""

import re
from pathlib import Path

from tests.aides_sources import modules_app

APP = Path(__file__).resolve().parents[1] / "app"

#: Le motif d'une composition MANUELLE : un prénom et un nom interpolés à la
#: suite dans la même f-string.
#:
#: ⚠️ On ne cherche pas `nom` seul : il apparaît partout, et un contrôle qui crie
#: sur du code juste se fait désarmer (leçon du 14/09, même journée).
#:
#: ⚠️ Le préfixe est FACULTATIF : `{prenom} {nom}` s'écrit aussi sans objet
#: porteur, et la première version du motif l'exigeait — elle laissait donc
#: passer la forme la plus courte. Son cas zéro l'a dit tout de suite.
#:
#: 🔴 La seconde forme — un tuple JOINT — est celle du point CS / Syndic
#: (17/10/2026) : `" ".join(x for x in (p.prenom, p.nom) if x)`. Le motif ne
#: connaissait que la f-string, et le compte rendu rendait les noms tels que tapés.
_COMPOSITION = re.compile(
    r"\{[\w.]*prenom[^}]*\}\s*\{[\w.]*nom\b[^}]*\}"
    r"|join\([^)]*[(\[]\s*[\w.]*prenom\s*,\s*[\w.]*\bnom\s*[)\]]"
)

#: Les endroits où composer le nom à la main est JUSTE, avec leur raison.
#:
#: ⚠️ Une exception qui ne sert plus fait échouer ce test : une tolérance qui
#: survit à son objet finit par en couvrir une qui compte.
#: (Vide depuis #2153 : le rapprochement d'un bailleur à ses locataires ne lit plus
#: que son NOM, sans composer « prénom nom ».)
EXCEPTIONS: dict[str, str] = {}


def test_le_motif_reconnait_ce_quil_doit_reconnaitre():
    """🔴 Cas zéro du MOTIF : sans lui, le test passe en ne trouvant jamais rien.

    Les quatre premières formes sont celles réellement rencontrées dans ce dépôt
    le 14/09/2026 ; les deux dernières ne doivent PAS être prises.
    """
    assert _COMPOSITION.search('f"{user.prenom} {user.nom}"')
    assert _COMPOSITION.search('f"{u[1]} {u[2]}"') is None  # trop générique : hors portée
    assert _COMPOSITION.search('f"{prenom} {nom}"')
    assert _COMPOSITION.search('f"{user.prenom} {user.nom} — lot {n}"')
    assert _COMPOSITION.search('{"nom": u.nom, "prenom": u.prenom}') is None
    assert _COMPOSITION.search('f"{destinataire.prenom}"') is None
    assert _COMPOSITION.search('" ".join(x for x in (p.prenom, p.nom) if x)')
    assert _COMPOSITION.search("nom_affiche(p.prenom, p.nom)") is None


def test_aucune_composition_manuelle_du_nom():
    fautifs = []
    for m in modules_app():
        rel = m.rel
        if rel == "utils/noms.py":
            continue  # c'est le module qui PORTE la règle
        for numero, ligne in enumerate(m.lignes, 1):
            nue = ligne.strip()
            #  Les commentaires et docstrings racontent l'incident : les compter
            #  interdirait de l'expliquer.
            if nue.startswith("#") or nue.startswith("*") or "`" in ligne:
                continue
            if _COMPOSITION.search(ligne) and rel not in EXCEPTIONS:
                fautifs.append(f"{rel}:{numero}")
    assert not fautifs, (
        "Le nom est composé à la main :\n  "
        + "\n  ".join(fautifs)
        + "\n→ `nom_affiche(prenom, nom)` (`app.utils.noms`) — la casse du nom est "
        "une règle arbitrée, pas un détail de mise en forme."
    )


def test_chaque_exception_sert_encore():
    inutiles = []
    for rel, raison in EXCEPTIONS.items():
        chemin = APP / rel
        if not chemin.is_file():
            inutiles.append(f"{rel} (fichier absent)")
            continue
        if not _COMPOSITION.search(chemin.read_text(encoding="utf-8")):
            inutiles.append(f"{rel} (ne compose plus de nom) — {raison}")
    assert not inutiles, f"Exceptions devenues inutiles : {inutiles}"


#: Les fichiers qui LISENT le prénom et le nom d'un utilisateur sans les
#: afficher — avec leur raison.
EXCEPTIONS_LECTURE = {
    "routers/bailleur/baux.py": "rapprochement, pas affichage (voir ci-dessus)",
    "routers/acces/commun.py": "rend le prénom et le nom SÉPARÉMENT au client, qui compose lui-même — "
    "le front a sa propre `nomAffiche`, éprouvée identique par `lint:noms`.",
}


def test_lire_un_prenom_et_un_nom_oblige_a_employer_la_regle():
    """🔴 LE CONTRÔLE QUI AURAIT ATTRAPÉ LE DÉFAUT DU 14/09.

    Le test précédent cherche un prénom et un nom interpolés à la suite. La
    télémétrie, elle, écrivait les COLONNES d'un tuple — sans nommer les
    champs. Aucun motif textuel ne peut distinguer cela d'une interpolation
    quelconque, et vouloir l'essayer donnerait des faux positifs partout.

    On regarde donc l'autre bout : un module qui va CHERCHER
    `Utilisateur.prenom` en base a l'intention d'en faire quelque chose. S'il
    ne cite jamais `nom_affiche`, soit il compose le nom lui-même, soit il le
    transmet — et il doit alors le dire.

    ⚠️ Vérifié en réintroduisant le défaut : sans cette fonction, le fichier
    passait au VERT sur la version fautive. Un contrôle qui n'attrape pas
    l'incident qui l'a fait naître est un contrôle à compléter, pas à garder.
    """
    fautifs = []
    for m in modules_app():
        rel = m.rel
        if rel == "utils/noms.py" or rel in EXCEPTIONS_LECTURE:
            continue
        source = m.source
        if "Utilisateur.prenom" not in source:
            continue
        #  🔴 L'IMPORT, pas le mot : la première version cherchait
        #  « nom_affiche » n'importe où dans le fichier, et le trouvait dans le
        #  COMMENTAIRE qui explique la règle. Éprouvée en réintroduisant le
        #  défaut, elle restait verte. Troisième fois que ce dépôt l'apprend
        #  (`lint:html` comptait les mentions dans les commentaires).
        if "from app.utils.noms import" not in source or "nom_affiche" not in "".join(
            ligne for ligne in source.splitlines() if ligne.startswith("from app.utils.noms import")
        ):
            fautifs.append(rel)
    assert not fautifs, (
        "Ces modules lisent le prénom et le nom sans employer la règle "
        "d'affichage :\n  "
        + "\n  ".join(fautifs)
        + "\n→ `nom_affiche(prenom, nom)`, ou une entrée dans EXCEPTIONS_LECTURE "
        "qui dit pourquoi ils n'affichent pas."
    )


def test_chaque_exception_de_lecture_sert_encore():
    inutiles = []
    for rel, raison in EXCEPTIONS_LECTURE.items():
        chemin = APP / rel
        if not chemin.is_file():
            inutiles.append(f"{rel} (fichier absent)")
            continue
        if "prenom" not in chemin.read_text(encoding="utf-8"):
            inutiles.append(f"{rel} (ne lit plus de prénom) — {raison}")
    assert not inutiles, f"Exceptions de lecture devenues inutiles : {inutiles}"
