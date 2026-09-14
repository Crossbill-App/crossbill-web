/**
 * The ranges the browser's own highlight painter holds inside the frames under `root`.
 * Those with boxes only: a range with none is registered rather than painted.
 */
export const drawnRanges = (root: ParentNode): Range[] =>
  [...root.querySelectorAll('iframe')]
    .flatMap((frame) => {
      const realm = frame.contentWindow as unknown as
        { CSS?: { highlights?: Map<string, Iterable<Range>> } } | undefined;
      return [...(realm?.CSS?.highlights?.values() ?? [])];
    })
    .flatMap((ranges) => [...ranges])
    .filter((range) => range.getClientRects().length > 0);

/** Each drawn range as the element it lies in and the words it covers. */
export const drawnOn = (root: ParentNode): string[] =>
  drawnRanges(root).map(
    (range) => `${range.startContainer.parentElement?.tagName}:${range.toString()}`
  );
