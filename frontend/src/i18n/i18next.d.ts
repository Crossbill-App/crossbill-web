import 'i18next';
import type { defaultNS } from './index';
import type { en } from './locales/en';

// Types every `t('...')` call against the English resources, so a missing or
// misspelled key is a type error rather than a raw key on screen.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS;
    resources: { translation: typeof en };
  }
}
