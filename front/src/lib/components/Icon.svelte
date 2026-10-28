<script lang="ts">
	export let name: string;
	export let size: number = 20;

	//  Les tracés vivent dans `#lib/icones-svg.json`, catalogue commun au site et
	//  aux documents imprimables du serveur (`api/app/utils/icones-svg.json`, copie
	//  octet pour octet, verrouillée par `api/tests/test_icones_svg.py`).
	//
	//  Ils étaient écrits ici, et le serveur ne pouvait donc que les RECOPIER pour
	//  ses PDF — ce qu'il avait déjà fait pour le globe et pour le logo WhatsApp,
	//  celui-là même qu'on avait consolidé le 08/08/2026 parce qu'il était dessiné
	//  six fois avec deux tracés différents. La consolidation n'avait pas franchi la
	//  frontière front/api : le catalogue partagé la fait franchir.
	//
	//  Exception assumée, portée par le tracé lui-même : `whatsapp` n'est pas une
	//  icône Lucide mais une marque. Son `fill` (vert officiel) et son `stroke="none"`
	//  neutralisent les attributs de l'enveloppe <svg> plus bas.
	import icones from '#lib/icones-svg.json';

	const icons = icones as Record<string, string>;
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.5"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{@html icons[name] ?? icons['help-circle']}
</svg>
