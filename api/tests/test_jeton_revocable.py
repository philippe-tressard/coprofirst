"""Le jeton d'accès cesse de valoir dès que le mot de passe change (#1063).

## Le trou (ouvert en marge de #1027)

Le jeton d'accès est un **JWT autoporteur**, vérifié par signature. Changer son
mot de passe révoquait les `RefreshToken`, donc ramenait la fenêtre d'un
attaquant de sept jours à **cent vingt minutes** — la durée du jeton d'accès.
Elle ne tombait pas à zéro : rien, côté serveur, ne pouvait invalider un jeton
d'accès déjà émis.

## La décision (22/09/2026) : l'empreinte du mot de passe DANS le jeton

Des trois pistes du ticket, c'est la seule dont le coût est **nul** : une liste
de révocation par `jti` demanderait une lecture de plus par requête
authentifiée — un coût permanent sur un Raspberry Pi —, et raccourcir la durée
ne ferait que réduire la fenêtre sans la fermer.

`_get_current_user` **charge déjà** le compte pour vérifier qu'il est actif. Le
condensé du `hashed_password` est donc là, gratuitement : le jeton en porte une
empreinte courte, on les compare, et un mot de passe changé invalide d'un coup
**tous** les jetons d'accès du compte.

⚠️ Un jeton émis avant ce lot n'a pas d'empreinte : il est refusé. Sans douleur
— le front renouvelle en silence sur 401 (`project_session_expiree_images`), et
le rafraîchissement émet un jeton complet.

🔴 Ce que cela ne couvre PAS, et c'est écrit pour que personne ne le croie : la
**désactivation** d'un compte est déjà traitée ailleurs (`_get_current_user`
refuse `actif = False`), mais une élévation ou une perte de rôle ne l'est pas —
le rôle n'entre pas dans l'empreinte.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from app.auth.jwt import (
    create_access_token,
    creer_jeton_acces,
    decode_token,
    empreinte_du_compte,
    empreinte_secret,
    hash_password,
)
from tests.aides_sources import modules_app


def test_le_jeton_porte_l_empreinte():
    """Sans elle, il n'y a rien à comparer."""
    jeton = create_access_token({"sub": "1"}, empreinte="abc123")
    charge = decode_token(jeton)
    assert charge is not None
    assert charge.get("pwd") == "abc123"


def test_l_empreinte_change_avec_le_mot_de_passe():
    """Deux condensés différents pour deux mots de passe : c'est tout ce que la
    comparaison demande."""
    avant = empreinte_secret(hash_password("ancien-mot-de-passe"))
    apres = empreinte_secret(hash_password("nouveau-mot-de-passe"))
    assert avant != apres
    assert len(avant) == 16, "une empreinte courte : elle voyage dans chaque requête"


def test_l_empreinte_ne_revele_pas_le_condense():
    """Le jeton est lisible par son porteur : il ne doit pas y trouver de quoi
    attaquer le mot de passe hors ligne."""
    condense = hash_password("mot-de-passe")
    empreinte = empreinte_secret(condense)
    assert empreinte not in condense
    assert condense[-16:] != empreinte


def test_la_meme_entree_donne_la_meme_empreinte():
    """Sinon chaque requête serait refusée."""
    condense = hash_password("stable")
    assert empreinte_secret(condense) == empreinte_secret(condense)


def _appels(nom: str) -> list[pathlib.Path]:
    """Les fichiers qui appellent `nom`, hors du module qui le définit."""
    trouves = []
    for module in modules_app():
        for noeud in ast.walk(module.arbre):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", None) == nom:
                trouves.append(module.chemin)
                break
    return trouves


def test_une_seule_porte_emet_un_jeton_d_acces():
    """🔴 Deux appelants, c'est deux chances d'oublier l'empreinte.

    `create_access_token` était appelé à la connexion ET au rafraîchissement,
    chacun composant sa charge utile. Un jeton émis sans empreinte serait refusé
    par `_get_current_user` — donc une porte oubliée ne se verrait pas à la
    relecture, elle déconnecterait des gens.
    """
    appelants = {f.name for f in _appels("create_access_token")}
    assert appelants <= {"jwt.py"}, (
        f"`create_access_token` appelé hors de sa porte : {sorted(appelants)}. "
        "Passer par `creer_jeton_acces(user)`, qui pose l'empreinte."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  LE COMPORTEMENT, et non sa structure
# ══════════════════════════════════════════════════════════════════════════════
#
#  🔴 Les tests ci-dessus lisent le code ; celui-ci exerce la dépendance
#  réelle. Sans lui, une empreinte posée et jamais comparée passerait tous les
#  contrôles précédents — c'est la différence entre « le contrôle existe » et
#  « le contrôle mord » (`standards/04`). C'est aussi lui qui prouve que
#  `auth/deps.py` compare l'empreinte : y chercher la chaîne `empreinte_secret`
#  ne le prouvait pas (un import inutilisé suffisait).


class _SessionFactice:
    """Juste ce que `_get_current_user` demande : rendre un compte par son id."""

    def __init__(self, compte):
        self._compte = compte

    def get(self, _modele, _id):
        return self._compte


class _Compte:
    def __init__(self, hashed_password: str, actif: bool = True):
        self.id = 1
        self.hashed_password = hashed_password
        self.actif = actif
        self.generation_sessions = 0


def _appel(jeton: str, compte: _Compte):
    from app.auth.deps import _get_current_user

    return _get_current_user(access_token=jeton, session=_SessionFactice(compte))


def test_un_jeton_valide_passe():
    compte = _Compte(hash_password("mot-de-passe"))
    jeton = create_access_token({"sub": "1"}, empreinte=empreinte_secret(compte.hashed_password))
    assert _appel(jeton, compte) is compte


def test_un_jeton_emis_avant_le_changement_est_REFUSE():
    """Le cœur du ticket : la fenêtre de 120 minutes se ferme."""
    compte = _Compte(hash_password("ancien"))
    jeton = create_access_token({"sub": "1"}, empreinte=empreinte_secret(compte.hashed_password))
    #  Le mot de passe change — le jeton, lui, est déjà dans la nature.
    compte.hashed_password = hash_password("nouveau")
    with pytest.raises(Exception) as erreur:
        _appel(jeton, compte)
    assert "401" in str(erreur.value) or "invalidée" in str(erreur.value)


def test_un_jeton_sans_empreinte_est_REFUSE():
    """Les jetons émis avant ce lot. Les accepter rouvrirait le trou — et pour
    toujours, le jour où un appelant cesserait de poser l'empreinte."""
    compte = _Compte(hash_password("mot-de-passe"))
    jeton = create_access_token({"sub": "1"})
    with pytest.raises(Exception):
        _appel(jeton, compte)


# ── Un jeton de rafraîchissement rejoué change l'empreinte (#2481) ──────────


def test_la_generation_zero_garde_l_empreinte_d_avant():
    """🔴 Sinon la mise en production de #2481 refusait tous les jetons d'accès en
    cours : la colonne naît à 0 pour tout le monde."""
    condense = hash_password("mot-de-passe")
    assert empreinte_du_compte(condense, 0) == empreinte_secret(condense)


def test_la_generation_change_l_empreinte():
    condense = hash_password("mot-de-passe")
    empreintes = {empreinte_du_compte(condense, g) for g in (0, 1, 2)}
    assert len(empreintes) == 3


def test_un_jeton_emis_avant_le_rejeu_est_REFUSE():
    """La comparaison réelle de `_get_current_user` lit la génération du compte."""
    compte = _Compte(hash_password("mot-de-passe"))
    avant = creer_jeton_acces(1, compte.hashed_password, compte.generation_sessions)
    assert _appel(avant, compte) is compte
    compte.generation_sessions += 1  # ce que fait `fermer_apres_rejeu`
    with pytest.raises(Exception):
        _appel(avant, compte)
    apres = creer_jeton_acces(1, compte.hashed_password, compte.generation_sessions)
    assert _appel(apres, compte) is compte
