"""Les images publiées à chaque version (#1753, 08/10/2026).

Lot DI-1 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.10, D12) : le workflow `.github/workflows/images.yml` pose le tag `vX.Y.Z` et
publie, signées, les images de chaque service. Une installation CoproFirst —
et la référence, au lot DI-6 — n'aura QUE ces images : un service construit par
`docker-compose.yml` mais absent de la matrice manquerait à toutes, sans que
rien ne le dise avant le jour de l'installation.

Ce que le test tient, sur le texte du workflow (PyYAML vient avec
`uvicorn[standard]`) :

- la matrice publie **exactement** les services que `docker-compose.yml` construit,
  avec le même contexte et le même Dockerfile ;
- le workflow ne tourne que sur `main` (ou à la main), jamais sur une PR : une PR
  d'un fork ne doit pas pouvoir publier ;
- aucun droit par défaut, et l'écriture des paquets seulement là où elle sert ;
- chaque commit publie sous `sha-<commit>` (le canal de la référence) ; la version vient
  de `front/package.json` et le tag de `scripts/ci/tag-version.sh` ;
- aucune étiquette flottante (`latest`) : une installation désigne une version.
"""

from __future__ import annotations
import re


from tests.aides_compose import RACINE, services_construits
from tests.aides_compose import lire_yaml as _yaml

WORKFLOW = RACINE / ".github" / "workflows" / "images.yml"


def _declencheurs(flux: dict) -> dict:
    #  PyYAML lit la clé `on:` comme le booléen True (YAML 1.1).
    return flux.get("on") or flux.get(True) or {}


def services_publies() -> dict[str, tuple[str, str]]:
    matrice = _yaml(WORKFLOW)["jobs"]["construire"]["strategy"]["matrix"]["service"]
    return {s["nom"]: (s["contexte"], s["fichier"]) for s in matrice}


def test_chaque_service_construit_est_publie():
    construits, publies = services_construits(), services_publies()
    assert len(construits) >= 4, f"{len(construits)} service(s) construit(s) : le relevé est cassé"
    assert publies == construits, (
        "La matrice d'images.yml ne publie pas exactement ce que docker-compose.yml "
        f"construit :\n  compose  : {sorted(construits.items())}\n  publiés : {sorted(publies.items())}"
    )


def test_la_publication_suit_les_services_dans_les_deux_jobs():
    flux = _yaml(WORKFLOW)
    publies = set(services_publies())
    assert set(flux["jobs"]["publier"]["strategy"]["matrix"]["service"]) == publies
    assert flux["jobs"]["construire"]["strategy"]["matrix"]["plateforme"] == ["amd64", "arm64"], (
        "les Raspberry Pi sont en arm64 : sans lui, la référence ne pourrait pas tirer l'image"
    )


def test_seul_main_publie():
    declencheurs = _declencheurs(_yaml(WORKFLOW))
    assert set(declencheurs) == {"push", "workflow_dispatch"}, declencheurs
    assert declencheurs["push"] == {"branches": ["main"]}


def test_aucun_droit_par_defaut_et_chaque_job_dit_les_siens():
    flux = _yaml(WORKFLOW)
    assert flux["permissions"] == {}, "aucun droit hérité : chaque job déclare les siens"
    for nom, job in flux["jobs"].items():
        assert "permissions" in job, f"le job `{nom}` ne déclare pas ses droits"
    ecrivent_le_depot = {
        n for n, j in flux["jobs"].items() if j["permissions"].get("contents") == "write"
    }
    assert ecrivent_le_depot == {"version", "publier-version"}, (
        f"seuls le tag et la release écrivent dans le dépôt : {ecrivent_le_depot}"
    )
    signent = {n for n, j in flux["jobs"].items() if j["permissions"].get("id-token") == "write"}
    assert signent == {"publier"}, f"seul le job qui atteste reçoit un jeton OIDC : {signent}"


def test_la_version_et_le_tag_ont_une_seule_source():
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert "require('./front/package.json').version" in texte
    assert "bash scripts/ci/tag-version.sh" in texte
    assert (RACINE / "scripts" / "ci" / "tag-version.sh").exists()
    assert "check-version-servie.mjs --client" in texte, (
        "le pied de page de l'image publiée doit être lu, pas supposé"
    )


def test_chaque_commit_publie_sous_son_empreinte():
    """La référence tire `sha-<commit>` : aucun commit de main ne doit en manquer (arbitrage du 08/10)."""
    flux = _yaml(WORKFLOW)
    assert "if" not in flux["jobs"]["construire"], "la construction ne dépend pas d'un bump"
    assert "if" not in flux["jobs"]["publier"]
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert '"$IMAGE:sha-$COMMIT"' in texte
    assert "COMMIT: ${{ github.sha }}" in texte, "l'empreinte complète, pas une abréviation"


def test_aucune_etiquette_flottante():
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert ":latest" not in texte and "type=raw,value=latest" not in texte


# ── La référence tire ce que la CI publie (#1758) ───────────────────────────────

LIB_IMAGES_CI = RACINE / "scripts" / "lib" / "lib-images-ci.sh"


def _constante_shell(nom: str) -> str:
    for ligne in LIB_IMAGES_CI.read_text(encoding="utf-8").splitlines():
        if ligne.startswith(f"{nom}="):
            return ligne.split("=", 1)[1].strip().strip('"')
    raise AssertionError(f"{nom} introuvable dans {LIB_IMAGES_CI.name}")


def test_la_reference_tire_exactement_ce_que_la_ci_publie():
    """Un service publié mais pas tiré resterait construit ; tiré mais pas publié, introuvable."""
    assert set(_constante_shell("SERVICES_IMAGES").split()) == set(services_publies())
    assert _constante_shell("REGISTRE_IMAGES") == _yaml(WORKFLOW)["env"]["REGISTRE"]


def test_la_purge_reconnait_les_images_par_l_etiquette_que_la_ci_pose():
    """Une purge par l'étiquette de Compose ne voyait AUCUNE image tirée : 90 Go par nœud (17/10/2026).

    Le workflow pose `org.opencontainers.image.source=https://github.com/<dépôt>` ;
    le dépôt se lit dans le registre (`ghcr.io/<propriétaire>`) et le préfixe des
    paquets (`coprofirst-<service>`). Et la maintenance hebdomadaire la rejoue.
    """
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert "org.opencontainers.image.source=https://github.com/${{ github.repository }}" in texte
    proprietaire = _yaml(WORKFLOW)["env"]["REGISTRE"].removeprefix("ghcr.io/")
    assert "${{ env.REGISTRE }}/coprofirst-${{ matrix.service.nom }}" in texte
    assert _constante_shell("SOURCE_IMAGES") == f"https://github.com/{proprietaire}/coprofirst"
    maintenance = (RACINE / "scripts" / "exploitation" / "maintenance.sh").read_text(
        encoding="utf-8"
    )
    assert "purger_images_ci_orphelines" in maintenance


def test_auto_deploy_et_la_bascule_obtiennent_sans_construire_eux_memes():
    """La porte est `obtenir_images` : tirer, construire seulement en secours.

    Et sous `set -euo pipefail`, un code de retour non nul tue le script : chaque
    appel capture le sien (`rc=0; obtenir_images … || rc=$?`), sans quoi « en
    attente des images » arrêterait auto-deploy en silence.
    """
    import re

    for chemin in ("scripts/exploitation/auto-deploy.sh", "scripts/exploitation/bascule.sh"):
        code = [
            ligne
            for ligne in (RACINE / chemin).read_text(encoding="utf-8").splitlines()
            if not ligne.lstrip().startswith("#")
        ]
        assert not [
            ligne
            for ligne in code
            if re.search(r"(^|[;&|\s])construire_images\b", ligne) and "À faire sur" not in ligne
        ], f"{chemin} construit lui-même"
        assert any("obtenir_images" in ligne for ligne in code), (
            f"{chemin} n'obtient plus ses images"
        )
    appels = [
        ligne.strip()
        for ligne in (RACINE / "scripts/exploitation/auto-deploy.sh")
        .read_text(encoding="utf-8")
        .splitlines()
        if "obtenir_images" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert len(appels) == 3, appels
    assert all(a == "rc=0; obtenir_images --quiet || rc=$?" for a in appels), appels


def test_chaque_version_taguee_est_publiee_apres_ses_images():
    """#2210 : la référence ne propose que les versions qui ont leur archive de
    déploiement ; elle se publie une fois les images lues, jamais avant."""
    job = _yaml(WORKFLOW)["jobs"]["publier-version"]
    assert job["needs"] == ["version", "verifier-front"]
    assert job["if"] == "needs.version.outputs.versionner == 'true'"
    assert "bash scripts/ci/publier-version.sh" in WORKFLOW.read_text(encoding="utf-8")
    assert re.search(
        r"bash scripts/ci/publier-version\.sh\s+--selftest",
        (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
    ), "publier-version.sh --selftest n'est lancé par aucun job de la CI"
