import { Locator } from '@readium/shared';
import { findLast } from 'lodash';

/**
 * Where in this publication's own position list a locator lands, or `null` when
 * it names a resource the publication has not got.
 *
 * The navigator resolves an initial position by looking `locations.position` up
 * in the list it was built with and throws when it finds no match — and neither
 * a position number another browser wrote nor the absent one a KOReader-derived
 * locator carries can be trusted to index the list this publication has today.
 */
export const landingFor = (target: Locator, positions: Locator[]): Locator | null => {
  const inResource = positions.filter((entry) => entry.href === target.href);
  if (inResource.length === 0) return null;
  const progression = target.locations.progression;
  const entry =
    findLast(
      inResource,
      (candidate) => (candidate.locations.progression ?? 0) <= (progression ?? 0)
    ) ?? inResource[0];
  // The target is what is returned, wearing the entry's numbers rather than the
  // other way round: the progression is what places the reader within the
  // resource, while the position only has to index the list without throwing.
  // The covering entry is picked so that the pair agrees anyway — which is what
  // the navigator computes for itself the moment a frame reports back, and what
  // it is left holding if one never does.
  return target.copyWithLocations({
    position: entry.locations.position,
    totalProgression: entry.locations.totalProgression,
  });
};
