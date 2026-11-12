"""Un e-mail TRANSACTIONNEL ne se laisse jamais couper par une préférence.

## Pourquoi ce contrôle existe (10/09/2026, #873)

La migration 0187 honore enfin le refus de notifications des comptes qui avaient
décoché la case d'inscription : leurs préférences passent à « aucun e-mail ».
C'est ce que Philippe a arbitré, et c'est juste.

🔴 **Mais `mail_autorise(user, None)` — le cas d'un envoi qui ne vise aucun
bâtiment — répond `mon_batiment_mail`.** Si un envoi transactionnel passait un
`destinataire_id`, un compte basculé perdrait du même coup son **mot de passe
oublié** et sa **validation de compte** : il ne pourrait plus jamais entrer.
Couper un accès en croyant respecter un consentement serait le mauvais côté de
l'erreur — bien pire que le défaut qu'on corrige.

Aujourd'hui aucun ne le fait, et c'est ce qui rend la bascule sûre. Ce test le
**vérifie** au lieu de le supposer, et refuse qu'on l'ajoute demain : la
préférence n'est consultée par `send_email` que si un `destinataire_id` lui est
passé (`utils/email/__init__.py`).

⚠️ Ce n'est pas un contrôle sur le nom du modèle mais sur le **geste** : on
cherche, dans l'arbre syntaxique, les appels qui envoient l'un de ces codes, et
on regarde s'ils portent l'argument qui déclenche la préférence.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

#: Les codes dont la remise conditionne l'ACCÈS au compte. Un e-mail que
#: l'utilisateur ne peut pas remplacer par un autre chemin.
#: L'avis de changement d'adresse en est (#1549) : c'est l'alerte d'un compte
#: qu'on détourne, et un refus de notifications ne doit pas la faire taire.
#: L'avertissement de purge en est aussi (#1580) : un compte qui a coupé ses
#: notifications serait sinon supprimé sans avoir été prévenu.
TRANSACTIONNELS = {
    "reinitialisation_mdp",
    "verification_email",
    "adresse_changement_avis",
    "compte_inactif_avertissement",
    #  La suppression de son compte (#2699) : l'accusé prévient le titulaire d'un
    #  compte volé ; le dernier part quand le compte n'existe plus.
    "suppression_compte_demandee",
    "suppression_compte_effectuee",
}


def _appels_avec_code(arbre: ast.AST):
    """Tout appel portant un `code=` littéral, avec ses mots-clés."""
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        mots = {k.arg: k.value for k in noeud.keywords if k.arg}
        code = mots.get("code")
        if isinstance(code, ast.Constant) and isinstance(code.value, str):
            yield code.value, mots


def test_aucun_envoi_transactionnel_ne_passe_de_destinataire_id():
    fautes = []
    vus = set()
    for m in modules_app():
        for code, mots in _appels_avec_code(m.arbre):
            if code not in TRANSACTIONNELS:
                continue
            vus.add(code)
            if "destinataire_id" in mots:
                fautes.append(f"{m.rel} — code={code!r}")

    assert not fautes, (
        "Envoi transactionnel soumis aux préférences du destinataire :\n  "
        + "\n  ".join(fautes)
        + "\n\n  Un compte dont les notifications sont coupées (migration 0187)\n"
        "  ne recevrait plus son mot de passe oublié : il ne pourrait plus entrer.\n"
        "  Retirer `destinataire_id` — ces envois ne sont pas des notifications."
    )
    #  Cas zéro : si plus aucun de ces codes n'était envoyé, le test passerait
    #  en ne mesurant rien.
    assert vus == TRANSACTIONNELS, (
        f"Codes transactionnels introuvables dans app/ : {TRANSACTIONNELS - vus}. "
        "Renommés ? Le contrôle ne mesure plus ce qu'il croit."
    )
