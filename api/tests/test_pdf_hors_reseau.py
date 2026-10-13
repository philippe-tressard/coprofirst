"""Le rendu PDF n'ouvre aucune ressource hors du document (#1908).

POURQUOI CE TEST (13/10/2026) :

WeasyPrint ouvre, par défaut, tout ce que le HTML désigne — `http(s)`, `ftp`,
`file` — **depuis le serveur**. Une image `http://192.168.1.x/…` glissée dans un
contenu rendu aurait donc fait sortir une requête de l'API vers le réseau local
des RPi (SSRF), et un `file:///…` lu un fichier du conteneur. Les documents de
ce site sont autonomes (data-URI, `<style>`) : `pdf_rendu.PROTOCOLES_ADMIS` ne
laisse passer que le data-URI.

On le vérifie par le **comportement**, pas par la présence d'un paramètre : un
serveur HTTP témoin, sur cette machine, ne doit recevoir aucune requête pendant
le rendu d'un document qui le désigne. Et l'on prouve d'abord que ce témoin sait
compter — un serveur qui ne reçoit rien parce qu'il n'écoute pas rendrait ce test
vert pour toujours (`standards/04-fiabilite-des-controles.md` §2, le cas zéro).
"""

import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.aides_pdf import besoin_weasyprint

#: Une image PNG d'un pixel : la ressource que le rendu DOIT continuer d'ouvrir.
PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def serveur_temoin():
    """Un serveur HTTP local qui compte les requêtes reçues."""
    recues: list[str] = []

    class _Gestionnaire(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — nom imposé par http.server
            recues.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()

        def log_message(self, *_args):  # silence : le journal du test suffit
            pass

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Gestionnaire)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    try:
        yield f"http://127.0.0.1:{serveur.server_address[1]}", recues
    finally:
        serveur.shutdown()
        serveur.server_close()


def test_le_serveur_temoin_compte_ce_qu_il_recoit(serveur_temoin):
    """Le cas zéro : sans lui, « aucune requête reçue » ne prouverait rien."""
    adresse, recues = serveur_temoin
    with urllib.request.urlopen(f"{adresse}/sonde", timeout=5):  # noqa: S310
        pass
    assert recues == ["/sonde"]


@besoin_weasyprint
def test_une_ressource_http_n_est_jamais_ouverte(serveur_temoin):
    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    adresse, recues = serveur_temoin
    html = (
        f'<html><head><link rel="stylesheet" href="{adresse}/feuille.css"></head>'
        f'<body><p>Contenu.</p><img src="{adresse}/image.png" alt=""></body></html>'
    )

    contenu = html_to_pdf(html)

    assert contenu[:5] == b"%PDF-", "le document doit se rendre, sans la ressource"
    assert recues == [], f"le rendu PDF a ouvert le réseau : {recues}"
    #  Le refus doit être la RAISON de l'absence de requête — pas un document
    #  que le moteur n'aurait pas lu.
    refus = [m for _n, _niv, m in pdf_rendu.dernier_journal if "disallowed protocol" in m]
    assert refus, (
        "aucun refus de protocole au journal : la ressource n'a pas été demandée, "
        f"ce test ne mesure plus rien. Journal : {pdf_rendu.dernier_journal[-5:]}"
    )


@besoin_weasyprint
def test_un_fichier_local_n_est_jamais_lu():
    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    html_to_pdf('<html><body><img src="file:///etc/hostname" alt=""></body></html>')

    assert any(
        "disallowed protocol" in m and "file:" in m for _n, _niv, m in pdf_rendu.dernier_journal
    ), f"file:// n'a pas été refusé. Journal : {pdf_rendu.dernier_journal[-5:]}"


@besoin_weasyprint
def test_une_image_en_data_uri_se_rend_toujours():
    """La restriction ne doit pas emporter ce dont les documents vivent."""
    from app.utils import pdf_rendu
    from app.utils.pdf_theme import html_to_pdf

    html_to_pdf(f'<html><body><img src="{PIXEL_PNG}" alt=""></body></html>')

    echecs = [m for _n, _niv, m in pdf_rendu.dernier_journal if "Failed to load" in m]
    assert echecs == [], f"un data-URI n'a pas été chargé : {echecs}"
