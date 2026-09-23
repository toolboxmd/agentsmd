
# Logic Prototype

Build one self-contained, shareable HTML demo for questions about business
logic, state transitions, or data shape. A non-developer must be able to press
buttons and judge the state model. For appearance questions, use [UI.md](UI.md).
Apply the common prototype rules and capture procedure in [common procedure](index.md).

## Build

1. Put a visible paragraph at the top naming the state model and precise
   question. The user must be able to check it even when returning later.
2. Isolate the logic in one `<script>` block as a portable pure module. Choose
   the shape from the question: a reducer `(state, action) => state` for discrete
   events, an explicit state machine for legal transitions, pure functions over
   data for transformations, or a module/class when ongoing internal state is
   necessary. No DOM, `document`, or button handlers inside the module. The page
   calls it, never the reverse; validated logic can later move into the real module.
3. Use inline HTML/CSS/JS only, without a framework, bundler, server, or install.
   The file must open by double-click and remain shareable by email. Use domain
   language and plain explanations throughout, not code labels.
4. Arrange the demo in this order:
   - Title and one-line explanation of the question.
   - Full relevant current state as labelled fields, not raw JSON. Re-render
     after each click; call out changes when that helps understanding.
   - Always-available free-play buttons, one per action, allowing any order.
   - Tabbed guided scenarios with a plain-language situation and what to watch
     for. Each ordered step is a real button that performs its action and
     advances. Starting a walkthrough resets to a known state for repeatability.
5. Cover the happy path, an awkward edge case, and an attempted illegal action.
   Use restrained typography, generous spacing, and one accent colour. Avoid
   animations or gimmicks that distract from state and actions.
6. Send or open the file. Add actions or scenarios when feedback needs them.
   Capture the answer and artifact under the common procedure. Validated logic
   may lift into the real module; the HTML shell remains on the throwaway branch
   as re-runnable primary evidence, never production code.

Do not add tests or a production test suite; use the common runnable smoke
check. Do not generalise beyond the question. Use memory, never the real
database unless persistence itself is the question; apply the common disposable
data rule when it is.
