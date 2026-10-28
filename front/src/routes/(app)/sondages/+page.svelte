<script lang="ts">
	import PageCommunaute from '#lib/components/PageCommunaute.svelte';

	export let data: { onglet: string };
</script>

<PageCommunaute onglet={data.onglet} />
