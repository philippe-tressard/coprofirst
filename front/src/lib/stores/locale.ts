import { writable } from 'svelte/store';
import { browser } from '$app/env';

export type Locale = 'fr' | 'en';

const saved = browser ? (localStorage.getItem('hostachy_locale') as Locale | null) : null;

// Default to 'fr'; only switch to 'en' if explicitly saved
export const locale = writable<Locale>(saved === 'en' ? 'en' : 'fr');

if (browser) {
	locale.subscribe((v) => localStorage.setItem('hostachy_locale', v));
}

export const NAV_LABELS: Record<Locale, Record<string, string>> = {
	fr: {
		'/tableau-de-bord': 'Accueil',
		'/residence': 'Résidence',
		'/calendrier': 'Calendrier',
		'/tickets': 'Demandes',
		'/mon-lot': 'Mes lots & accès',
		'/sondages': 'Communauté',
		'/idees': 'Boîte à idées',
		'/gouvernance': 'Gouvernance',
		'/prestataires': 'Prestataires',
		'/annuaire': 'Annuaire',
		'/faq': 'FAQ',
		'/espace-cs': 'Espace CS',
		'/admin': 'Paramétrage',
		'/profil': 'Profil',
		deconnexion: 'Déconnexion',
	},
	en: {
		'/tableau-de-bord': 'Home',
		'/residence': 'Building',
		'/calendrier': 'Calendar',
		'/tickets': 'Requests',
		'/mon-lot': 'My units & access',
		'/sondages': 'Participation',
		'/idees': 'Ideas box',
		'/gouvernance': 'Governance',
		'/prestataires': 'Contractors',
		'/annuaire': 'Directory',
		'/faq': 'FAQ',
		'/espace-cs': 'Board space',
		'/admin': 'Settings',
		'/profil': 'Profile',
		deconnexion: 'Sign out',
	},
};
