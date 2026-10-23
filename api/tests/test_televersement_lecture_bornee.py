"""La porte de téléversement, vue de son EMPLOI (#2156, #2164 — audit du 22/10/2026).

`test_televersement_source_unique.py` tient la TABLE des familles et l'unicité de
l'écriture. Ce fichier-ci tient ce que la table ne dit pas : chaque famille est
appliquée par quelqu'un, un fichier reçu ne se lit que borné par sa famille, le
débit des dépôts et le corps d'une requête sont plafonnés.
"""

from __future__ import annotations

import ast
import re

from tests.aides_sources import modules_app

SOURCE = "utils/fichiers.py"

# ── #2156 et #2164 (audit du 22/10/2026) ─────────────────────────────────────

_GESTES_DE_FAMILLE = {"verifier_fichier_recu", "enregistrer_fichier_recu", "lire_fichier_recu"}


def _familles_nommees() -> set[str]:
    """Les noms de famille passés en CONSTANTE à un geste de la porte, dans `app/`."""
    from app.utils.fichiers import FAMILLES

    nommees = set()
    for m in modules_app():
        for n in ast.walk(m.arbre):
            if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) in (
                _GESTES_DE_FAMILLE
            ):
                for a in [*n.args, *(k.value for k in n.keywords)]:
                    if isinstance(a, ast.Constant) and a.value in FAMILLES:
                        nommees.add(a.value)
    return nommees


def test_chaque_famille_a_un_appelant():
    """Une famille déclarée que personne ne nomme n'est pas une règle, c'est un décor.

    🔴 `document_prive` portait ses types et son plafond depuis #1026, et n'avait
    AUCUN appelant : les documents privés n'avaient ni l'un ni l'autre, et
    `test_chaque_famille_porte_les_TROIS_regles` restait vert — il lisait la
    table, jamais son emploi (#2156).
    """
    from app.utils.fichiers import FAMILLES

    nommees = _familles_nommees()
    assert nommees, "aucune famille relevée : le contrôle ne lit plus rien"
    assert set(FAMILLES) <= nommees, f"famille(s) sans appelant : {sorted(set(FAMILLES) - nommees)}"


def _lectures_non_bornees() -> list[str]:
    fautes = []
    for m in modules_app():
        for f in ast.walk(m.arbre):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if f.name == "lire_fichier_recu" and m.rel == SOURCE:
                continue
            for n in ast.walk(f):
                lit_le_flux = (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "read"
                    and isinstance(n.func.value, ast.Attribute)
                    and n.func.value.attr == "file"
                )
                attend_read = (
                    isinstance(n, ast.Await)
                    and isinstance(n.value, ast.Call)
                    and getattr(n.value.func, "attr", "") == "read"
                )
                if lit_le_flux or attend_read:
                    fautes.append(f"{m.rel}:{n.lineno}")
    return fautes


def test_un_fichier_recu_ne_se_lit_que_borne_par_sa_famille():
    """`UploadFile.file.read()` lisait le corps ENTIER avant de juger sa taille (#2164)."""
    assert not _lectures_non_bornees(), (
        "un fichier reçu se lit par `utils/fichiers.lire_fichier_recu` (plafond + 1 octet), "
        f"jamais par `.file.read()` : {_lectures_non_bornees()}"
    )


def _fichier(octets: bytes, nom: str, type_mime: str):
    import io

    from starlette.datastructures import Headers, UploadFile

    return UploadFile(
        io.BytesIO(octets), filename=nom, headers=Headers({"content-type": type_mime})
    )


def test_un_document_prive_subit_les_trois_regles(disque_jetable):
    import pytest
    from fastapi import HTTPException

    from app.utils.fichiers import FAMILLES, enregistrer_televersement

    pdf = b"%PDF-1.4\n%%EOF\n"
    with pytest.raises(HTTPException) as refus:
        enregistrer_televersement(
            _fichier(b"MZ" + b"0" * 30, "x.exe", "application/x-msdownload"), "x.exe"
        )
    assert refus.value.status_code == 400
    plafond = FAMILLES["document_prive"].plafond_mo * 1024 * 1024
    with pytest.raises(HTTPException) as refus:
        enregistrer_televersement(
            _fichier(pdf + b"0" * plafond, "x.pdf", "application/pdf"), "x.pdf"
        )
    assert refus.value.status_code == 413
    cle = enregistrer_televersement(_fichier(pdf, "PV AG.pdf", "application/pdf"), "PV AG.pdf")
    assert cle.startswith("prive/") and cle.endswith(".pdf")
    assert (disque_jetable / cle).read_bytes() == pdf


def test_le_depot_d_un_fichier_est_borne_en_debit():
    """Par la porte réelle : `/uploads/fichier` est ouvert à tout compte connecté (#2164).

    Un refus (type inconnu, 400) compte aussi : la limite borne la requête, pas
    le fichier accepté.
    """
    from app.models.core import RoleUtilisateur
    from app.utils.limiter import LIMITE_TELEVERSEMENT
    from tests.aides_http import base_http, client_http

    plafond = int(LIMITE_TELEVERSEMENT.split("/")[0])
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.résident)
        codes = [
            http.post(
                "/uploads/fichier", files={"file": ("x.bin", b"0", "application/x-inconnu")}
            ).status_code
            for _ in range(plafond + 1)
        ]
    assert set(codes[:plafond]) == {400} and codes[plafond] == 429, codes


def test_caddy_plafonne_le_corps_au_dessus_de_la_plus_grosse_famille():
    """Le plafond de Caddy (#2164) ne doit ni manquer, ni couper un dépôt légitime.

    Contrat entre deux fichiers que rien d'autre ne relie : `request_body.max_size`
    du bloc `/api/*` et le plus gros `plafond_mo` de `FAMILLES`.
    """
    from app.utils.fichiers import FAMILLES
    from tests.aides_caddy import caddyfile

    bloc = re.search(r"handle /api/\* \{(.*?)\n\t\}", caddyfile(), re.S)
    assert bloc, "bloc `handle /api/*` introuvable dans le Caddyfile"
    plafond = re.search(r"request_body \{\s*max_size (\d+)MB", bloc.group(1))
    assert plafond, "aucun `request_body { max_size … }` sur /api/* : rien ne borne le corps"
    plus_grosse = max(f.plafond_mo for f in FAMILLES.values())
    assert plus_grosse < int(plafond.group(1)) <= plus_grosse * 2, (
        f"max_size {plafond.group(1)} Mo pour une famille de {plus_grosse} Mo"
    )


def test_un_type_indetermine_se_deduit_de_l_extension_dans_la_famille(disque_jetable):
    """Sous Windows, un `.md` part souvent sans type, ou en `application/octet-stream` :
    le règlement de copropriété se joint pourtant en Markdown (#2156). Le type se
    déduit alors de l'extension, parmi ceux de la famille — et la signature juge."""
    import pytest
    from fastapi import HTTPException

    from app.utils.fichiers import enregistrer_televersement, type_annonce

    assert type_annonce("", "rcp.md", "document_prive") == "text/markdown"
    assert type_annonce("application/octet-stream", "pv.pdf", "document_prive") == "application/pdf"
    assert type_annonce("application/pdf", "x.md", "document_prive") == "application/pdf"
    cle = enregistrer_televersement(_fichier(b"# Reglement", "rcp.md", ""), "rcp.md")
    assert cle.endswith(".md")
    #  Un exécutable sans type, nommé .pdf : le type se déduit, la signature refuse.
    with pytest.raises(HTTPException) as refus:
        enregistrer_televersement(
            _fichier(b"MZ" + b"0" * 30, "x.pdf", "application/octet-stream"), "x.pdf"
        )
    assert refus.value.status_code == 400
    #  Une extension hors de la famille reste refusée.
    with pytest.raises(HTTPException):
        enregistrer_televersement(_fichier(b"<html>", "x.html", ""), "x.html")
