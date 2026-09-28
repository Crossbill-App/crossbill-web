import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './locales/en';

export const defaultNS = 'translation';

/**
 * Every piece of user-facing copy lives in `./locales/<language>/`. Components
 * read it with `useTranslation()`; plain modules (helpers, hooks building
 * messages outside render) use the `i18n.t` exported here.
 *
 * Initialised synchronously with bundled resources, so the first render
 * already has its copy and there is no loading state to handle.
 */
void i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  defaultNS,
  resources: { en: { [defaultNS]: en } },
  interpolation: {
    // React escapes rendered strings itself.
    escapeValue: false,
  },
});

export { i18n };
