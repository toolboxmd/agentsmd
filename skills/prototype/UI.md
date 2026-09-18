
# UI Prototype

Build several structurally different UI variants on one route with a floating
bottom switcher. For logic or state questions, use [LOGIC.md](LOGIC.md). Apply
[SKILL.md](SKILL.md)'s common prototype, capture, and continuation rules.

## Choose the host

Prefer an existing page, including for a new section, card, or step that naturally
belongs there. Keep its real header, sidebar, data density, fetching, params, and
auth; swap only rendering through `?variant=`. This context exposes problems that
an empty route hides.

Only when no sensible host exists, create an obviously named throwaway prototype
route using project routing conventions. Check for a possible host before choosing
this branch. Both branches use the same URL parameter and switcher.

## Build and compare

1. Default to three variants; cap at five. Record the question, count, route,
   and URL selection in one line at the prototype location or top-of-file comment.
2. Give each variant a clear exported name, such as `VariantA`. Preserve page
   purpose, available data, and the project's component/styling system. Vary
   layout, information hierarchy, and primary affordance, not just colour or
   copy. Redo near-duplicates, for example with explicit "no card grid" guidance.
   Sharing a header is fine; sharing a layout must not constrain the alternatives.
3. Select the rendered variant from `?variant=`, defaulting to A. Keep fetching
   above the switcher on an existing page; mount the same switcher on a new route.
4. Put the switcher in one shared component at the project's shared-UI location.
   Make it a visually distinct, fixed bottom-centre bar with:
   - Previous and next arrows that wrap around.
   - The current key and exported name when available, such as `B (Sidebar layout)`.
   - Framework-router updates to the URL so selections survive reload and sharing.
   - Left/right keyboard cycling, except while an `input`, `textarea`, or
     `[contenteditable]` element has focus.
   - A production-build guard, such as `process.env.NODE_ENV !== 'production'`,
     preventing accidental switcher exposure.
5. Share the URL and variant keys. Feedback may combine variants, for example
   B's header with C's sidebar. Keep real interactions read-only; stub mutations.
6. Record the winning choice and reasons, then capture all variants as primary
   evidence on the throwaway branch under the common procedure. For an existing
   host, fold the winner into that page; for a new surface, promote it to a real
   route. Rewrite properly for production, since prototype code lacks production
   tests and error handling. Remove losing variants, the temporary route, and
   the switcher from main.
