/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Absolute origin of the API, e.g. `http://localhost:8000`. Leave it unset
   * so the API shares the app's own origin — see `src/api/base-url.ts`.
   */
  readonly VITE_API_URL?: string;
}
