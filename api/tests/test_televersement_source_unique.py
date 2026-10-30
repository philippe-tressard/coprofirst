"""Un fichier reçu s'écrit sur disque à UN endroit, et il y est contrôlé (#1026).

## 🔴 Ce que ce contrôle refuse, et pourquoi c'est de la sécurité

Le téléversement avait **trois écritures**, et elles n'appliquaient pas les mêmes
règles :

| Chemin | Type MIME | Plafond | Signature |
|---|---|---|---|
| `utils/fichiers.enregistrer_televersement` (documents privés) | **aucun** | **aucun** | oui |
| `routers/uploads._save_image` | oui | oui | réencodage PIL |
| `routers/uploads.upload_fichier`, branche document | oui | oui | oui — **recopiée** de la première, message de journal identique au caractère près |

Et **trois imports Excel n'avaient aucun contrôle du tout** : ni type, ni
taille — `await file.read()` lisait le corps entier en mémoire, puis le passait à
l'analyseur.

**Une duplication de règle de sécurité ne produit aucun signal.** Un fichier
accepté à tort ne fait pas de bruit : il est stocké, servi, et personne ne se
plaint. On ne l'apprend que le jour où quelqu'un s'en sert — c'est le même
raisonnement que `test_regle_acces_source_unique.py` et
`test_appartenance_lot_source_unique.py`.

## Ce que le contrôle vérifie

1. **L'écriture sur disque d'un fichier reçu** n'existe que dans
   `utils/fichiers.py`. Les exceptions sont nommées une par une, et un test
   échoue si l'une cesse de servir.
2. **Les trois règles** — liste blanche de types, plafond de taille, signature —
   ne s'écrivent qu'à cet endroit : aucun routeur ne redéclare de liste MIME ni
   de plafond en mégaoctets.
3. **Chaque famille déclarée porte les trois**, sans exception : une famille
   sans plafond est un téléversement sans plafond.

⚠️ Ce contrôle ne dit pas si les valeurs sont **bien réglées** — un plafond de
500 Mo lui conviendrait. Il dit qu'elles existent, qu'elles sont nommées, et
qu'elles ne sont écrites qu'une fois. Le réglage se relit, il ne se mesure pas.
"""

from __future__ import annotations

import ast
import pathlib
import re

from tests.aides_sources import modules_app

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le module qui porte le geste — et le seul autorisé à écrire un fichier reçu.
SOURCE = "utils/fichiers.py"

#: Le SEUL module qui pose des octets sur le volume des fichiers : le stockage de
#: la copropriété (#1748). `SOURCE` y écrit les fichiers REÇUS, après contrôle.
STOCKAGE = "utils/stockage.py"

#: Qui appelle l'écriture du stockage (`.ecrire(…)`, `.ecrire_flux(…)`), et pourquoi.
#: Un fichier REÇU passe par `SOURCE` ; un fichier PRODUIT par l'application se
#: déclare ici. Sans cette liste, un routeur écrirait des octets reçus par le
#: stockage sans qu'aucune forme d'écriture ne paraisse chez lui.
ECRIVAINS_DU_STOCKAGE = {
    SOURCE: "les fichiers reçus, après la liste blanche, le plafond et la signature",
    "routers/annonces_hall.py": "le PDF d'affiche que l'application vient de PRODUIRE "
    "(WeasyPrint) — rien n'est reçu du client, il n'y a ni type ni signature à confronter",
    "utils/conservation_archive.py": "l'archive .zip des pièces jointes d'affaires échues, "
    "PRODUITE par la tâche de conservation (#2014) à partir de fichiers déjà stockés, et "
    "relue avant tout retrait — rien n'est reçu du client",
    "demo/fichiers.py": "le logo, l'illustration et les PDF de la démo publique, PRODUITS "
    "par l'application à chaque chargement (#1904) — la démo ne reçoit aucun fichier (M10)",
    "utils/points_conseil_expedition.py": "le PDF du compte rendu VALIDÉ d'un point CS / "
    "Syndic, PRODUIT par l'application (WeasyPrint) et rangé sous le dossier privé (#2082) — "
    "rien n'est reçu du client",
    "utils/question_reglement/transcription.py": "les décisions d'un PV d'AG, Markdown "
    "PRODUIT par l'assistant puis relu par l'administration — un texte saisi, pas un "
    "fichier reçu : son extension (.md) et son type sont fixés par le code, dans le "
    "dossier privé",
}

#: Les écritures sur disque qui ne sont **pas** des téléversements, nommées une
#: par une avec leur raison. Le dernier test échoue si l'une ne sert plus.
#:
#: La distinction est celle qui compte : un fichier **produit** par
#: l'application ne peut pas mentir sur son type, puisque c'est nous qui le
#: fabriquons. Un fichier **reçu** vient du réseau.
ECRITURES_NON_TELEVERSEMENT = {
    (
        "utils/manuel_pdf_cache.py",
        "write_bytes",
    ): "garde sur disque le manuel PDF que l'application vient de RENDRE (#1071) "
    "— rien n'est reçu, et le dossier est hors du volume `uploads` servi en statique",
    (
        "utils/import_copropriete.py",
        "write_bytes",
    ): "restaure les fichiers d'une archive d'EXPORT de la copropriété (#1749), chacun "
    "confronté à son empreinte SHA-256 du manifeste avant d'être écrit, dans le dossier "
    "que désigne l'opérateur — l'import vers une base cible (DI-7), jamais un fichier "
    "reçu d'un client",
}

#: Un plafond de taille en mégaoctets, écrit en clair.
_MOTIF_PLAFOND = re.compile(r"MAX_[A-Z_]*SIZE_MB|MAX_[A-Z_]*MO\b|1024\s*\*\s*1024")

#: Un type MIME, pour repérer les LISTES qui en contiennent.
_MOTIF_MIME = re.compile(r"^(?:image|application|text)/[a-z0-9.+-]+$")


def _mode_ecriture(mode: ast.AST | None) -> bool:
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "w" in mode.value


def _forme_d_ecriture(appel: ast.Call) -> str | None:
    """Le nom de la forme d'écriture d'octets sur disque que porte cet appel.

    🔴 **Quatre formes, et non deux** (30/09/2026). Le détecteur ne connaissait
    que `write_bytes` et `open(…, "w…")` ; `test_signature_fichiers.py` gardait,
    à côté, un relevé des routeurs qui faisaient `shutil.copyfileobj(file.file…`
    — dont le motif ne trouvait plus rien depuis la factorisation (#1026), et
    rendait donc un vert à vide. Les deux formes qu'il cherchait vivent ici
    désormais, au seul détecteur des écritures.
    """
    cible = ast.unparse(appel.func)
    mode_nomme = next((k.value for k in appel.keywords if k.arg == "mode"), None)
    if cible.endswith("write_bytes"):
        return "write_bytes"
    if cible.endswith("copyfileobj"):
        return "copyfileobj"
    if cible == "open":
        mode = appel.args[1] if len(appel.args) > 1 else mode_nomme
        return "open(w)" if _mode_ecriture(mode) else None
    #  `<chemin>.open("wb")` — un `Path` ouvert en écriture. Le mode y est le
    #  PREMIER argument ; `tarfile.open(dest, "w:gz")` ou `Image.open(flux)`, dont
    #  le premier argument n'est pas un mode, n'en sont pas.
    if isinstance(appel.func, ast.Attribute) and appel.func.attr == "open":
        mode = appel.args[0] if appel.args else mode_nomme
        return ".open(w)" if _mode_ecriture(mode) else None
    return None


def _ecritures_de(source: str) -> list[tuple[int, str]]:
    """(ligne, forme) pour chaque écriture d'octets sur disque de ce source."""
    return [
        (noeud.lineno, forme)
        for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call) and (forme := _forme_d_ecriture(noeud))
    ]


def _ecritures_disque():
    """(fichier, ligne, appel) pour chaque écriture d'octets sur disque."""
    for m in modules_app():
        try:
            ecritures = _ecritures_de(m.source)
        except SyntaxError:  # pragma: no cover
            continue
        for ligne, nom in ecritures:
            yield m.rel, ligne, nom


def test_le_controle_voit_bien_des_ecritures():
    """Cas zéro de la portée : une liste vide se lirait comme « aucun écart »."""
    vues = list(_ecritures_disque())
    assert vues, (
        "aucune écriture sur disque trouvée dans app/ — le contrôle a perdu sa "
        "portée et rendrait un vert parfait"
    )
    assert (_APP / SOURCE).exists(), f"{SOURCE} a disparu"


def test_le_detecteur_voit_CHAQUE_forme_d_ecriture():
    """Le contrôle sait REFUSER : un extrait forgé par forme, et deux lectures
    qui ne doivent pas être prises pour des écritures.

    Sans lui, une forme que le détecteur aurait cessé de reconnaître laisserait
    le test ci-dessus vert — sur le code même qu'il doit refuser.
    """
    forge = "\n".join(
        (
            "chemin.write_bytes(donnees)",  # 1
            "open(dest, 'wb')",  # 2
            "shutil.copyfileobj(file.file, sortie)",  # 3
            "chemin.open('wb')",  # 4
            "open(dest, mode='w')",  # 5
            "Image.open(io.BytesIO(donnees))",  # lecture
            "open(dest)",  # lecture
            "tarfile.open(dest, 'r:gz')",  # lecture
        )
    )
    vues = _ecritures_de(forge)
    attendues = [
        (1, "write_bytes"),
        (2, "open(w)"),
        (3, "copyfileobj"),
        (4, ".open(w)"),
        (5, "open(w)"),
    ]
    assert vues == attendues, (
        f"le détecteur a vu {vues}, il devait voir {attendues} : une forme "
        "d'écriture lui échappe, ou une lecture passe pour une écriture"
    )


def test_un_fichier_recu_ne_s_ecrit_que_dans_la_source():
    """Le défaut exact : deux routeurs écrivaient les octets reçus eux-mêmes."""
    fautes = []
    for fichier, ligne, appel in _ecritures_disque():
        if fichier == STOCKAGE:
            continue
        if (fichier, appel) in ECRITURES_NON_TELEVERSEMENT:
            continue
        fautes.append(f"  {fichier}:{ligne} — {appel}")

    assert not fautes, (
        "Ces lignes écrivent un fichier sur disque hors de la source unique :\n"
        + "\n".join(fautes)
        + "\n\n"
        f"Un fichier REÇU passe par `{SOURCE}`, qui porte la liste blanche de "
        "types, le plafond de taille et la vérification de signature. Un fichier "
        "PRODUIT par l'application est une autre notion : l'inscrire dans "
        "ECRITURES_NON_TELEVERSEMENT, avec sa raison."
    )


def test_aucun_routeur_ne_redeclare_un_plafond_ou_une_liste_de_types():
    """Les trois règles sont des NOTIONS, pas des valeurs à recopier.

    C'est la moitié du défaut que le premier test ne voit pas : un routeur peut
    déléguer l'écriture et garder sa propre liste MIME, donc décider seul de ce
    qu'il accepte.

    ⚠️ **Une liste blanche, pas un type de réponse.** La première version de ce
    contrôle cherchait un type MIME n'importe où dans une ligne : elle accusait
    `media_type="application/pdf"` (le type d'une réponse que nous *servons*) et
    `mime_type=file.content_type or "application/octet-stream"` (une valeur de
    repli stockée en base). Cinq faux positifs, tous légitimes.

    Un motif trop large ne rend pas un verdict prudent — il rend un verdict
    faux, et un contrôle qui accuse le code correct finit désarmé. Le critère
    porte donc sur ce qui se recopie vraiment : un **littéral d'ensemble ou de
    dictionnaire** dont les entrées sont des types MIME.
    """
    fautes = []
    for m in modules_app("routers"):
        source = m.source
        nom = m.rel
        try:
            arbre = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue

        for noeud in ast.walk(arbre):
            #  Une liste blanche : `{"image/jpeg", …}` ou `{"application/pdf": ".pdf", …}`
            if isinstance(noeud, (ast.Set, ast.Dict)):
                valeurs = noeud.elts if isinstance(noeud, ast.Set) else noeud.keys
                types = [
                    v.value
                    for v in valeurs
                    if isinstance(v, ast.Constant)
                    and isinstance(v.value, str)
                    and _MOTIF_MIME.match(v.value)
                ]
                if types:
                    fautes.append(
                        f"  {nom}:{noeud.lineno} — liste de types : {', '.join(types[:3])}…"
                    )

        #  Le plafond, lui, se lit bien en texte : c'est une constante nommée ou
        #  une multiplication, jamais une structure.
        for i, ligne in enumerate(source.split("\n"), 1):
            nue = ligne.strip()
            if nue.startswith("#") or nue.startswith('"""') or nue.startswith("*"):
                continue
            if _MOTIF_PLAFOND.search(ligne):
                fautes.append(f"  {nom}:{i} — plafond de taille : {nue[:70]}")

    assert not fautes, (
        "Ces routeurs déclarent eux-mêmes ce qu'ils acceptent :\n" + "\n".join(fautes) + "\n\n"
        f"Les familles de téléversement sont déclarées dans `{SOURCE}` "
        "(FAMILLES), avec leur liste de types, leur plafond et leurs extensions. "
        "Un routeur nomme la famille, il ne redéfinit pas ses règles."
    )


def test_chaque_famille_porte_les_TROIS_regles():
    """Une famille sans plafond est un téléversement sans plafond.

    Le défaut d'origine est exactement là : la famille des documents privés
    n'avait ni liste de types ni plafond, seulement la signature — et personne ne
    pouvait le voir, puisqu'il n'existait **aucune table** à comparer.

    ⚠️ Ce test lit la table **importée**, pas le texte du fichier. Une première
    version comptait les occurrences de `types=` dans le code source : elle
    échouait sur une table construite par une fabrique — c'est-à-dire sur la
    forme la mieux factorisée, celle où `extensions` est *dérivée* de `types` au
    lieu d'être recopiée. Vérifier le **comportement**, jamais l'artefact.
    """
    from app.utils.fichiers import FAMILLES, FamilleFichier

    assert len(FAMILLES) >= 3, f"seulement {len(FAMILLES)} famille(s) déclarée(s)"

    for nom, regles in FAMILLES.items():
        assert isinstance(regles, FamilleFichier), (
            f"la famille « {nom} » n'est pas un FamilleFichier : les trois règles "
            "ne sont plus garanties par le type"
        )
        assert regles.types, (
            f"la famille « {nom} » n'a **aucune liste de types** : elle accepte "
            "ce que le client annonce, c'est le défaut de #1026 à sa source"
        )
        assert regles.plafond_mo > 0, (
            f"la famille « {nom} » n'a **aucun plafond** : un envoi de n'importe "
            "quelle taille est accepté, et il est lu en mémoire avant de l'être"
        )
        assert regles.extensions, f"la famille « {nom} » ne produit aucune extension connue"
        #  🔴 L'extension écrite sur disque doit venir de la table, jamais du nom
        #  fourni : `/uploads/*` est servi en statique, et Caddy pose le
        #  `Content-Type` d'après l'extension du fichier.
        assert set(regles.extensions) == set(regles.types.values()), (
            f"la famille « {nom} » déclare des extensions qui ne correspondent "
            "pas à ses types : les deux listes ont divergé, donc l'une des deux "
            "est recopiée"
        )


def test_une_famille_inconnue_est_refusee_et_ne_passe_pas_en_silence():
    """Le cas zéro de la fabrique : un nom de famille fautif doit LEVER.

    Un `FAMILLES.get(famille)` qui rendrait `None` sans lever ferait sauter les
    trois contrôles d'un coup — le défaut le plus permissif possible, sur une
    simple faute de frappe dans un routeur.
    """
    import pytest

    from app.utils.fichiers import verifier_fichier_recu

    with pytest.raises(ValueError):
        verifier_fichier_recu(b"%PDF-1.4", "x.pdf", "application/pdf", "famille-absente")


def test_les_trois_regles_refusent_VRAIMENT(disque_jetable, session):
    """Chacune, éprouvée séparément — sinon « type et taille contrôlés » reste
    une affirmation sans contenu.
    """
    import pytest
    from fastapi import HTTPException

    from app.utils.fichiers import FAMILLES, enregistrer_fichier_recu
    from tests.aides_base import compte

    #  « essai » est un dossier SERVI : le fichier écrit note son auteur (#2154).
    auteur = compte(session)

    #  Le dossier « essai » du stockage de la copropriété servie (#1748) : `disque_jetable`.

    #  Un PDF minimal, dont la signature est cohérente.
    pdf = b"%PDF-1.4\n%%EOF\n"

    #  1. le type annoncé n'est pas dans la famille
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(pdf, "x.pdf", "application/x-msdownload", "document", "essai")
    assert refus.value.status_code == 400

    #  2. le plafond
    trop_gros = b"%PDF-1.4" + b"0" * (FAMILLES["document"].plafond_mo * 1024 * 1024)
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(trop_gros, "x.pdf", "application/pdf", "document", "essai")
    assert refus.value.status_code == 413

    #  3. la signature : un exécutable annoncé PDF — le défaut de #773
    with pytest.raises(HTTPException) as refus:
        enregistrer_fichier_recu(
            b"MZ\x90\x00" + b"0" * 20, "x.pdf", "application/pdf", "document", "essai"
        )
    assert refus.value.status_code == 400

    #  Et le cas qui doit PASSER, sans quoi les trois refus ne prouvent rien :
    #  un contrôle qui refuse tout est aussi faux qu'un contrôle qui accepte tout.
    nom = enregistrer_fichier_recu(
        pdf,
        "Devis toiture.pdf",
        "application/pdf",
        "document",
        "essai",
        user=auteur,
        session=session,
    )
    assert nom.endswith(".pdf")
    assert "toiture" in nom, "le radical du nom d'origine est perdu"
    assert (disque_jetable / "essai" / nom).read_bytes() == pdf


def test_aucune_exception_ne_survit_a_son_motif():
    """Une exception qui ne sert plus finit par couvrir autre chose."""
    vues = {(f, a) for f, _, a in _ecritures_disque()}
    perimees = [
        f"  {f} / {a} — « {raison} »"
        for (f, a), raison in ECRITURES_NON_TELEVERSEMENT.items()
        if (f, a) not in vues
    ]
    assert not perimees, (
        "Ces exceptions ne correspondent plus à rien :\n"
        + "\n".join(perimees)
        + "\n\nLes retirer de ECRITURES_NON_TELEVERSEMENT."
    )


def ecrivains(arbre: ast.AST) -> list[int]:
    """Les lignes d'un arbre qui appellent l'écriture du STOCKAGE.

    Le receveur est `stockage()` lui-même, ou un nom qui en a reçu la valeur
    (`st = stockage()`) : un autre `.ecrire(…)` — le cache disque du manuel —
    n'est pas la porte du volume.
    """

    def _est_stockage(noeud: ast.AST) -> bool:
        return (
            isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Name)
            and noeud.func.id == "stockage"
        )

    lies = {
        cible.id
        for n in ast.walk(arbre)
        if isinstance(n, ast.Assign) and _est_stockage(n.value)
        for cible in n.targets
        if isinstance(cible, ast.Name)
    }
    return [
        n.lineno
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in ("ecrire", "ecrire_flux")
        and (
            _est_stockage(n.func.value)
            or (isinstance(n.func.value, ast.Name) and n.func.value.id in lies)
        )
    ]


def test_seuls_les_ecrivains_declares_appellent_le_stockage():
    """La porte du disque est le stockage ; qui la franchit se déclare (#1748)."""
    vus = {m.rel for m in modules_app() if m.rel != STOCKAGE and ecrivains(m.arbre)}
    assert vus == set(ECRIVAINS_DU_STOCKAGE), (
        f"appelants de l'écriture du stockage : {sorted(vus)} — déclarés : "
        f"{sorted(ECRIVAINS_DU_STOCKAGE)}. Un fichier REÇU passe par `{SOURCE}` ; "
        "un fichier PRODUIT se déclare dans ECRIVAINS_DU_STOCKAGE, avec sa raison."
    )


def test_le_releve_des_ecrivains_voit_chaque_forme():
    source = (
        "st = stockage()\n"
        "st.ecrire(cle, b'x')\n"
        "stockage().ecrire_flux(cle, f)\n"
        "st.lire(cle)\n"
        "manuel_pdf_cache.ecrire(cle, pdf, dossier)\n"
    )
    assert ecrivains(ast.parse(source)) == [2, 3]
