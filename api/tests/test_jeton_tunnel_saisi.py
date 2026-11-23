"""Le jeton du tunnel se saisit masqué, jamais en argument de commande (claude-config#614).

`install-cloudflared.sh` recevait le jeton en paramètre positionnel, et la procédure
de restauration dictait `install-cloudflared.sh <JETON_DU_TUNNEL>` : la valeur
restait dans l'historique de l'interpréteur, dans la trace des commandes `sudo`, et
se lisait dans `ps` le temps du script. Son jumeau, `changer-jeton-tunnel.sh`, la
lisait déjà sans écho. La lecture vit désormais une fois, `lire_jeton_saisi`
(`scripts/lib/lib-jeton-tunnel.sh`), et ce test refuse le retour de l'argument :

- dans un script qui source le module, aucune variable de jeton prise d'un
  paramètre positionnel, et aucun `read` du jeton hors de `lire_jeton_saisi` ;
- dans un document ou une consigne, aucune commande qui passe le jeton à
  l'installateur.
"""

import re
import subprocess

from tests.conftest import racine_depot, scripts_shell_versionnes

RACINE = racine_depot()
MODULE = "scripts/lib/lib-jeton-tunnel.sh"

#: Une variable de jeton affectée depuis un paramètre positionnel (`$1`, `${1:-}`, `$@`).
JETON_EN_ARGUMENT = re.compile(r"\b\w*(TOKEN|JETON)\w*=[\"']?\$\{?[1-9@*]", re.I)
#: Une lecture de l'entrée qui n'est pas la porte unique.
LECTURE_DIRECTE = re.compile(r"^\s*(IFS=\S*\s+)?read\b[^#\n]*\b\w*(TOKEN|JETON)\w*", re.I | re.M)
#: L'installateur appelé avec une valeur après lui (`<JETON>`, `eyJ…`, `$VAR`).
INSTALLEUR_AVEC_JETON = re.compile(r"install-cloudflared\.sh[ \t]+[<$'\"]|install-cloudflared\.sh[ \t]+eyJ")


def _scripts_du_module() -> list:
    return [
        s
        for s in scripts_shell_versionnes()
        if s.relative_to(RACINE).as_posix() != MODULE
        and "lib-jeton-tunnel.sh" in s.read_text(encoding="utf-8", errors="replace")
    ]


def _textes() -> list:
    sortie = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md", "*.sh"],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [RACINE / p for p in sortie if (RACINE / p).is_file()]


def test_les_scripts_du_jeton_sont_lus():
    #  Cas zéro : une portée vide rendrait les tests suivants verts sans rien lire.
    noms = {s.name for s in _scripts_du_module()}
    assert {"install-cloudflared.sh", "changer-jeton-tunnel.sh"} <= noms, noms


def test_aucun_jeton_pris_d_un_argument():
    fautes = [
        f"{s.relative_to(RACINE)}:{n}: {ligne.strip()}"
        for s in _scripts_du_module()
        for n, ligne in enumerate(s.read_text(encoding="utf-8").splitlines(), 1)
        if JETON_EN_ARGUMENT.search(ligne)
    ]
    assert not fautes, "jeton reçu en argument — passer par lire_jeton_saisi :\n" + "\n".join(fautes)


def test_le_jeton_ne_se_lit_que_par_la_porte_unique():
    fautes = [
        f"{s.relative_to(RACINE)}: {m.group(0).strip()}"
        for s in _scripts_du_module()
        for m in LECTURE_DIRECTE.finditer(s.read_text(encoding="utf-8"))
    ]
    assert not fautes, "lecture du jeton hors de lire_jeton_saisi :\n" + "\n".join(fautes)
    for nom in ("install-cloudflared.sh", "changer-jeton-tunnel.sh"):
        script = next(s for s in _scripts_du_module() if s.name == nom)
        assert "lire_jeton_saisi" in script.read_text(encoding="utf-8"), nom


def test_aucune_procedure_ne_passe_le_jeton_a_l_installateur():
    fautes = [
        f"{p.relative_to(RACINE)}:{n}: {ligne.strip()}"
        for p in _textes()
        for n, ligne in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if INSTALLEUR_AVEC_JETON.search(ligne)
    ]
    assert not fautes, "le jeton se colle à l'invite de l'installateur :\n" + "\n".join(fautes)


def test_les_motifs_reconnaissent_la_faute():
    #  Le contrôle lui-même : les trois formes fautives d'avant le correctif.
    assert JETON_EN_ARGUMENT.search('TOKEN="${1:-}"')
    assert LECTURE_DIRECTE.search("  read -rs JETON; dire ''")
    assert INSTALLEUR_AVEC_JETON.search("sudo bash …/install-cloudflared.sh <JETON_DU_TUNNEL>")
    assert not INSTALLEUR_AVEC_JETON.search("sudo bash …/install-cloudflared.sh")
