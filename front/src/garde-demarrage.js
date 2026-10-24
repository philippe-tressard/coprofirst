/*
 *  Garde de démarrage (#1993) — servi INLINE dans chaque page, premier script de
 *  <head> : une page qui ne se dessine pas se recharge une fois, puis dit quoi
 *  faire. Pourquoi et comment : `src/lib/garde-demarrage.ts`. La CSP l'admet par
 *  le condensat de CE fichier (`svelte.config.js`) : le modifier suffit.
 */
(function () {
	var DESSIN_MS = 10000;
	var DEMARRAGE_MS = 20000;
	// Un rechargement automatique au plus par fenêtre : jamais de boucle.
	var FENETRE_RECHARGEMENT_MS = 5 * 60 * 1000;
	var CLE = 'garde-demarrage-recharge-le';
	// Le motif du rechargement de secours, lu par l'application une fois démarrée
	// pour le signaler au journal des erreurs (`$lib/garde-demarrage`).
	var CLE_MOTIF = 'garde-demarrage-motif';
	var NON_DESSINEE = 'non-dessinee';
	var NON_DEMARREE = 'non-demarree';
	var NON_STYLEE = 'non-stylee';
	// Posée par la feuille principale (`styles/socle.css`) : absente du style
	// calculé, la page s'affiche sans sa mise en forme.
	var TEMOIN_FEUILLE = '--feuille-principale';

	var racine = document.documentElement;
	/** @type {ReturnType<typeof setTimeout> | undefined} */
	var minuteur;
	/** @type {HTMLDivElement | null} */
	var message = null;

	function demarree() {
		return racine.getAttribute('data-application') === 'demarree';
	}

	function dessinee() {
		var perf = window.performance;
		// Sans mesure du dessin (navigateur ancien), rien n'est établi : on se tait.
		if (!perf || !perf.getEntriesByName || !window.PerformanceObserver) return true;
		var types = PerformanceObserver.supportedEntryTypes || [];
		if (types.indexOf('paint') < 0) return true;
		return perf.getEntriesByName('first-contentful-paint').length > 0;
	}

	function stylee() {
		if (!window.getComputedStyle) return true; // rien n'est établi : on se tait
		return getComputedStyle(racine).getPropertyValue(TEMOIN_FEUILLE).trim() !== '';
	}

	function rechargeRecente() {
		try {
			var le = Number(sessionStorage.getItem(CLE) || 0);
			return Date.now() - le < FENETRE_RECHARGEMENT_MS;
		} catch {
			return true; // stockage refusé : on ne sait pas compter, donc on ne recharge pas
		}
	}

	/** @param {string} motif */
	function recharger(motif) {
		try {
			sessionStorage.setItem(CLE, String(Date.now()));
			sessionStorage.setItem(CLE_MOTIF, motif);
		} catch {
			/* le rechargement part quand même */
		}
		var parti = false;
		var partir = function () {
			if (parti) return;
			parti = true;
			location.reload();
		};
		// Désinscrit, le service worker ne sert plus le rechargement — comme
		// Ctrl+Maj+R. Il se réinscrit à l'ouverture suivante (`MajDisponible`).
		var sw = navigator.serviceWorker;
		if (sw && sw.getRegistrations) {
			sw.getRegistrations()
				.then(function (inscrits) {
					return Promise.all(
						inscrits.map(function (r) {
							return r.unregister();
						}),
					);
				})
				.then(partir, partir);
			setTimeout(partir, 1500);
		} else partir();
	}

	/** Une feuille de `<head>` qui ne répond pas retient tout le dessin : on la lâche. */
	function lacherLesFeuillesEnAttente() {
		var liens = document.querySelectorAll('link[rel="stylesheet"]');
		for (var i = 0; i < liens.length; i++) {
			var lien = /** @type {HTMLLinkElement} */ (liens[i]);
			if (!lien.sheet) lien.remove();
		}
	}

	/** @param {string} titre @param {string} consigne @param {string} motif */
	function dire(titre, consigne, motif) {
		if (message || !document.body) return;
		message = document.createElement('div');
		message.setAttribute('role', 'alert');
		message.className = 'alert alert-error';
		var t = document.createElement('p');
		var gras = document.createElement('strong');
		gras.textContent = titre;
		t.appendChild(gras);
		var c = document.createElement('p');
		c.textContent = consigne;
		var bouton = document.createElement('button');
		bouton.type = 'button';
		bouton.className = 'btn btn-primary';
		bouton.textContent = 'Recharger la page';
		bouton.addEventListener('click', function () {
			recharger(motif);
		});
		message.appendChild(t);
		message.appendChild(c);
		message.appendChild(bouton);
		document.body.insertBefore(message, document.body.firstChild);
	}

	function constater() {
		minuteur = undefined;
		if (demarree()) return;
		if (!dessinee()) {
			if (!rechargeRecente()) return recharger(NON_DESSINEE);
			lacherLesFeuillesEnAttente();
			dire(
				'Cette page ne s’affiche pas.',
				'Rechargez-la — sur un ordinateur, Ctrl+Maj+R (Cmd+Maj+R sur Mac). ' +
					'Dans l’application installée, ' +
					'fermez-la puis rouvrez-la.',
				NON_DESSINEE,
			);
			return;
		}
		// Dessinée : le constat suivant porte sur le démarrage, plus tard.
		armer(DEMARRAGE_MS - DESSIN_MS, function () {
			minuteur = undefined;
			if (demarree()) return;
			dire(
				'L’application n’a pas fini de se charger.',
				'Rechargez la page. Si cela se reproduit, fermez l’application puis rouvrez-la.',
				NON_DEMARREE,
			);
		});
	}

	/** @param {number} delai @param {() => void} action */
	function armer(delai, action) {
		clearTimeout(minuteur);
		minuteur = setTimeout(action, delai);
	}

	/**
	 *  Une page affichée SANS sa feuille principale (24/10/2026) : une tablette
	 *  rouverte le lendemain montrait la page brute, liens soulignés sur fond
	 *  blanc — une page d'avant une MEP dont les feuilles, aux noms hachés,
	 *  n'existent plus. Elle est dessinée, parfois même démarrée : les deux
	 *  constats ci-dessus se taisaient. Jugé au chargement complet, au retour
	 *  sur l'onglet et à la restauration depuis le cache de navigation — et
	 *  après le démarrage aussi, la page restaurée l'étant souvent déjà.
	 */
	function verifierFeuilles() {
		if (message || document.readyState !== 'complete') return;
		if (document.visibilityState === 'hidden' || stylee()) return;
		if (!rechargeRecente()) return recharger(NON_STYLEE);
		dire(
			'Cette page s’affiche sans sa mise en forme.',
			'Rechargez-la — sur un ordinateur, Ctrl+Maj+R (Cmd+Maj+R sur Mac). ' +
				'Dans l’application installée, fermez-la puis rouvrez-la.',
			NON_STYLEE,
		);
	}

	window.addEventListener('load', verifierFeuilles);
	window.addEventListener('pageshow', verifierFeuilles);
	document.addEventListener('visibilitychange', verifierFeuilles);

	// Le décompte ne court que pendant que l'onglet est visible.
	function surVisibilite() {
		if (demarree() || message) return;
		if (document.visibilityState === 'hidden') {
			clearTimeout(minuteur);
			minuteur = undefined;
		} else if (!minuteur) armer(DESSIN_MS, constater);
	}

	document.addEventListener('visibilitychange', surVisibilite);
	surVisibilite();

	// L'application démarre après le message : il n'a plus lieu d'être.
	if (window.MutationObserver) {
		new MutationObserver(function (_changements, observateur) {
			if (!demarree()) return;
			clearTimeout(minuteur);
			document.removeEventListener('visibilitychange', surVisibilite);
			if (message) message.remove();
			observateur.disconnect();
		}).observe(racine, { attributes: true, attributeFilter: ['data-application'] });
	}
})();
