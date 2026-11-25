<script lang="ts">
	import { onMount } from 'svelte';
	import qrcode from 'qrcode-generator';

	export let data = '';
	export let size = 80;

	let svgMarkup = '';

	onMount(() => {
		if (!data) return;
		const qr = qrcode(0, 'M');
		qr.addData(data);
		qr.make();
		svgMarkup = qr.createSvgTag({ cellSize: 2, margin: 0, scalable: true });
	});
</script>

{#if svgMarkup}
	<div class="qr-wrap" style="width:{size}px;height:{size}px">
		{@html svgMarkup}
	</div>
{/if}

<style>
	.qr-wrap {
		display: inline-block;
		line-height: 0;
	}
	.qr-wrap :global(svg) {
		width: 100%;
		height: 100%;
	}
</style>
