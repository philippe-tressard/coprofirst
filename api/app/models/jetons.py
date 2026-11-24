"""Les jetons d'authentification — rafraîchissement, mot de passe oublié, e-mail.

## Pourquoi ce module (#833, 08/09/2026)

Extraits de `models/core.py` quand le garde-fou de modularité a refusé de le
laisser grossir (1 066 lignes). Le refus désignait juste : ces trois modèles
n'ont **aucun `Relationship`** et ne référencent aucun autre modèle. C'est ce qui
les rendait déplaçables sans risque — et c'est aussi ce qui montrait qu'ils
n'avaient rien à faire au milieu du patrimoine et des tickets.

Ils accompagnent `routers/auth_mot_de_passe.py` et `routers/auth_telemetrie.py`,
sortis du même fichier pour la même raison.

⚠️ `core.py` les réimporte : `from app.models.core import RefreshToken` reste
valide, et c'est cet import qui enregistre les tables dans les métadonnées
SQLModel. Le retirer ferait disparaître trois tables d'une base neuve — sans
erreur, jusqu'à la première écriture.
"""

from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: NaiveDatetime
    revoked: bool = False
    #: Quand ce jeton a été ÉCHANGÉ contre un autre par `/auth/refresh` — `None`
    #: s'il a été révoqué autrement (déconnexion, mot de passe posé). C'est ce qui
    #: distingue un jeton volé rejoué d'une session fermée : voir
    #: `auth/jetons_rafraichissement.py`.
    remplace_le: Optional[NaiveDatetime] = None
    #: La SESSION de ce jeton : tirée à la connexion, recopiée par chaque rotation,
    #: portée aussi par les jetons d'accès (`sid`). La déconnexion ferme tous les
    #: jetons de la session présentée (migration 0347) ; `None` pour un jeton d'avant.
    session_id: Optional[str] = Field(default=None, index=True)


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: NaiveDatetime
    used: bool = False


class EmailVerificationToken(SQLModel, table=True):
    __tablename__ = "email_verification_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: NaiveDatetime
    used: bool = False
    #: La nouvelle adresse que ce lien CONFIRME (#1549, migration 0247) — `None`
    #: pour le lien de l'inscription, qui vérifie l'adresse du compte. Tant que le
    #: lien n'est pas servi, l'ancienne adresse reste celle du compte :
    #: `utils/verification_adresse.py`.
    nouvelle_adresse: Optional[str] = None


class JetonMontre(SQLModel, table=True):
    """Le jeton d'une montre (Apple Watch, Wear OS) — lecture de la cloche seule (#2771).

    Émis à la demande du téléphone connecté, transmis à la montre par le téléphone.
    Les règles — portée, expiration, révocation — vivent dans `auth/jetons_montre.py`.
    Stocké par son EMPREINTE (#1389) : le brut ne vit que sur la montre.
    """

    __tablename__ = "jeton_montre"
    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="utilisateur.id", index=True)
    empreinte: str = Field(unique=True)
    #: `watchos` ou `wearos` — pour la liste que voit la personne, jamais pour la portée.
    plateforme: str
    #: L'empreinte du compte à l'émission (`auth/jwt.empreinte_du_compte`) : un mot de
    #: passe changé ou une session rejouée fait tomber le jeton, comme un jeton d'accès.
    empreinte_compte: str
    cree_le: NaiveDatetime
    expire_le: NaiveDatetime
    #: La dernière lecture de la cloche par la montre — `None` tant qu'elle n'a rien lu.
    vu_le: Optional[NaiveDatetime] = None
