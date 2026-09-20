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

No routing, state, chart, or component libraries. Fonts are system stacks (no external font loads).
