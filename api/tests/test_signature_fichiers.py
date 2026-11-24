"""Un fichier téléversé doit ÊTRE ce qu'il prétend être — à chaque point de réception.

## Le défaut (#773, audit du 05/09/2026)

Les documents n'étaient validés que par `file.content_type` : une chaîne
**envoyée par le client**, qu'un `curl` fixe librement. Un exécutable renommé
`.pdf` avec `Content-Type: application/pdf` était stocké, puis servi aux
résidents authentifiés.

Les **images**, elles, étaient réellement vérifiées — PIL les ouvre. Le même
produit avait donc deux niveaux d'exigence pour la même question, et personne ne
pouvait le voir : les deux chemins vivaient dans le même fichier, à trente
lignes d'écart.

## Pourquoi ce test regarde AUSSI la portée

La règle ne vaut que si **chaque** point de réception l'APPELLE : toute route
déclarée qui reçoit un `UploadFile` (`points_de_reception`, relevés sur les
routes, jamais une liste recopiée — #2912). Une règle centralisée qu'un seul
appelant emploie ne protège qu'un seul chemin, et donne l'illusion de tous
(`standards/03` §1).

Qu'aucun routeur n'écrive un fichier reçu hors de `utils/fichiers.py` est tenu
par `test_televersement_source_unique.py`, seul détecteur des écritures sur
disque : ce fichier-ci en portait un second, dont le motif ne trouvait plus rien
depuis la factorisation (#1026) — un vert à vide, retiré le 30/09/2026.
"""

from __future__ import annotations

import inspect
import pathlib
import typing

from app.utils.fichiers import signature_incoherente
from tests.aides_sources import (
    APP,
    Module,
    atteint,
    routes_declarees,
    routes_qui_atteignent,
)

#: Les points de réception : les routes qui reçoivent un fichier d'un client.
#:
#: 🔴 Les TROIS IMPORTS DE TABLEUR ont rejoint la liste le 19/09/2026 (#1026) :
#: ils n'y étaient pas, et n'avaient **aucun** contrôle — ni type, ni taille, ni
#: signature. Le test était vert, et il avait raison au sens strict : sa portée
#: disait « les quatre endpoints qui ÉCRIVENT sur le disque », et un import
#: n'écrit rien, il analyse en mémoire.
#:
#: ⚠️ C'est la leçon de `standards/05` §9 dans sa forme la plus coûteuse : **la
#: portée d'un contrôle fait partie du contrôle**. Celle-ci était juste, et elle
#: laissait dehors trois chemins par lesquels un fichier arbitraire entrait.
#: « Écrire sur le disque » était le critère du jour où le test a été écrit ;
#: « recevoir un fichier » est celui de la règle.
#:
#: 🔴 ET LE DÉFAUT EST REVENU (audit du 23/11/2026, #2912). La liste `_POINTS` —
#: sept noms de fichier écrits à la main — ignorait trois routes qui reçoivent un
#: fichier : la photo d'annonce, le logo, et l'état descriptif des lots, un
#: QUATRIÈME import de tableur ajouté après #1026. Et son critère était une
#: sous-chaîne dans le TEXTE du fichier : un import, un commentaire ou une autre
#: route du même fichier le satisfaisaient — l'import des lots lu sans la porte,
#: son nom laissé en commentaire, restait vert.
#:
#: Désormais la liste ne se recopie plus, elle se RELÈVE : toute route déclarée
#: dont un paramètre est un `UploadFile` est un point de réception, et sa
#: fonction doit APPELER une porte — directement ou par une fonction de `app/`
#: qu'elle appelle (`_save_image` de `routers/uploads.py`, importée par
#: l'annonce), résolue par les imports du module (`aides_sources.atteint`).

#: Le plancher du relevé : douze routes recevaient un fichier le 23/11/2026. En
#: dessous, le relevé ne voit plus les routes, et le contrôle ne mesure plus rien.
PLANCHER_POINTS = 12


def _est_un_fichier(annotation) -> bool:
    """`UploadFile`, `list[UploadFile]`, `Optional[UploadFile]`, `Annotated[…]`."""
    from starlette.datastructures import UploadFile

    if isinstance(annotation, type) and issubclass(annotation, UploadFile):
        return True
    return any(_est_un_fichier(a) for a in typing.get_args(annotation))


def points_de_reception() -> list[tuple[str, str]]:
    """(module relatif à `app/`, fonction) de chaque route déclarée qui reçoit un fichier."""
    points = set()
    for route in routes_declarees():
        fonction = inspect.unwrap(route.endpoint)
        #  `eval_str` : sous `from __future__ import annotations`, une annotation
        #  est une chaîne ; FastAPI l'a déjà évaluée pour déclarer la route.
        parametres = inspect.signature(fonction, eval_str=True).parameters.values()
        if any(_est_un_fichier(p.annotation) for p in parametres):
            chemin = pathlib.Path(inspect.getsourcefile(fonction)).resolve()
            points.add((chemin.relative_to(APP).as_posix(), fonction.__name__))
    return sorted(points)


def test_un_faux_pdf_est_refuse():
    """Le cas qui motive tout : un exécutable annoncé PDF."""
    motif = signature_incoherente(b"MZ\x90\x00\x03\x00\x00\x00", ".pdf")
    assert motif and ".pdf" in motif, "un exécutable déguisé en PDF passe encore"


def test_les_vrais_fichiers_passent():
    """Un contrôle qui refuse le légitime est désarmé dans la semaine."""
    for donnees, ext in (
        (b"%PDF-1.7\n%\xe2\xe3", ".pdf"),
        (b"PK\x03\x04\x14\x00", ".docx"),
        (b"PK\x03\x04\x14\x00", ".xlsx"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", ".doc"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpg"),
        (b"\x89PNG\r\n\x1a\n\x00\x00", ".png"),
        (b"GIF89a\x01\x00", ".gif"),
    ):
        assert signature_incoherente(donnees, ext) is None, f"{ext} légitime refusé"


def test_une_photo_heic_se_reconnait_a_sa_boite_ftyp():
    """#2389 : la marque est à l'octet 4. Une vraie photo passe sous ses deux
    extensions ; un JPEG ou un AVIF renommé `.heic` est refusé."""
    photo = (pathlib.Path(__file__).parent / "donnees" / "photo.heic").read_bytes()
    assert signature_incoherente(photo, ".heic") is None
    assert signature_incoherente(photo, ".HEIF") is None
    assert signature_incoherente(b"\xff\xd8\xff\xe0\x00\x10JFIF", ".heic") is not None
    assert signature_incoherente(b"\x00\x00\x00\x1cftypavif", ".heic") is not None


def test_un_format_SANS_signature_passe_sans_etre_inspecte():
    """🔴 La moitié qui empêche ce contrôle de devenir une restriction.

    `.txt` et `.csv` n'ont pas de signature stable. Refuser faute de savoir
    reconnaître reviendrait à interdire du contenu légitime au nom de la
    sécurité — et à faire désarmer le contrôle par le premier qui en a besoin.
    """
    assert signature_incoherente(b"n'importe quel texte", ".txt") is None
    assert signature_incoherente(b"a;b;c\n1;2;3", ".csv") is None
    assert signature_incoherente(b"peu importe", "") is None


def test_la_casse_de_l_extension_ne_desarme_pas_le_controle():
    """`.PDF` est un `.pdf` — un contrôle sensible à la casse se contourne au clavier."""
    assert signature_incoherente(b"MZ\x90\x00", ".PDF") is not None
    assert signature_incoherente(b"%PDF-1.4", ".PDF") is None


def test_le_motif_est_LISIBLE_et_pas_un_booleen():
    """Un refus sans motif ressemble à une panne, et c'est ainsi qu'on le désarme."""
    motif = signature_incoherente(b"MZ", ".docx")
    assert isinstance(motif, str) and len(motif) > 20
    assert ".docx" in motif


#: Les deux façons ADMISES de vérifier un fichier téléversé.
#:
#: 🔴 La seconde est née le 08/09/2026 (#825) : le geste complet — lire seize
#: octets, rembobiner, vérifier, journaliser, refuser, nommer, copier — était
#: recopié dans TROIS routeurs au caractère près. La règle était factorisée, son
#: emploi non, et c'est l'emploi qui contient les pièges : sans `seek(0)` le
#: fichier écrit perd sa tête, sans le `raise` la vérification ne bloque rien.
#:
#: ⚠️ Ce test a échoué au moment de la factorisation, et il avait raison de le
#: faire : il cherchait `signature_incoherente` en direct, et ne la trouvait plus.
#: Un contrôle qui suit le code sans qu'on le relise cesse de mesurer ce qu'il
#: croit mesurer — celui-ci a exigé qu'on décide, et voilà la décision.
#:
#: 🔴 ET ELLE A ÉCHOUÉ UNE SECONDE FOIS, le 19/09/2026, pour la même raison et
#: sur une factorisation plus large (#1026) : le geste complet — liste blanche
#: de types, plafond de taille, signature, écriture — vit maintenant dans
#: `verifier_fichier_recu` et `enregistrer_fichier_recu`. Deux appels de plus
#: sont donc admis, et c'est la décision que ce test a exigée.
#:
#: ⚠️ Admettre un nom n'est pas affaiblir le contrôle **tant que le nom admis
#: appelle vraiment la règle** : les deux nouveaux appellent
#: `signature_incoherente`, et `test_televersement_source_unique.py` refuse
#: qu'une écriture de fichier reçu existe ailleurs que dans ce module. Les deux
#: contrôles se tiennent : celui-ci dit « chaque point appelle la règle »,
#: l'autre dit « la règle n'a qu'un seul endroit où vivre ».
_APPELS_ADMIS = (
    "signature_incoherente",
    "enregistrer_televersement",
    "verifier_fichier_recu",
    "enregistrer_fichier_recu",
    "lire_tableur_recu",  # lit puis appelle `verifier_fichier_recu` (#1564)
)


def test_chaque_point_de_televersement_appelle_la_regle():
    """🔴 La portée fait partie du contrôle.

    Une règle centralisée qu'un seul appelant emploie ne protège qu'un chemin —
    et laisse croire qu'elle les protège tous.
    """
    points = points_de_reception()
    assert len(points) >= PLANCHER_POINTS, (
        f"seulement {len(points)} route(s) reçoivent un `UploadFile` "
        f"(plancher {PLANCHER_POINTS}) : {points}. Le relevé ne voit plus les routes, "
        "et ce contrôle serait vert sur rien."
    )
    controlees = set(routes_qui_atteignent(set(_APPELS_ADMIS)))
    manquants = [f"{rel}::{nom}" for rel, nom in points if (rel, nom) not in controlees]
    assert not manquants, (
        "ces points de téléversement n'APPELLENT pas la vérification du fichier, ni "
        f"directement ni par une aide de `app/` : {manquants}. Un fichier déguisé y "
        "passe encore. Employer `enregistrer_fichier_recu` (valide ET écrit), "
        "`verifier_fichier_recu` ou `lire_tableur_recu` (valident sans écrire)."
    )


def _module_forge(rel: str, source: str) -> Module:
    return Module(APP / rel, rel, inspect.cleandoc(source))


#: Le code forgé du témoin : une aide qui vérifie, un routeur, et un homonyme.
_AIDE_FORGEE = """
    from app.utils.fichiers import verifier_fichier_recu

    def _enregistrer(fichier):
        verifier_fichier_recu(fichier.file.read(), fichier.filename, "", "image")
"""
_ROUTEUR_FORGE = """
    from app.utils.fichiers import enregistrer_fichier_recu  # importée, non appelée
    from app.utils.aide_forgee import _enregistrer
    from app.utils import aide_forgee

    @router.post("/autre")
    def autre_route(file):
        return enregistrer_fichier_recu(file)

    @router.post("/commentaire")
    def route_commentaire(file):
        # enregistrer_fichier_recu(file) : la porte, en commentaire seulement
        return file.file.read()

    @router.post("/aide")
    def route_par_aide(file):
        return _enregistrer(file)

    @router.post("/module")
    async def route_par_module(file):
        return aide_forgee._enregistrer(file)
"""
_HOMONYME_FORGE = """
    def _enregistrer(file):
        return file.file.read()  # même nom que l'aide qui vérifie, sans la porte

    @router.post("/homonyme")
    def route_homonyme(file):
        return _enregistrer(file)
"""


def test_temoin_nommer_la_porte_ne_suffit_pas_il_faut_l_appeler():
    """🔴 Le défaut de #2912, rejoué sur un code forgé.

    Refusées : la route qui ne nomme la porte que dans un commentaire et un import
    non appelé (une AUTRE route du même module l'appelant), et celle qui appelle
    une aide locale homonyme d'une aide qui vérifie — la résolution suit les
    imports, pas le nom. Admises : l'appel direct, et l'appel d'une aide d'un
    autre module qui appelle la porte, par son nom ou par son module.
    """
    modules = [
        _module_forge("utils/aide_forgee.py", _AIDE_FORGEE),
        _module_forge("routers/forge.py", _ROUTEUR_FORGE),
        _module_forge("routers/homonyme.py", _HOMONYME_FORGE),
    ]
    portes = set(_APPELS_ADMIS)
    assert routes_qui_atteignent(portes, modules=modules) == [
        ("routers/forge.py", "autre_route"),
        ("routers/forge.py", "route_par_aide"),
        ("routers/forge.py", "route_par_module"),
    ], "un commentaire, un import non appelé ou un nom homonyme satisfait le contrôle"
    assert not atteint("routers/forge.py", "route_commentaire", portes, modules=modules)
    assert not atteint("routers/homonyme.py", "route_homonyme", portes, modules=modules)
    assert atteint("routers/forge.py", "route_par_aide", portes, modules=modules), (
        "l'appel d'une aide qui appelle la porte n'est plus suivi"
    )


def test_le_geste_factorise_REMBOBINE_le_flux():
    """🔴 Sans `seek(0)`, le fichier écrit perd ses seize premiers octets.

    Il n'est pas rejeté : il est **corrompu**, silencieusement, et personne ne
    s'en aperçoit avant de l'ouvrir. C'est le piège que la factorisation retire
    des trois routeurs, et il mérite son propre test — le reste du geste échoue
    bruyamment, celui-ci non.
    """
    import io as _io
    from types import SimpleNamespace

    from app.utils.fichiers import enregistrer_televersement

    from app.utils.stockage import DOSSIER_PRIVE, stockage

    #  ⚠️ Le répertoire est créé PAR LE TEST, pas par la fonction : en
    #  production il existe (volume Docker), et le créer à chaque écriture
    #  masquerait un montage manquant — une panne d'infrastructure deviendrait
    #  un fichier écrit dans le vide du conteneur, perdu au redémarrage.
    stockage().chemin(DOSSIER_PRIVE).mkdir(parents=True, exist_ok=True)

    contenu = b"%PDF-1.4 contenu de test"
    #  Le type annoncé, comme un vrai `UploadFile` : la famille le juge depuis #2156.
    faux = SimpleNamespace(file=_io.BytesIO(contenu), content_type="application/pdf")
    chemin = stockage().chemin(enregistrer_televersement(faux, "rapport.pdf"))
    try:
        assert pathlib.Path(chemin).read_bytes() == contenu, (
            "le fichier écrit ne correspond pas à ce qui a été téléversé : "
            "le flux n'a pas été rembobiné après la lecture de la signature."
        )
    finally:
        pathlib.Path(chemin).unlink(missing_ok=True)


def test_le_geste_factorise_REFUSE_un_fichier_deguise():
    """Le pendant : un exécutable renommé en `.pdf` doit lever une 400.

    ⚠️ Vérifié sur le geste COMPLET, pas seulement sur la règle : c'est
    l'oubli du `raise` qui transformerait le contrôle en simple journal.
    """
    import io as _io
    from types import SimpleNamespace

    import pytest as _pytest
    from fastapi import HTTPException

    from app.utils.fichiers import enregistrer_televersement

    faux = SimpleNamespace(
        file=_io.BytesIO(b"MZ" + bytes([0x90, 0x00]) + b" un executable"),
        content_type="application/pdf",
    )
    with _pytest.raises(HTTPException) as capture:
        enregistrer_televersement(faux, "innocent.pdf")
    assert capture.value.status_code == 400
    assert ".pdf" in str(capture.value.detail)
