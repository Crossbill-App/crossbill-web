/**
 * Strips a publication's own JavaScript before Readium ever frames it.
 *
 * ## Why this has to exist
 *
 * `@readium/navigator` frames each resource in an iframe it creates with
 * `sandbox="allow-same-origin allow-scripts"`
 * (`FrameManager.ts:28`), and the document it frames is a `blob:` URL built by
 * our own page — so the frame is **same-origin with the app**. A `<script>` in
 * a book therefore runs with the reader's privileges: it can read and write
 * `parent.document`, call the API as the signed-in user, and spend the
 * publication cookie. The library's own injected CSP does not stop it — it
 * ships `script-src ${domains} blob: 'unsafe-inline'`
 * (`FrameBlobBuilder.ts:5-21`), which deliberately permits both the book's
 * inline scripts and its external ones.
 *
 * Crossbill is self-hosted and its books come from wherever their owner found
 * them, so "the EPUB is trusted" is not a premise worth holding.
 *
 * ## Why a CSP rather than dropping `allow-scripts`
 *
 * Readium needs scripts *of its own* inside the frame: `css-selector-generator`
 * is injected unconditionally (`epubInjectables.ts`), and it is what turns a
 * browser selection into a Locator — the write path ADR-0004 §2 describes, and
 * the thing M3/M4 are built on. Those injectables are injected as
 * `<script src="blob:...">` (`Injector.ts`, `getOrCreateBlobUrl`), while a
 * book's own scripts are inline or come from the publication's origin. A
 * `script-src blob:` policy separates the two exactly: CSP policies combine by
 * intersection, so ours meets the library's at `blob:` and nothing else.
 *
 * Removing `allow-scripts` would kill Readium's injectables too, and removing
 * `allow-same-origin` would make the frame unscriptable from the parent, which
 * is how the navigator drives it at all. Neither is available.
 *
 * ## What is left
 *
 * This is a mitigation, not a sandbox. The frame is still same-origin, so
 * anything that does get script running in it has the page. The architectural
 * fix is to serve publication resources from a separate origin; the blob-URL
 * design makes that awkward, and it is not this ticket's to do.
 */

/**
 * Allows the navigator's own injected scripts, and nothing else.
 *
 * `child-src`/`object-src` are closed because a nested browsing context loaded
 * from our API origin would be a fresh same-origin document carrying no CSP at
 * all — an `<iframe>` or an `<object>` would hand a book the execution this
 * policy just took away. Styles, images and fonts are deliberately untouched:
 * a book's typography is the point of rendering it.
 */
const CONTENT_POLICY = ['script-src blob:', "object-src 'none'", "child-src 'none'"].join('; ');

/** The media types whose documents are parsed, cleaned, and re-serialised. */
const parserTypeFor = (contentType: string): DOMParserSupportedType | null => {
  const type = contentType.split(';')[0].trim().toLowerCase();
  if (type === 'application/xhtml+xml') return 'application/xhtml+xml';
  if (type === 'text/html') return 'text/html';
  return null;
};

const isEventHandler = (name: string) => name.toLowerCase().startsWith('on');

const isJavascriptUrl = (value: string) => /^\s*javascript:/i.test(value);

/**
 * Removes every way a document can name executable code.
 *
 * Belt and braces with the CSP above: the policy is the control the browser
 * enforces, and this is what makes the document harmless even where a policy
 * delivered by `<meta>` is not honoured. It also spares Readium the work of
 * neutralising scripts that are no longer there.
 */
const disarm = (doc: Document): void => {
  doc.querySelectorAll('script').forEach((script) => script.remove());

  doc.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const isUrlAttribute = attribute.name === 'href' || attribute.name === 'src';
      if (isEventHandler(attribute.name) || (isUrlAttribute && isJavascriptUrl(attribute.value))) {
        element.removeAttribute(attribute.name);
      }
    }
  });
};

const harden = (text: string, parserType: DOMParserSupportedType): string => {
  const doc = new DOMParser().parseFromString(text, parserType);
  // A document that does not parse is Readium's to complain about, in its own
  // words. Handing back the original text keeps that error the one the reader
  // sees, rather than a mangled serialisation of a broken file.
  if (doc.querySelector('parsererror')) return text;

  disarm(doc);

  const head = doc.head as HTMLHeadElement | null;
  if (head) {
    const meta = doc.createElement('meta');
    meta.setAttribute('http-equiv', 'Content-Security-Policy');
    meta.setAttribute('content', CONTENT_POLICY);
    head.prepend(meta);
  }

  return new XMLSerializer().serializeToString(doc);
};

/**
 * Wraps a fetch so every publication document it returns arrives disarmed.
 *
 * This is the seam because it is the only one that sees the bytes: Readium
 * builds each frame from `publication.get(item).readAsString()`
 * (`FrameBlobBuilder.buildHtmlFrame`), so a fetcher that hands back a cleaned
 * document is a navigator that frames a cleaned document. Anything that is not
 * a markup document — stylesheets, images, fonts — passes through untouched.
 */
export const hardeningFetch =
  (inner: typeof fetch): typeof fetch =>
  async (input, init) => {
    const response = await inner(input, init);
    const parserType = parserTypeFor(response.headers.get('content-type') ?? '');
    if (!response.ok || parserType === null) return response;

    const hardened = harden(await response.text(), parserType);
    return new Response(hardened, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  };
