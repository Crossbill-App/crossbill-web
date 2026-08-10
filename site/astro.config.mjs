// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://crossbill-app.github.io',
	base: '/crossbill-web',
	integrations: [
		starlight({
			title: 'Crossbill',
			description:
				'A self-hosted reading companion that turns e-reader highlights into active reading.',
			favicon: '/favicon.png',
			logo: {
				src: './src/assets/crossbill-logo.png',
				alt: '',
			},
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/Crossbill-App/crossbill-web',
				},
			],
			customCss: [
				'@fontsource/lora/400.css',
				'@fontsource/lora/400-italic.css',
				'@fontsource/lora/500.css',
				'@fontsource/lora/600.css',
				'@fontsource/lora/700.css',
				'./src/styles/custom.css',
			],
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Introduction', slug: 'getting-started/introduction' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'KOReader plugin', slug: 'getting-started/koreader-plugin' },
						{ label: 'Optional components', slug: 'getting-started/optional-components' },
					],
				},
				{
					label: 'Features',
					items: [
						{ label: 'Highlights', slug: 'features/highlights' },
						{ label: 'Tags and organization', slug: 'features/tags-and-organization' },
						{ label: 'Notes', slug: 'features/notes' },
						{ label: 'Chapter digests', slug: 'features/chapter-digests' },
						{ label: 'Flashcards', slug: 'features/flashcards' },
						{ label: 'Book reflections', slug: 'features/book-reflections' },
						{ label: 'Semantic search', slug: 'features/semantic-search' },
					],
				},
				{
					label: 'Integrations',
					items: [
						{ label: 'KOReader', slug: 'integrations/koreader' },
						{ label: 'Obsidian', slug: 'integrations/obsidian' },
						{ label: 'Anki', slug: 'integrations/anki' },
					],
				},
			],
		}),
	],
});
