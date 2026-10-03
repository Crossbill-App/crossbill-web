## Development

When starting the dev server, use background mode:

```
astro dev --background
```

Manage the background server with `astro dev stop`, `astro dev status`, and `astro dev logs`.

## Documentation

Full documentation: https://docs.astro.build

Consult these guides before working on related tasks:

- [Adding pages, dynamic routes, or middleware](https://docs.astro.build/en/guides/routing/)
- [Working with Astro components](https://docs.astro.build/en/basics/astro-components/)
- [Using React, Vue, Svelte, or other framework components](https://docs.astro.build/en/guides/framework-components/)
- [Adding or managing content](https://docs.astro.build/en/guides/content-collections/)
- [Adding styles or using Tailwind](https://docs.astro.build/en/guides/styling/)
- [Supporting multiple languages](https://docs.astro.build/en/guides/internationalization/)

## Writing style for the docs

Write the pages in `src/content/docs/` in plain, direct language. Readers want
to know what a feature does and how to use it.

- Use periods and commas, not em dashes. For a term and its definition in a
  list, write `**Term**: definition`.
- Say what something is or does. Do not define it by what it is not ("not X,
  but Y", "X rather than Y", headings like "Labels are not tags").
- Do not end a paragraph with a summary line or a clever closing phrase
  ("Highlights hold the author's words; notes hold yours.").
- Cut sentences that state the obvious. If you register an account, the
  reader already knows that the books they add belong to it.
- Use one idea per sentence and keep paragraphs short. When a paragraph holds
  three or more rules, make it a list.
- Use everyday words. Avoid literary wording such as "stays whole", "hanging
  off it" or "two ways in".
- Keep exact UI labels, environment variables, commands and tool names.
