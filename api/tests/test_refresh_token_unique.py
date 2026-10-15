"""Deux jetons de rafraîchissement émis dans la même seconde sont DIFFÉRENTS.

## L'incident (19/08/2026, trouvé par le point 6 du pré-check)

```
IntegrityError: UNIQUE constraint failed: refresh_token.token
POST /auth/refresh HTTP/1.1" 500 Internal Server Error
```

Le contenu du jeton était entièrement déterministe — `{"sub": …, "exp": …,
"type": "refresh"}` — et `exp` a une résolution d'**une seconde**. Deux
rafraîchissements du même utilisateur dans la même seconde produisaient donc deux
JWT identiques octet pour octet, et la colonne `refresh_token.token` est UNIQUE.

🔴 **Ce n'était pas un cas de bord.** Quand une page charge, plusieurs appels
reçoivent 401 en même temps et déclenchent chacun un rafraîchissement : sur les
dernières 24 h de production, **4 collisions pour 4 appels** — la totalité.

## Pourquoi ce test et pas seulement le correctif

Le `jti` est invisible : rien à l'écran ne dit qu'il est là, et le retirer ne
casserait aucun autre test. Le défaut reviendrait donc silencieusement, et ne se
verrait qu'en production — comme cette fois-ci, où il a fallu qu'un contrôle
lise les journaux d'un serveur pour le découvrir (`standards/05` §1).

⚠️ Le test compare **deux jetons émis à la suite**, sans figer l'horloge. C'est
volontaire : figer le temps testerait le test, pas le jeton. Sur une machine
assez lente pour que la seconde change entre les deux appels, l'assertion resterait
vraie — mais elle ne prouverait plus rien. D'où le troisième test, qui vérifie la
propriété *par construction* : le `jti` est présent et il diffère.
"""

from __future__ import annotations

from app.auth.jwt import create_access_token, create_refresh_token, decode_token


def test_deux_jetons_de_rafraichissement_successifs_different():
    """Le cas exact du 500 : deux émissions rapprochées pour le même utilisateur."""
    a = create_refresh_token({"sub": "42"})
    b = create_refresh_token({"sub": "42"})
    assert a != b, (
        "Deux jetons de rafraîchissement identiques : la contrainte UNIQUE de "
        "`refresh_token.token` refusera le second, et `/auth/refresh` répondra 500."
    )


def test_le_jeton_porte_un_jti_unique():
    """La propriété par construction, indépendante de la vitesse de la machine.

    C'est ce test qui tient si l'horloge avance entre deux appels — l'autre
    passerait alors pour une raison qui n'est pas celle qu'on veut vérifier.
    """
    charges = [decode_token(create_refresh_token({"sub": "42"})) for _ in range(5)]
    for charge in charges:
        assert charge is not None and charge.get("jti"), (
            "Le jeton de rafraîchissement ne porte pas de `jti` : son contenu "
            "redevient déterministe, et deux émissions dans la même seconde "
            "entrent de nouveau en collision."
        )
    jtis = {c["jti"] for c in charges}
    assert len(jtis) == 5, f"jti non uniques : {jtis}"


def test_le_jeton_reste_decodable_et_typé():
    """Le correctif ne change rien à ce que le jeton dit de lui-même.

    `refresh()` refuse tout jeton dont `type` n'est pas « refresh » : casser cela
    déconnecterait tout le monde au prochain déploiement, sans message.
    """
    charge = decode_token(create_refresh_token({"sub": "7"}))
    assert charge is not None
    assert charge["type"] == "refresh"
    assert charge["sub"] == "7"
    assert "exp" in charge


def test_le_jeton_d_acces_n_a_PAS_de_jti():
    """Et c'est délibéré — le vérifier empêche une symétrie coûteuse et inutile.

    Le jeton d'accès n'est stocké nulle part : aucune contrainte d'unicité ne le
    concerne. Lui ajouter un `jti` « pour faire pareil » rallongerait chaque
    en-tête de chaque requête sans rien protéger.
    """
    charge = decode_token(create_access_token({"sub": "7"}))
    assert charge is not None
    assert "jti" not in charge, (
        "Le jeton d'accès porte un `jti` : il n'est pas stocké, donc rien ne peut "
        "entrer en collision — c'est du poids ajouté à chaque requête pour rien."
    )
