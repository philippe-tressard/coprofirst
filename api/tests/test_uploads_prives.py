"""Garde-fou : les fichiers privés ne doivent jamais être servis en statique.

`/uploads/*` est publié par Caddy **sans authentification**. Jusqu'au 03/08/2026,
`documents.py` et `diagnostics.py` écrivaient à la racine de ce volume : 48
fichiers — PV d'assemblée générale, plan pluriannuel de travaux, modification du
règlement de copropriété, rapports de diagnostic — étaient accessibles à qui
connaissait l'URL. Leur endpoint de téléchargement applique pourtant un contrôle
d'accès à trois couches (`document_visible`) : l'URL statique le contournait
entièrement.

Deux conditions doivent tenir ensemble, et aucune ne se suffit :

1. le code écrit ces fichiers sous `stockage.DOSSIER_PRIVE`, pas à la racine —
   par `fichiers.enregistrer_televersement`, seule écriture d'un fichier privé ;
2. le `Caddyfile` refuse `/uploads/prive/*`, **avant** le service statique —
   Caddy applique le premier `handle` qui correspond, une directive placée après
   ne servirait à rien.

Le second point est un piège classique : la protection tient à l'**ordre** de
deux blocs, ce qu'aucune relecture rapide ne vérifie.
"""

import os
import pathlib
import re

import pytest

from tests.aides_caddy import bloc_handle, blocs_handle, caddyfile

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _routeurs_prives() -> tuple:
    """Les routeurs qui écrivent un fichier privé — DÉDUITS, pas listés.

    🔴 La liste était écrite à la main, et elle a dérivé au premier découpage :
    le 29/08/2026, les relevés de compteurs sont sortis de `prestataires.py`
    vers `compteurs.py` et ont emporté l'écriture de fichiers avec eux. Le
    contrôle a continué de fouiller l'ancien module — il a échoué, ce qui est le
    bon comportement, mais une liste qui doit être corrigée à chaque
    réorganisation finit par l'être en la raccourcissant.

    ⚠️ « La portée du contrôle fait partie du contrôle » (`standards/05` §9) :
    un routeur créé demain qui écrit un fichier privé entre ici tout seul.
    """
    routeurs = sorted(
        f.name
        for f in (RACINE / "api" / "app" / "routers").glob("*.py")
        #  Depuis #1748, l'écriture privée a UNE porte : `enregistrer_televersement`.
        if "enregistrer_televersement(" in f.read_text(encoding="utf-8")
    )
    #  Cas zéro : aucun routeur trouvé ⇒ le glob ou le motif a changé, et tous
    #  les tests qui s'appuient dessus passeraient au vert SANS RIEN VÉRIFIER.
    assert routeurs, "aucun routeur privé trouvé — contrôle impossible, pas vert"
    return tuple(routeurs)


ROUTEURS_PRIVES = _routeurs_prives()


def test_le_repertoire_prive_est_refuse_par_caddy():
    contenu = caddyfile()
    assert re.search(r"handle\s+/uploads/prive/\*\s*\{[^}]*respond\s+404", contenu), (
        "Le Caddyfile ne refuse plus /uploads/prive/* : les PV d'AG et les "
        "rapports de diagnostic redeviennent téléchargeables sans authentification."
    )


def test_le_refus_precede_le_service_statique():
    """L'ordre EST la protection : Caddy applique le premier `handle` qui matche."""
    contenu = caddyfile()
    prive = contenu.find("handle /uploads/prive/*")
    statique = re.search(r"handle\s+/uploads/\*\s*\{", contenu)

    assert prive != -1, "bloc /uploads/prive/* introuvable"
    assert statique, "bloc /uploads/* introuvable — le Caddyfile a changé de forme"
    assert prive < statique.start(), (
        "Le refus de /uploads/prive/* est placé APRÈS le service statique : "
        "Caddy sert les fichiers avant de l'atteindre, la protection est inerte."
    )


def test_les_annonces_de_hall_restent_protegees():
    """Même mécanisme, antérieur : une régression d'ordre les toucherait aussi."""
    contenu = caddyfile()
    hall = contenu.find("handle /uploads/annonces-hall/*")
    statique = re.search(r"handle\s+/uploads/\*\s*\{", contenu)
    assert hall != -1 and statique and hall < statique.start()


@pytest.mark.parametrize("routeur", ROUTEURS_PRIVES)
def test_les_routeurs_prives_n_ecrivent_plus_a_la_racine(routeur):
    """Un fichier privé posé à la racine serait servi malgré le Caddyfile."""
    source = (RACINE / "api" / "app" / "routers" / routeur).read_text(encoding="utf-8")

    assert "enregistrer_televersement(" in source, f"{routeur} n'écrit plus par la porte privée"
    fautifs = re.findall(r"os\.path\.join\(\s*UPLOADS_DIR\s*,|racine_fichiers", source)
    assert not fautifs, (
        f"{routeur} construit encore un chemin depuis la racine du volume servi "
        f"({len(fautifs)} occurrence(s)) : passer par `enregistrer_televersement`."
    )


def test_un_fichier_prive_s_ecrit_sous_le_dossier_prive(disque_jetable):
    """Le comportement, pas la forme : le fichier ATTERRIT sous `prive/`."""
    import io
    from types import SimpleNamespace

    from app.utils.fichiers import enregistrer_televersement
    from app.utils.stockage import DOSSIER_PRIVE, stockage

    recu = SimpleNamespace(file=io.BytesIO(b"%PDF-1.7 essai"), content_type="application/pdf")
    #  La porte rend la CLÉ (#1816) ; le fichier est sous la racine du stockage.
    cle = enregistrer_televersement(recu, "pv-ag.pdf")
    chemin = stockage().chemin(cle)
    assert cle.startswith(f"{DOSSIER_PRIVE}/")
    assert chemin.is_file() and chemin.read_bytes() == b"%PDF-1.7 essai"
    assert chemin.parent == (disque_jetable / DOSSIER_PRIVE).resolve()


def test_le_repertoire_prive_est_bien_sous_le_volume_repliqué():
    """Un volume dédié serait absent de bascule.sh et de backup.py.

    `bascule.sh` réplique `5hostachy_uploads` par son NOM, `backup.py` archive
    `/app/uploads` par son CHEMIN. Sortir les fichiers de cette arborescence les
    priverait des deux — perte à la première bascule.
    """
    from app.utils.stockage import DOSSIER_PRIVE, cle_valide, stockage

    #  Une CLÉ relative, donc sous la racine par construction (`stockage.chemin`).
    assert cle_valide(DOSSIER_PRIVE) == DOSSIER_PRIVE
    racine = os.getenv("UPLOADS_DIR", "/app/uploads")
    assert os.path.normpath(stockage().racine) == os.path.normpath(racine)

    bascule = (RACINE / "scripts" / "exploitation" / "bascule.sh").read_text(encoding="utf-8")
    assert "5hostachy_uploads" in bascule, "bascule.sh ne réplique plus ce volume"
    backup = (RACINE / "api" / "app" / "utils" / "backup.py").read_text(encoding="utf-8")
    assert "tar.add(uploads" in backup and "stockage().racine" in backup, (
        "backup.py n'archive plus la racine du stockage"
    )


# ── forward_auth : le reste de /uploads exige une session ────────────────────


def test_uploads_exige_une_session_authentifiee():
    """Photos de profil, de ticket et pièces jointes ne sont plus publiques."""
    contenu = caddyfile()
    bloc = bloc_handle(contenu, "/uploads/*")
    assert bloc, "bloc /uploads/* introuvable"
    assert "forward_auth" in bloc, (
        "Le service statique de /uploads/* ne passe plus par forward_auth : "
        "toutes les pièces jointes redeviennent publiques."
    )
    assert "/auth/verifier-acces" in bloc, (
        "forward_auth n'interroge plus l'endpoint de vérification attendu"
    )


def _blocs_uploads(contenu: str) -> list[tuple[str, str]]:
    """Chaque `handle /uploads…` du Caddyfile : (chemin, corps du bloc)."""
    return blocs_handle(contenu, r"/uploads/\S*")


def _servis_sans_session(blocs) -> list[str]:
    return [
        chemin for chemin, corps in blocs if "file_server" in corps and "forward_auth" not in corps
    ]


def test_aucun_fichier_televerse_n_est_servi_sans_session():
    """Un bloc qui sert des fichiers téléversés passe par `forward_auth` — sans exception.

    `/uploads/publications/*` a été servi en anonyme jusqu'au 30/09/2026 (#1494),
    au motif que le bridge WhatsApp allait y chercher les images sans cookie. Ce
    motif a disparu le 10/08/2026 (envoi en base64, `utils/whatsapp_media.py`) ;
    l'exposition, elle, a survécu sept semaines — et un test la DÉFENDAIT, parce
    qu'il vérifiait la conséquence d'une raison sans vérifier la raison.

    Un bloc placé avant la règle commune ne peut donc que REFUSER (`respond`).
    """
    fautes = _servis_sans_session(_blocs_uploads(caddyfile()))
    assert not fautes, (
        f"Servi sans session : {fautes}. Un fichier téléversé se lit derrière "
        "`forward_auth` (bloc /uploads/*) ; un bloc qui le précède ne sert qu'à refuser."
    )


def test_le_controle_des_blocs_uploads_voit_et_refuse():
    """Cas zéro : il lit bien les blocs du vrai Caddyfile, et il refuse un service anonyme."""
    blocs = dict(_blocs_uploads(caddyfile()))
    assert "/uploads/*" in blocs and "forward_auth" in blocs["/uploads/*"], (
        "le bloc protégé /uploads/* n'est plus lu : le contrôle ne mesure plus rien"
    )
    forge = "\thandle /uploads/ouvert/* {\n\t\troot * /srv\n\t\tfile_server\n\t}"
    assert _servis_sans_session(_blocs_uploads(forge)) == ["/uploads/ouvert/*"]


def test_l_endpoint_de_verification_existe_et_reste_authentifie():
    """Un endpoint qui cesserait d'exiger une session rendrait forward_auth inerte."""
    source = (RACINE / "api" / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    bloc = re.search(
        r'@router\.get\("/verifier-acces".*?\ndef verifier_acces\((.*?)\)', source, re.S
    )
    assert bloc, "l'endpoint /auth/verifier-acces a disparu — forward_auth pointe dans le vide"
    assert "get_current_user" in bloc.group(1), (
        "verifier_acces ne dépend plus de get_current_user : il répondrait 204 "
        "à tout le monde, et forward_auth n'empêcherait plus rien."
    )


def test_les_fichiers_proteges_ne_sont_pas_mis_en_cache_par_le_cdn():
    """Sans cette directive, `forward_auth` ne protège rien.

    Cloudflare met en cache les extensions statiques (.pdf, .jpg…) par défaut.
    Le premier accès AUTORISÉ peuple donc l'edge, qui sert ensuite le fichier à
    tout le monde sans jamais revenir à l'origine.

    Constaté le 03/08/2026, quelques minutes après la mise en production de
    forward_auth : sur une pièce jointe de ticket, l'origine répondait 401 et
    l'edge 200, avec `CF-Cache-Status: HIT` et `Age: 344`. Le contrôle était
    parfaitement fonctionnel — et parfaitement inutile.

    Une purge du cache ne suffit pas : le premier accès autorisé suivant
    repeuple l'edge. Seule la directive à l'origine règle le problème.
    """
    contenu = caddyfile()
    bloc = bloc_handle(contenu, "/uploads/*")
    assert bloc, "bloc /uploads/* introuvable"

    directive = re.search(r'header\s+Cache-Control\s+"([^"]+)"', bloc)
    assert directive, (
        "Le bloc protégé n'impose plus de Cache-Control : Cloudflare remettra "
        "les pièces jointes en cache et les servira sans authentification."
    )
    valeur = directive.group(1).lower()
    assert "private" in valeur or "no-store" in valeur, (
        f"Cache-Control « {directive.group(1)} » n'interdit pas le stockage par "
        "un cache partagé — une réponse qui dépend d'un cookie ne doit être "
        "conservée nulle part."
    )


# ── Fichiers de prestataires : autorisation, pas seulement authentification ──


def test_les_fichiers_de_prestataires_exigent_le_role_cs():
    """`forward_auth` ne vérifie qu'une session — pas le rôle.

    Devis, ordres de service, conditions d'assurance et relevés de compteur ne
    s'affichent que dans un écran réservé au conseil syndical. Tant qu'ils
    étaient servis en statique, tout résident disposant de l'URL pouvait les
    lire : authentifié n'est pas autorisé. Servis par un endpoint, ils héritent
    enfin de `require_cs_or_admin`.
    """
    source = (RACINE / "api" / "app" / "routers" / "compteurs.py").read_text(encoding="utf-8")

    #  ⚠️ `/devis/{d_id}/fichier/{nom}` est parti avec la prestation ponctuelle
    #  (#603). Le contrôle NE PERD RIEN : il portait sur deux endpoints qui
    #  partagent `_servir_fichier_prive`, et c'est cette fonction — donc la
    #  validation d'appartenance — qui est l'objet réel du test.
    for endpoint in ("/releves/{r_id}/photo/{nom}",):
        assert f'@router.get("{endpoint}")' in source, (
            f"L'endpoint {endpoint} a disparu : les URLs stockées en base "
            "pointent dans le vide et les pièces jointes deviennent illisibles."
        )

    bloc = source[source.index("def _servir_fichier_prive") :]
    assert "require_cs_or_admin" in source[source.index("download_photo_releve") - 400 :], (
        "Le téléchargement des photos de relevé n'exige plus le rôle CS/admin."
    )
    assert "noms_autorises" in bloc, "la validation d'appartenance a disparu"


def test_un_endpoint_prestataire_ne_peut_pas_servir_un_pv_dag():
    """`prive/` contient AUSSI les PV d'AG et les diagnostics.

    Un endpoint qui servirait un nom arbitraire depuis ce répertoire
    contournerait le contrôle d'accès à trois couches de la bibliothèque
    documentaire. La validation par appartenance à la ressource est donc une
    condition de sécurité, pas une commodité — et un `basename` ne suffit pas.
    """
    source = (RACINE / "api" / "app" / "routers" / "compteurs.py").read_text(encoding="utf-8")

    assert "if nom not in noms_autorises:" in source, (
        "La vérification d'appartenance a été retirée : l'endpoint peut servir "
        "n'importe quel fichier de prive/, PV d'assemblée générale compris."
    )
    # Les noms proposés viennent des colonnes de la ressource, jamais de l'URL.
    assert "os.path.basename(r.photo_url)" in source


def test_les_urls_stockees_pointent_vers_les_endpoints_authentifies():
    """Le front lit ces URLs depuis la base : elles font foi.

    Si le code réécrivait `/uploads/…`, les fichiers seraient à nouveau demandés
    en statique — donc introuvables (ils sont dans `prive/`), et l'affichage
    casserait sans erreur serveur.
    """
    source = (RACINE / "api" / "app" / "routers" / "compteurs.py").read_text(encoding="utf-8")

    fautifs = re.findall(r'f"/uploads/\{[^"]*\}"', source)
    assert not fautifs, f"{len(fautifs)} URL(s) publique(s) encore écrite(s) en base : {fautifs}"
    assert "/api/prestataires/releves/" in source


def test_les_urls_de_fichiers_portent_le_nom_du_fichier():
    """Une URL qui sert à RETROUVER un fichier doit contenir son nom.

    La 0125 a stocké `/api/prestataires/releves/{id}/photo` — sans nom — alors
    que l'endpoint dérivait le nom de cette même URL. `basename` rendait
    « photo », et la migration avait écrasé la seule copie du vrai nom : toutes
    les photos de relevé sont devenues introuvables en production, une heure
    après la mise en service. Réparé par la 0126, à partir de la base du standby.

    La leçon tient en une phrase : **ne pas écraser la seule copie d'une donnée
    par une valeur qui en dépend**. Le circuit était fermé sur lui-même.
    """
    source = (RACINE / "api" / "app" / "routers" / "compteurs.py").read_text(encoding="utf-8")

    urls = re.findall(r'= f"(/api/prestataires/[^"]+)"', source)
    assert urls, "aucune URL de fichier construite — le module a changé de forme"
    for url in urls:
        assert url.rstrip("/").endswith("}"), (
            f"L'URL « {url} » ne se termine pas par un segment variable : si "
            "c'est le nom du fichier qui manque, l'endpoint ne pourra pas le "
            "retrouver et la donnée d'origine sera perdue."
        )
        assert "basename(cle)" in source, "le nom du fichier n'est plus injecté dans l'URL stockée"


def test_l_api_entiere_est_non_cacheable():
    """Le bloc /uploads/* ne suffit pas : les fichiers passent AUSSI par /api/*.

    Cloudflare met en cache d'après l'extension de l'URL. Les endpoints de
    téléchargement en portent une (`…/photo/x.png`, `…/fichier/y.pdf`) : le
    premier accès autorisé peuple l'edge, qui sert ensuite le fichier à tout le
    monde.

    Le défaut s'est produit DEUX FOIS le 03/08/2026 — sur `/uploads/*` le matin,
    puis sur `/api/*` l'après-midi, parce que la directive n'avait été posée que
    sur le premier bloc. La règle est écrite dans `standards/03-securite.md` §6 ;
    ce test est ce qui la rend applicable ici.

    Appliqué à TOUT `/api/*` volontairement : une réponse d'API dépend d'une
    session par nature, et la prochaine route qui servira un fichier n'aura pas
    à y penser.
    """
    contenu = caddyfile()
    bloc = bloc_handle(contenu, "/api/*")
    assert bloc, "bloc /api/* introuvable"

    directive = re.search(r'header\s+Cache-Control\s+"([^"]+)"', bloc)
    assert directive, (
        "Le bloc /api/* n'impose plus de Cache-Control : tout endpoint servant "
        "un fichier avec une extension redeviendra public via le cache du CDN."
    )
    valeur = directive.group(1).lower()
    assert "private" in valeur or "no-store" in valeur, (
        f"Cache-Control « {directive.group(1)} » n'interdit pas le stockage par un cache partagé."
    )


# ── #2158 : l'API ne sert aucun fichier téléversé sans session ───────────────


@pytest.mark.parametrize("methode", ["GET", "HEAD"])
def test_l_api_ne_sert_aucun_fichier_televerse_sans_session(methode, disque_jetable):
    """Un montage `StaticFiles` répondait 200 à `HEAD /uploads/prive/…` (#2158).

    La route de fichiers ne déclare que GET : le HEAD retombait sur le montage,
    qui rendait la taille et la date d'un document privé. Le fichier existe ici,
    sur le disque jetable : un refus ne vient pas de son absence.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    (disque_jetable / "prive").mkdir(exist_ok=True)
    (disque_jetable / "prive" / "pv.pdf").write_bytes(b"%PDF-1.4 confidentiel")
    reponse = TestClient(app).request(methode, "/uploads/prive/pv.pdf")
    assert reponse.status_code >= 400, (methode, reponse.status_code, dict(reponse.headers))
    assert "content-length" not in reponse.headers or reponse.headers["content-length"] != "21"
