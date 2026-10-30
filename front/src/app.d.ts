// Types du module virtuel `virtual:pwa-register` (vite-plugin-pwa), utilisé par
// `#lib/components/MajDisponible.svelte`.
/// <reference types="vite-plugin-pwa/client" />

//  La configuration du site lue par `hooks.server.ts` pour une page (palette,
//  #2379), reprise par le layout racine sans seconde requête.
declare global {
	namespace App {
		interface Locals {
			siteConfig?: Record<string, string>;
		}
	}
}

export {};
