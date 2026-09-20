# ui citations

Every third-party library the ui pulls in. Nothing else is vendored or copied.

| name | url | licence | use |
|---|---|---|---|
| react | https://github.com/facebook/react | MIT | view layer |
| react-dom | https://github.com/facebook/react | MIT | DOM renderer |
| vite | https://github.com/vitejs/vite | MIT | dev server + bundler; `configureServer` hosts the read-only `/data/` plugin |
| @vitejs/plugin-react | https://github.com/vitejs/vite-plugin-react | MIT | JSX fast refresh |
| typescript | https://github.com/microsoft/TypeScript | Apache-2.0 | typecheck (`tsc --noEmit`) |
| @types/react, @types/react-dom, @types/node | https://github.com/DefinitelyTyped/DefinitelyTyped | MIT | type definitions (dev only) |
| Newsreader (via `@fontsource-variable/newsreader`) | https://github.com/productiontype/Newsreader · https://github.com/fontsource/font-files | OFL-1.1 (font), MIT (packaging) | serif: the public statement and every human-facing label |
| IBM Plex Mono (via `@fontsource/ibm-plex-mono`) | https://github.com/IBM/plex · https://github.com/fontsource/font-files | OFL-1.1 (font), MIT (packaging) | mono: scratchpads, player ids, model ids, numbers |

No routing, state, chart, icon, animation or component libraries. Both fonts are self-hosted: vite bundles the
woff2 files from the fontsource packages, so nothing is fetched from a font CDN at demo time and the ui looks the
same with the wifi down. System stacks remain as fallbacks. Every icon is an inline svg written in `src/components/Glyphs.tsx`.
