/**
 * Between the API's locator schemas and the engine's `EbookLocation`.
 *
 * The API says `null` where the seam says `undefined`, and this is the one
 * place that translates.
 */
import type { BrowserLocatorSchema, LocatorSchema } from '@/api/generated/model';
import type { EbookLocation } from '@/components/reader/EbookReader.ts';

/** The API's locator in the engine's terms, whose absences are `undefined`. */
export const fromBrowserLocator = (stored: BrowserLocatorSchema): EbookLocation => ({
  href: stored.href,
  type: stored.type,
  title: stored.title ?? undefined,
  locations: {
    position: stored.locations?.position ?? undefined,
    progression: stored.locations?.progression ?? undefined,
    totalProgression: stored.locations?.totalProgression ?? undefined,
    fragments: stored.locations?.fragments ?? undefined,
  },
});

/** A highlight's locator in the engine's terms. */
export const fromLocatorSchema = (locator: LocatorSchema): EbookLocation => ({
  href: locator.href,
  type: locator.type,
  locations: {
    progression: locator.locations.progression ?? undefined,
    cssSelector: locator.locations.cssSelector ?? undefined,
  },
  text: {
    before: locator.text.before ?? undefined,
    highlight: locator.text.highlight ?? undefined,
    after: locator.text.after ?? undefined,
  },
});

// The serialised JSON is also the "has this moved?" key, so an engine that
// reports no fragments one tick and an empty array the next must not read as a move.
export const toBrowserLocator = ({
  href,
  type,
  title,
  locations,
}: EbookLocation): BrowserLocatorSchema => ({
  href,
  type,
  title,
  locations: {
    position: locations.position,
    progression: locations.progression,
    totalProgression: locations.totalProgression,
    fragments: locations.fragments?.length ? locations.fragments : undefined,
  },
});
