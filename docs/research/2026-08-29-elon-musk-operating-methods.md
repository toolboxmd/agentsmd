# Elon Musk's operating methods: source-checked guidance for agent instructions

**Status:** Research complete; closed-loop instruction implemented on the Issue #6 branch

**Date:** 2026-08-29

**Scope:** Complete analysis of *The Book of Elon: A Guide to Purpose and Success* by Eric Jorgenson, foreword by Naval Ravikant; the complete linked My First Million conversation with Jon McNeill; and the primary Everyday Astronaut interview source for Musk's five-step sequence.

**Source PDF:** User-provided `The+Book+of+Elon+Free+PDF.pdf`; its SHA-256 is recorded below.

**Layout extraction:** Temporary audit artifact; byte count and SHA-256 are recorded below.

**Requested conversation:** <https://www.youtube.com/watch?v=GG4TwQEYdBY>

**Primary Algorithm source:** <https://www.youtube.com/watch?v=t705r8ICkRw&t=809s>

**Target question:** What is Elon Musk's "Algorithm," what other operating methods does this book attribute to him, and which of those methods could safely improve a compact `AGENTS.md` for software agents?

## Executive conclusion

The book's most useful contribution to agent instructions is a strict sequence for improving work: question the requirement, delete unnecessary work, simplify what remains, accelerate the validated path, and automate last. The sequence matters more than any individual step. Its purpose is to prevent an expert from efficiently solving the wrong problem or automating waste. The book supports this with a Tesla battery-line example in which automation, acceleration, and optimization were all attempted before the underlying part was shown to be unnecessary. [E, PDF pp. 131-138, "The Algorithm"]

For software agents, the sequence is promising only after adding two safeguards that are not optional: governing instructions and user-owned constraints retain precedence, and deletion or experimentation must be risk-scaled and reversible. The book itself supports risk-scaling. It treats exploratory Starship tests differently from crewed Dragon missions, says failure must be culturally acceptable when trying unknown technology, and also says catastrophic failure is not acceptable. [A from E, PDF pp. 120-124, "Innovation Needs Permission to Fail"; pp. 237-240, "You Have to Blow Things Up"]

The strongest supporting methods are: define useful outcomes, stay close to source evidence and actual work, assume error and seek fast feedback, attack the active constraint, keep communication simple and direct, parallelize genuinely independent or gestating work, use one meaningful measure of progress, and distinguish a prototype from reliable production. Together these form a coherent operating loop rather than a collection of motivational slogans. [A from E, PDF pp. 33-35, "Be Useful"; pp. 55-71, "Think Like a Physicist"; pp. 113-119, "Designing the Organization"; pp. 141-150, "Maniacal Urgency"; pp. 157-160, "We Must Make Stuff"; pp. 177-180, "Listen Well, Correct Fast"; pp. 200-202, "Sequenced Strategy of Tesla"; pp. 237-240, "You Have to Blow Things Up"; pp. 277-280, "The Last Human Drivers"]

Several memorable lines should not be copied into an always-loaded `AGENTS.md`: "work like hell," "empathy is not an asset," treating all requirements as recommendations, a universal 10 percent deletion-addback target, or unconditional failure tolerance. The book itself either limits these ideas, contradicts the editor's compressed maxim, or supplies a safety-critical counterexample. [A from E and J, PDF pp. 45-47, "Work Like Hell"; pp. 91-93, "Sleep on the Factory Floor" and "Frontline Leadership"; pp. 109-110, "Retain Only Special Forces" and "Feedback over Feelings"; pp. 120-124, "Innovation Needs Permission to Fail"; pp. 133-138, "The Algorithm"; pp. 237-240, "You Have to Blow Things Up"; pp. 291-294, "Regulation Accumulation"; pp. 336-339, "The 69 Core Musk Methods"]

The linked conversation strengthens the case for reality and constraint focus,
but it does not provide the five-step sequence. It discusses Jon McNeill's
broader book, also titled *The Algorithm*, through operational stories about
talent, direct observation, order-of-magnitude goals, product simplification,
and compact decision communication. Those are useful corroborating practices,
not a substitute source for Musk's ordered engineering method. [W, requested
conversation, 1:18-40:50]

The primary Everyday Astronaut interview confirms the five steps, their order,
and the warning against reversing them. It also narrows the meaning of
requirements: Musk says each requirement or constraint should resolve to a
named person who accepts responsibility for it. [P, *Starbase Tour Part 1*,
13:29-24:48]

The complete source comparison supports an ordered inner sequence inside a
short feedback loop, not a 69-item manifesto. Establish the useful outcome;
challenge the proposed path; reject or delete in-scope Git-backed work that
does not serve it; simplify only the survivors; shorten the iteration through
the current constraint; and automate only a necessary, stable, proven,
recurring loop. In every cycle, make a small meaningful change or experiment,
run the fastest check that can falsify the current assumption, inspect the
result, correct the model and implementation, expose bad news, and repeat. [A
from P and E, *Starbase Tour Part 1*, 13:29-24:48; PDF pp. 55-60, 110,
131-138, 177-180, and 237-240; W, requested conversation, 11:26-21:45]

The first implementation compressed that operating model into two cautious
Work bullets. It named the five steps but omitted addback as feedback, did not
make Git recoverability operational, and left no closed observe-correct-repeat
cadence. The user rejected that result because it could be read without
changing the agent's next action. A two-turn, read-only Grok 4.6 Build review at
xhigh reasoning independently found the same behavioral defects and was then
red-teamed to separate fast per-cycle falsification from final proof. The final
instruction below is my software-agent translation and judgment, not an Elon
Musk quotation or a delegation of policy ownership to Grok. [A]

## Evidence and attribution model

Every source-derived or interpretive claim in this report uses one of these labels. Mechanical coverage checks are reported separately:

- **[P] Primary Musk interview:** Musk speaking in Tim Dodd's manually
  captioned *Starbase Tour* video. Subtitle wording was checked against the
  surrounding sequence and timestamps.
- **[W] Eyewitness account:** Jon McNeill describing his experience at Tesla
  in the requested My First Million conversation. This is direct testimony
  from a participant, but still a recollection in a promotional interview for
  McNeill's own book.
- **[H] Host framing:** Shaan Puri's questions, interpretations, and examples
  in the requested conversation. These are secondary commentary.
- **[E] Elon-attributed material:** First-person or direct-speech material that the compiler presents as Elon Musk's words. This does not mean independently authenticated verbatim speech.
- **[J] Jorgenson/editorial material:** Eric Jorgenson's framing, headings, questions, summaries, selected highlights, and the 69-method synthesis.
- **[N] Naval material:** Naval Ravikant's foreword.
- **[A] Analysis:** My inference or translation to software-agent work. It is
  not attributed to any source participant or editor.

This distinction is necessary because Jorgenson says transcripts were edited multiple times for clarity, brevity, and flow; he cannot guarantee every source's authenticity; he recontextualized everything; and readers should verify phrasing against a primary source before citing Musk. [J, PDF p. 16, "Notes on This Book"]

The typography is also not a reliable verbatim marker. Jorgenson says highlights "summarize or punctuate" ideas, and says some bolded interview questions were written to provide context. A highlighted sentence or question can therefore be editorially constructed even when surrounded by Elon-attributed material. [J, PDF p. 17, "Highlights" and "Bolded Questions"]

The body is presented as being built from transcripts, tweets, and interviews, but the source notes also cite biographies and secondary syntheses such as Walter Isaacson, Eric Berger, Tim Urban, Ashlee Vance, and *Musk's Memos*. The book should therefore be treated as an edited anthology with mixed source distance, not as a single primary transcript. [J, PDF p. 16, "Notes on This Book"; PDF pp. 364-399, "Sources"]

The "69 Core Musk Methods" are explicitly described as selected, edited, or paraphrased maxims. They are compiler interpretation, even when a maxim resembles language elsewhere in the body. [J, PDF pp. 336-339, "The 69 Core Musk Methods"]

Naval calls the book an explanation and manual, praises Musk as an exceptional entrepreneur, and argues that his methods are copyable. This is advocacy in a foreword, not independent evidence that every method generalizes or caused the reported outcomes. [N, PDF pp. 18-20, "Foreword"]

Jorgenson likewise says he selected only Musk's "most useful ideas," excluded family life and politics, hopes to inspire "one million Musks," and designed the book to feel like personal tutoring. This declared selection strategy makes the book useful for hypothesis generation but weak as a balanced causal evaluation. [J, PDF pp. 22-25, "Eric's Welcome to This Book"]

## PDF coverage and verification

The source PDF was read from physical PDF page 1 through physical PDF page 401. Citations in this report always use physical PDF page numbers, not the printed page number in the footer. In the main body, the physical number is generally one higher than the printed number. For example, physical PDF p. 131 is printed p. 130, where "The Algorithm" begins.

| Physical PDF pages | Material read |
|---|---|
| 1-15 | Cover, title, copyright, dedication, and complete contents |
| 16-29 | Editorial notes, Naval foreword, Jorgenson welcome, opening quotation, and transition |
| 30-83 | Part I, "Pursue Purpose" |
| 84-161 | Part II, "Ultra Hardcore Work" |
| 162-249 | Part III, "Building Companies" |
| 250-333 | Part IV, "On Behalf of Humanity" |
| 334-339 | Bonus heading and all 69 compiler-selected methods |
| 340-363 | Timeline, recommended reading, appreciation, and author material |
| 364-399 | All 1,063 source entries |
| 400-401 | Blank terminal pages retained in the page audit |

Coverage checks:

- `pdfinfo` reports exactly 401 pages.
- The supplied layout extraction contains exactly 401 form-feed-delimited page segments plus a terminal empty segment.
- The extraction contains 68,786 words and 421,864 bytes.
- A fresh `pdftotext -layout` stream from the source PDF was byte-identical to the supplied extraction. Both have SHA-256 `f648e9db13eef3d7edb3bc6480a6d81426ed9ba32b4cdf436a243ce3fa089add`.
- The PDF SHA-256 is `df24fb6c3b8f75985c2cdf821e6f37b302a648c53731f656e56d6e1d01474b47`.
- Physical pages 16-17, 131-138, 336-339, and 375-376 were re-extracted directly from the PDF with layout preserved to verify editorial boundaries, the full Algorithm sequence, the 69-method disclaimer, and Algorithm source attribution.
- The existing render of physical pages 131-138 was visually inspected. It confirmed that the five-step list begins on physical p. 131, the 10 percent deletion line is a standalone visual on p. 134, and the "optimize a thing that should not exist" line is repeated as a standalone visual on p. 137.

## Video coverage and verification

### Requested My First Million conversation

The public video is *Ex-Tesla President reveals EVERYTHING Elon does to win*,
published by My First Million on 2026-04-09. It runs 1:02:45 and features
Shaan Puri interviewing Jon McNeill. [Video metadata,
<https://www.youtube.com/watch?v=GG4TwQEYdBY>]

The complete original-language automatic-caption track was downloaded and
read from the opening at 0:00.08 through the spoken signoff at 1:02:25.68. The
remaining seconds contain no additional discussion. The cleaned track contains
1,849 spoken caption segments and 13,085 words.

One automatic-caption gap ran from 57:29.36 through 57:50.80. The matching
audio was downloaded, isolated, and transcribed locally. That passage explains
that digital spreadsheets calculated complex problems faster than the former
human calculation floors, enabling sophisticated pricing engines and new
options, futures, and derivatives markets. The recovered passage completes the
argument and adds no Elon-specific operating rule. A separate audio check of
the final 25 seconds confirmed that the captioned signoff is the end of the
conversation.

The transcript was read in full across its published chapters:

| Time | Subject |
|---|---|
| 0:00-5:07 | Musk interview story and deep problem interrogation |
| 5:07-11:23 | Talent evidence, actual ownership, and live problems |
| 11:23-23:41 | Store observation, sales constraint, and factory bottleneck |
| 23:41-31:45 | One-size-fits-all assumptions, friction, and noticing |
| 31:45-38:34 | Order-of-magnitude goals and configuration simplification |
| 38:34-43:24 | Three-sentence decision communication |
| 43:24-49:05 | Collision-repair constraint and throughput redesign |
| 49:05-1:02:25 | AI, domain judgment, automation, and second-order effects |

### Primary Musk source

The book's source notes point to Tim Dodd's *Starbase Tour* Parts 1 and 2. Both
complete manually captioned tracks were downloaded and searched. Part 1 has
1,124 spoken segments and 7,668 words; Part 2 has 1,464 segments and 9,637
words. The ordered five-step explanation is in Part 1 from 13:29 through the
Model 3 example ending near 24:48. [P,
<https://www.youtube.com/watch?v=t705r8ICkRw&t=809s>]

Part 2 contains later examples of simplification and deletion but not another
enumeration of the five-step sequence. [P,
<https://www.youtube.com/watch?v=SA8ZBJWo73E>]

## The Algorithm, exactly and in context

### Exact five-step formulation

The book presents the following as Elon-attributed first-person material. The order is explicitly described as "very important." [E, PDF p. 131, "The Algorithm"]

1. "Make your requirements less dumb."
2. "Try very hard to delete the part or process."
3. "Simplify or optimize."
4. "Accelerate."
5. "Automate."

These short formulations are exact as printed in the book, but still inherit the compiler's warning that the book has edited and recontextualized its source material. [E qualified by J, PDF p. 131, "The Algorithm"; PDF p. 16, "Notes on This Book"]

### Why the order matters

The central failure mode is backward optimization. In the battery-line example, the team improved a robot's speed and path, optimized glue and drying, and only later asked why the fiberglass mat existed. The battery team said it was for noise and vibration, while the noise-and-vibration team said it was for fire safety. A comparison test found no perceptible difference, so the mat and roughly $2 million of associated robotics were removed. [E, PDF pp. 131-132, "The Algorithm"]

This example does not show that automation is bad. It shows that automation compounds whatever process definition comes before it. Automating a necessary, understood process may be valuable; automating an unexamined process hardens waste into equipment, code, dependencies, and operating assumptions. [A from E, PDF pp. 131-132 and 138, "The Algorithm"]

### Step 1: question the requirement

The method begins by asking whether the problem statement is correct. The stated risk is producing a perfect answer to the wrong question. The book says requirements from smart people can be especially dangerous because others are less likely to question them. [E, PDF pp. 132-133, "The Algorithm"]

The method also demands provenance. Every requirement should resolve to a named person who can explain and own it, rather than an abstract department. The book describes finding inherited requirements that nobody currently in the named department actually supported. [E, PDF p. 133, "The Algorithm"]

For software agents, "question" should mean recover intent, owner, evidence, and acceptance criteria. It must not mean disobey system or developer instructions, reinterpret the user's explicit request, ignore law or safety, or silently expand scope. [A from E, PDF pp. 132-133, "The Algorithm"; counterweight from E, PDF pp. 291-294, "Regulation Accumulation"]

### Step 2: try to delete the part or process

The method asks whether the requirement, component, step, meeting, dependency, or artifact needs to exist at all. This is stronger than making it cheaper or cleaner. The book links deletion to avoiding "just in case" accumulation and to recursive costs, where one added element creates secondary mass, fuel, structure, and coordination costs. [E, PDF pp. 133-136, "The Algorithm"]

The printed 10 percent addback heuristic is intended to counter excessive conservatism: if nothing ever needs to be restored, the claim is that deletion was probably too timid. [E, PDF pp. 134-136, "The Algorithm"]

For agents, that percentage should not become a target. For in-scope committed
Git-backed work, addback is cheap enough to be a normal way to map the deletion
boundary. Git history should replace just-in-case maintenance. This recoverable
class is different from user data, credentials, migrations, production
configuration, legal controls, or uncommitted user work. The transferable
principle is "test whether absence is better," not "cause a fixed amount of
rework." [A from E, PDF pp. 133-136, "The Algorithm"; risk qualification from
E, PDF pp. 237-240, "You Have to Blow Things Up"]

### Step 3: simplify or optimize

Only after deletion does the method improve what remains. The book's exact warning is that smart engineers commonly "optimize a thing that should not exist." The attributed explanation says formal education trains people to answer the given question instead of challenging it. [E, PDF pp. 136-138, "The Algorithm"]

This step aligns with the broader simplicity principle: fewer components can reduce cost and failure points; lines of code are not a merit by themselves; and one-piece casting can remove joints, sealants, dissimilar materials, and hundreds of robots. The same chapter also admits that simplification is difficult, not a slogan that automatically identifies the right design. [E, PDF pp. 125-130, "Simplicity Wins"]

For agents, simplification comes after deciding what must remain. It can mean fewer states, a narrower interface, one clear owner, a smaller patch, a direct data path, or removal of duplicate ceremony. It does not mean suppressing necessary error handling, proof, safety, or user-visible capability. [A from E, PDF pp. 125-130, "Simplicity Wins"; pp. 136-138, "The Algorithm"]

### Step 4: accelerate

Acceleration means shortening cycle time after direction and structure are sound. The book explicitly warns against speeding up a process that should have been deleted. [E, PDF p. 138, "The Algorithm"]

The adjacent urgency chapter treats time as scarce, recommends leaving meetings that do not create value, emphasizes speed as a competitive factor, and recommends putting independent "gestating" elements in parallel rather than serializing them. [E, PDF pp. 141-146, "Maniacal Urgency"]

For agents, the safest acceleration mechanisms are faster feedback, smaller checks, fewer handoffs, direct source inspection, cached or parallel read-only work, and concurrent execution only where ownership and dependencies are genuinely independent. Speed must not erase proof or make two writers race on the same state. [A from E, PDF pp. 141-146, "Maniacal Urgency"; pp. 113-119, "Designing the Organization"]

### Step 5: automate

Automation is last because it magnifies a chosen process. The book attributes Tesla's removal of hundreds of prematurely installed robots to automating before requirements, deletion, and process design were settled. [E, PDF p. 138, "The Algorithm"]

For agents, automation should follow a proven semantic path. A repeated, stable, observed operation is a candidate for a script, hook, workflow, generator, or reusable skill. A one-off or still-ambiguous process should usually remain explicit until its invariants and failure modes are understood. [A from E, PDF p. 138, "The Algorithm"]

### Primary-source verification of the Algorithm

The book's endnotes map Algorithm notes 324-327 to Tim Dodd's *Starbase Tour* Parts 1 and 2, which are interview/video sources, while notes 328-329 map to Walter Isaacson's biography. The printed section is therefore assembled from at least one first-person interview stream and one secondary narrative source. [J source apparatus, PDF pp. 375-376, "Sources"]

The manually captioned Part 1 interview directly confirms the sequence and the
importance of order. [P, *Starbase Tour Part 1*, 13:29-24:48]

| Step | Direct interview evidence | Timestamp |
|---|---|---|
| 1 | Make requirements less dumb; requirements from smart people can be especially dangerous because they receive less challenge. | 13:36-13:54 |
| 1 provenance | A requirement or constraint must have a person's name, and that person must accept responsibility for it. | 16:00-16:16 |
| 2 | Try very hard to delete the part or process; addback is presented as evidence that deletion was not too timid. | 13:56-14:46 and 17:03-17:17 |
| 3 | Only then simplify or optimize, because a common engineering error is optimizing something that should not exist. | 17:18-18:04 |
| 4 | Accelerate cycle time only after the first three steps. Going faster in the wrong process means digging faster in the wrong direction. | 21:32-21:50 |
| 5 | Automate last. Musk says he has personally reversed all five steps and describes the Model 3 battery-mat failure. | 21:57-24:48 |

The primary wording is close to the anthology, but the video supplies two
useful qualifications that compact summaries often lose. First, a requirement
has accountable human provenance. Second, acceleration is specifically cycle
time after the first three steps, not generalized haste. [P, *Starbase Tour
Part 1*, 13:29-21:57]

The direct source also shows why the 10 percent addback claim should remain a
contextual heuristic rather than agent policy. It is spoken while discussing
rocket parts and processes under tight mass margins, not user data, production
deletion, legal constraints, or software authority. [P, *Starbase Tour Part
1*, 13:56-17:17; A]

### Exact adjacent formulations worth preserving as evidence

These are short formulations printed in the Elon-attributed body, not final agent instructions. Highlights may be editorially clipped or punctuated, and all inherit the book-wide editing warning. [E qualified by J, PDF pp. 16-17, "Notes on This Book" and "Highlights"]

| Exact wording in the book | Immediate context | Agent relevance |
|---|---|---|
| "Start somewhere. Then be prepared to question your assumptions" | Truth-seeking precedes correction and adaptation. [E, PDF p. 55, "Obsess over Truth"] | Begin with a testable model, not a claim of certainty. [A] |
| "Assume we're wrong" and "Aspire to be less wrong" | Physics is presented as a discipline of error correction. [E, PDF p. 69, "Aspire to Be Less Wrong"] | Make confidence evidence-sensitive and update quickly. [A] |
| "Go as close to the source as possible" | The example bypasses hierarchy to speak with people doing the welding. [E, PDF pp. 116-117, "Remove Organizational Boundaries"] | Inspect the exact code, state, log, issue, or user surface. [A] |
| "Communication should travel via the shortest path" | The target is solving the problem for the whole company, not preserving chain-of-command power. [E, PDF pp. 113-114, "Remove Organizational Boundaries"] | Reduce lossy handoffs while keeping ownership explicit. [A] |
| "The best part is no part. The best process is no process." | Removal is used to improve throughput, reliability, and cost. [E, PDF pp. 127-129, "Simplicity Wins"] | Test whether an artifact or ceremony can be absent before refining it. [A] |
| "You need to be a vector, not just a scalar" | Speed must have a direction and allow course correction. [E, PDF p. 143, "Speed Is Both Offense and Defense"] | Optimize cycle time only after outcome and direction are clear. [A] |
| "Avoid serialized dependencies" | Independent vendor setup and software work are allowed to mature in parallel. [E, PDF p. 146, "Do Things in Parallel"] | Parallelize independent latency, not shared write ownership. [A] |
| "All bad news should be given loudly and often" | Feedback should focus on substance and permit improvement. [E, PDF p. 110, "Feedback over Feelings"] | Surface blockers and uncertainty before celebratory status. [A] |
| "Prototypes are easy; production is hard" | Ideas and demonstrations are contrasted with reliable production and positive cash flow. [E, PDF p. 82, "Engineering Creates Value"] | Keep prototype, implementation, deployment, and live proof as distinct states. [A] |

The table preserves exact fragments for traceability. Its agent-relevance column is my inference, not quoted Musk or compiler language. [A from the cited E material]

## What the requested conversation adds

### It discusses a different, broader "Algorithm"

The host introduces McNeill's book *The Algorithm* as a framework that equipped
world-class people at Tesla to make decisions at the edge. McNeill agrees with
that three-layer framing: Musk's ability, exceptional talent, and a shared
method. The conversation does not enumerate Musk's five engineering steps or
claim that McNeill's entire book is those five steps. [H and W, requested
conversation, 29:39-31:45]

This distinction matters. The attached anthology and primary Tim Dodd interview
support one ordered reduction sequence. The requested conversation offers a
wider collection of management practices and stories. Calling all of them
"Elon's Algorithm" would blend two sources and overstate the evidence. [A]

### 1. Test problem ownership, not prestige

McNeill says Musk tested candidates by going deeply into a concrete problem,
partly one Musk already understood, to see how many layers of reasoning the
candidate could sustain. McNeill later used two probes: examine a candidate's
past problem closely enough to separate personal work from team credit, then
give the candidate a current problem and observe curiosity, analysis,
questions, and problem solving. [W, requested conversation, 1:18-7:30]

The agent analogue is evidence of actual ownership: inspect the exact diff,
commands, artifacts, and causal chain instead of inferring quality from a
branch name, tool, model, or claimed result. This is already covered by the
repository's proof and handoff rules and does not need a new global hiring
section. [A]

### 2. Go to the real work and user surface

Before joining Tesla, McNeill mystery-shopped eight stores and found that none
followed up after a test drive. A CRM query then found 9,000 recent test drives
without callbacks. In a separate factory story, he and Musk stood at the
inventory pile-up, watched the door-fitting operation, and saw the blind bolt
alignment that needed a jig. [W, requested conversation, 11:26-19:23]

He summarizes the operating pattern as stack-ranking the constraints on the
business, taking the largest one from the top, and working it. [W, requested
conversation, 16:57-17:12]

For agents, this supports inspecting the exact code, log, issue, runtime, or
user surface and identifying the constraint that controls completion. It does
not support replacing representative evidence with executive intuition. The
conversation itself warns that observation can alter behavior when workers
know the boss is present. [W, requested conversation, 18:45-20:18; A]

### 3. Use order-of-magnitude goals as a design probe

McNeill says Musk set 10x or 100x improvement goals because a small target can
be met by tweaking the status quo, while an order-of-magnitude target forces a
different design. The Tesla example was a 20x digital-sales goal when buying a
car required 64 clicks. Comparison with a 10-tap pizza order led the team to
challenge 360,000 nominal car configurations; customer data showed two core
jobs, and the product was reduced to a few configurations. [W, requested
conversation, 33:11-38:15]

For agents, "what would make this 10x simpler, safer, or faster?" can be a
useful exploration question when incremental improvement cannot meet the real
outcome. It should not become a delivery estimate, a universal target, or a
reason to skip proof. The durable principle is that a sufficiently ambitious
constraint can expose the need for deletion and redesign. [A]

### 4. Communicate problem, cause, and proposed solution

McNeill recalls an effort to run Tesla through three-sentence emails: state the
problem, the analysis of root cause, and the proposed solution. He says cost
and economics belong in the proposed solution, and that the compression saved
executive absorption, processing, and decision time while sharpening the
writer's own thinking. [W, requested conversation, 39:35-40:50]

This is useful as a decision-update template, not as a literal three-sentence
limit for all agent answers. Complex proof, exceptions, exact commands, legal
or safety boundaries, and user-requested detail may require more space. The
current Communication and Handoff sections are the better policy owners; a
separate Elon communication rule would duplicate them. [A]

### 5. Pair agents with domain judgment

In the AI section, McNeill describes agents learning client workflows quickly,
while domain experts decide which rules are good, judge whether agent output is
correct, and redirect it when needed. [W, requested conversation,
54:10-55:47]

This supports automating an understood process after knowledgeable review. It
does not support automating a still-ambiguous workflow merely because an agent
can imitate it. [A]

### 6. Do not copy action beyond authority

One story celebrates McNeill changing Tesla's global sales-lead flow before he
formally worked for the company, then asking Musk's forgiveness. The change
apparently improved sales and helped secure the job. [W, requested
conversation, 12:43-15:10]

That outcome does not make unauthorized mutation a safe agent method. An agent
cannot manufacture ownership from urgency or confidence. The useful part is
finding the real constraint and proposing a small intervention; authority,
Human Gates, exact targets, and verification still govern execution. [A]

## The wider operating system in the book

The book's methods become more coherent when arranged as a loop:

1. Choose an outcome that is useful and worth doing.
2. Build the most accurate available model of reality.
3. Stay close to the source, the work, and the people experiencing the problem.
4. Run the Algorithm in order.
5. Identify the active constraint and concentrate effort there.
6. Iterate quickly where failure is reversible and noncatastrophic.
7. Prove the result at production scale or the actual user surface.
8. Correct the model from feedback and repeat.

This loop is my synthesis, not a sequence printed by Musk or Jorgenson. [A from E, PDF pp. 33-35, "Be Useful"; pp. 55-71, "Think Like a Physicist"; pp. 113-119, "Designing the Organization"; pp. 120-138, "Innovation Needs Permission to Fail," "Simplicity Wins," and "The Algorithm"; pp. 141-160, "Maniacal Urgency" and "We Must Make Stuff"; pp. 177-180, "Listen Well, Correct Fast"; pp. 200-202, "Sequenced Strategy of Tesla"; pp. 237-240, "You Have to Blow Things Up"]

### 1. Define usefulness before activity

The book repeatedly frames success as useful output: ask how many people are helped and by how much, build something that improves on the current state, and test whether organizational effort makes a product or service better. [E, PDF pp. 33-35, "Be Useful"; pp. 214-215, "Give People More for Less"]

For agent work, this translates to a concrete requested outcome, acceptance criteria, non-goals, and proof. It argues against performative process, speculative cleanup, or producing artifacts that do not change the user's outcome. [A from E, PDF pp. 33-35, "Be Useful"; pp. 214-215, "Give People More for Less"]

### 2. Treat truth-seeking as an operating discipline

The book attributes an explicit willingness to start somewhere, question assumptions, correct mistakes, and adapt to reality. It also says to assume error, seek evidence-proportional belief, and look for feedback from all sources. [E, PDF pp. 55-60, "Obsess over Truth" and "First-Principles Thinking"; pp. 69-72, "Aspire to Be Less Wrong"]

The PayPal account adds a concrete feedback loop: the broad financial-services idea attracted little interest, while email payments did, so the team focused on the observed demand. The stated lesson is to close environmental feedback loops quickly and correct prior assumptions. [E, PDF pp. 177-180, "Listen Well, Correct Fast"]

For agents, confidence should follow evidence. Current files, tests, live state, and the requested user surface should outrank a plausible narrative. Bad news and uncertainty should be surfaced early because hiding them breaks the feedback loop. [A from E, PDF pp. 55-60, "Obsess over Truth"; p. 110, "Feedback over Feelings"; pp. 177-180, "Listen Well, Correct Fast"]

### 3. Use first principles selectively

The book defines first-principles work as finding foundational truths, reasoning upward, and checking conclusions against the axioms. Battery and rocket cost examples decompose products into material constituents and compare raw material cost with the finished product. [E, PDF pp. 59-63, "First-Principles Thinking"]

An important caveat appears in the same section: reasoning by analogy is appropriate for most of life because reconstructing everything from first principles would require too much thought. First principles are especially valuable for important or genuinely new problems constrained by convention. [E, PDF p. 59, "First-Principles Thinking"]

For agents, routine work should normally follow repository conventions, established interfaces, and known safe workflows. First-principles analysis is best reserved for a novel design, a surprising failure, an inherited assumption that blocks the outcome, or an apparent impossibility. [A from E, PDF pp. 59-63, "First-Principles Thinking"]

### 4. Think in limits and edge cases

The book recommends scaling an idea toward very large or very small values, comparing current design with a theoretically ideal arrangement, and asking what remains expensive at high volume. It also warns that the ideal changes as knowledge improves. [E, PDF pp. 64-67, "Thinking in Limits"]

For software, analogous questions include zero and maximum input, one and many users, high concurrency, network loss, repeated retries, hostile paths, latency floors, storage growth, and the ideal interface if legacy tooling were not a constraint. This is a translation of the reasoning tool, not a list provided in the book. [A from E, PDF pp. 64-67, "Thinking in Limits"]

### 5. Stay close to source evidence and actual work

The organization chapter says communication should take the shortest path needed to solve a problem, designers and manufacturers should be connected, leaders should perform skip-level checks, and people should physically go where the problem occurs. One explicit rule is to go "as close to the source as possible." [E, PDF pp. 113-117, "Remove Organizational Boundaries"]

The leadership chapter similarly argues that technical managers need hands-on experience and should spend meaningful time doing the work they manage. [E, PDF pp. 92-93, "Frontline Leadership"]

For agents, source proximity means opening the exact file, state, log, database record, issue, or user-facing surface rather than relying on a summary when direct inspection is practical. It also argues for proving integration at the seam where design, code, operations, and user behavior meet. [A from E, PDF pp. 92-93, "Frontline Leadership"; pp. 113-117, "Remove Organizational Boundaries"]

### 6. Keep communication simple and direct

The book criticizes made-up acronyms and terms that require a glossary, because people may sit silently rather than reveal they do not understand them. It favors simple, straightforward, low-ego language. [E, PDF pp. 118-119, "Simple Communication"]

For agent instructions, this supports plain verbs, one owner per state, explicit output names, and compact status language. Detailed procedures can live at the point of use instead of burdening every task with an always-loaded glossary. [A from E, PDF pp. 118-119, "Simple Communication"]

### 7. Attack the constraint, not the average

The manufacturing account says a production line moves at the rate of its slowest failing element: 9,999 working elements do not compensate for one blocked element. It also says that production systems receive vastly more work than the initial product design. [E, PDF pp. 157-160, "Attack the Constraint" and "Manufacturing Is the Moat"]

For agent work, this means identify the current blocker to the requested outcome and spend the next unit of effort there. Additional polish, broad refactoring, or more parallel tasks do not help when one unmet acceptance criterion, unavailable authority, failing dependency, or unproved boundary determines completion. [A from E, PDF pp. 157-160, "Attack the Constraint"]

### 8. Prototype early, but do not confuse prototype with delivery

The book recommends producing a mock-up, demonstration, sketch, or working prototype quickly because a tangible object helps others understand and evaluate an idea. [E, PDF p. 102, "A Group with a Goal"]

The same book later says prototypes are easy while reliable, affordable volume production is excruciatingly difficult, and emphasizes that reaching production without bankruptcy was the hard achievement. [E, PDF p. 82, "Engineering Creates Value"; p. 160, "Manufacturing Is the Moat"; pp. 200-202, "Sequenced Strategy of Tesla"]

For agents, a mock, unit test, synthetic harness, local build, or prototype can answer a design question, but it does not prove installation, deployment, persistence, production behavior, or the exact user-visible result. Those states should remain separately named. [A from E, PDF p. 102, "A Group with a Goal"; pp. 200-202, "Sequenced Strategy of Tesla"]

### 9. Use small-scale learning before scale

The Tesla strategy says the first version carries both new-technology and low-volume problems, recommends making mistakes at small scale, and only then reaching for scale. [E, PDF pp. 200-202, "Sequenced Strategy of Tesla"]

The Starship account similarly describes early units as learning exercises, eliminates doors that do not serve the immediate goal of reaching orbit, and optimizes for the shortest time to validated learning. [E, PDF pp. 237-240, "You Have to Blow Things Up"]

For agents, this supports one narrow vertical slice that proves the full path before a broad rollout, migration, generalized framework, or multi-module rewrite. [A from E, PDF pp. 200-202, "Sequenced Strategy of Tesla"; pp. 237-240, "You Have to Blow Things Up"]

### 10. Parallelize latency, not coupled ownership

The PayPal example describes setting up external financial relationships and software in parallel so they converged at the same time. The stated principle is to avoid unnecessary serialized dependencies and start independent items with unavoidable gestation periods early. [E, PDF pp. 144-146, "Do Things in Parallel"]

This does not support parallel writers on the same file, state, interface, or migration. The software-agent translation is to parallelize independent reads, checks, research lanes, builds, and external waits while preserving one writer and an explicit integration order for coupled work. [A from E, PDF pp. 144-146, "Do Things in Parallel"; coordination counterweight from E, PDF pp. 113-117, "Remove Organizational Boundaries"]

### 11. Match failure tolerance to consequence

The innovation chapter argues that punishing all failure produces conservative behavior and incremental work. It distinguishes hardworking people who made an honest technical mistake from people who lack motivation around the mission. [E, PDF pp. 122-124, "Innovation Needs Permission to Fail"]

The rocket chapter supplies the essential boundary: uncrewed early Starships were used for rapid learning, Falcon accepted some landing risk, and crewed Dragon required extreme conservatism and no tolerated failure. [E, PDF pp. 237-240, "You Have to Blow Things Up"]

For agents, cheap reversible experiments can run quickly. Security, money, credentials, destructive deletion, user data, production, irreversible migrations, and public releases require stronger checks and explicit authority. "Failure is an option" is a risk-class decision, not a universal culture rule. [A from E, PDF pp. 122-124, "Innovation Needs Permission to Fail"; pp. 237-240, "You Have to Blow Things Up"]

### 12. Use one meaningful progress signal when it clarifies the goal

The autonomy account says the team began meetings with miles per intervention because it directly measured improvement in the driving system, comparing an unscored project to a boring video game. [E, PDF p. 278, "The Last Human Drivers"]

For agents, a single measure can focus a bounded effort when it represents the real outcome: failing cases remaining, exact acceptance checks passed, latency at the user boundary, records migrated, or reproduced errors eliminated. A proxy should not replace qualitative review or safety evidence. [A from E, PDF p. 278, "The Last Human Drivers"]

### 13. Make bad news travel faster than good news

The book's exact management preference is that bad news be communicated loudly and often, while good news can be communicated quietly and once. It also says criticism should focus on an action rather than a person and that improvement depends on a functioning feedback loop. [E, PDF p. 110, "Feedback over Feelings"]

For agents, this supports early blocker reports, explicit unchecked areas, and status claims that name what is not yet proved. It does not justify hostility or stripping context from feedback. [A from E, PDF p. 110, "Feedback over Feelings"]

## Internal caveats, counterexamples, and risks

### The book is a curated success anthology, not a controlled evaluation

Jorgenson openly says the book selects useful ideas, edits and recontextualizes them, and excludes major areas of Musk's life and public activity. It therefore cannot establish that a method caused a success, that it works outside the described context, or that benefits outweigh unexamined costs. [A from J, PDF p. 16, "Notes on This Book"; pp. 22-25, "Eric's Welcome to This Book"]

The 69-method list compresses nuance further. It contains formulations that are not identical to body text and sometimes remove caveats supplied elsewhere. It should be treated as an index of hypotheses, not a policy source. [A from J, PDF pp. 336-339, "The 69 Core Musk Methods"]

### "Work like hell" is an emergency behavior, not a sustainable default

The book includes claims of 80-to-100-hour weeks and constant work, but it also attributes a direct warning that prolonged survival-mode work takes a toll, that younger Musk should have been less intense, and that he should have stopped to enjoy the moment. [E, PDF pp. 45-47, "Work Like Hell"]

The factory-floor section is more explicit: 100-hour weeks are described as something Musk would not recommend, appropriate for emergencies rather than all the time. [E, PDF p. 91, "Sleep on the Factory Floor"]

An agent instruction should therefore encode urgency, focus, and quick feedback, not glorify human sleep deprivation, user burnout, or permanent crisis mode. [A from E, PDF pp. 45-47, "Work Like Hell"; p. 91, "Sleep on the Factory Floor"]

### "Empathy is not an asset" is compiler language and is contradicted by nuance in the body

"Empathy is not an asset" appears in the explicitly edited/paraphrased 69-method list. [J, PDF p. 338, "The 69 Core Musk Methods"]

The body says Musk changed his hiring after overvaluing intellect relative to heart, says it matters whether a person is good, says criticism should target actions rather than the person, and describes retaining smart, hardworking people after good-faith launch failures because firing them would be unfair. [E, PDF p. 109, "Retain Only Special Forces"; p. 110, "Feedback over Feelings"; p. 122, "Innovation Needs Permission to Fail"]

The transferable point is to prioritize truthful feedback and enterprise outcomes without personal attack. Removing empathy from agent behavior would damage user understanding, safety judgment, and collaboration. [A from E and J, PDF pp. 109-110, "Retain Only Special Forces" and "Feedback over Feelings"; p. 122, "Innovation Needs Permission to Fail"; p. 338, "The 69 Core Musk Methods"]

### Requirements are not universally optional

The 69-method list paraphrases that all requirements should be treated as recommendations. [J, PDF p. 337, "The 69 Core Musk Methods"]

The body version is narrower: question inherited engineering requirements, identify their human owner, and check whether they serve the real need. [E, PDF pp. 132-133, "The Algorithm"]

Elsewhere, Musk-attributed material says his companies comply with an enormous body of regulation, and that objections concern a very small subset believed not to serve the public good. [E, PDF pp. 291-294, "Regulation Accumulation"]

For agents, system and developer instructions, user authority, law, safety, secrets, and explicit human gates are governing constraints. The useful action is to surface conflict or ask the owner, not silently demote the constraint. [A from E and J, PDF pp. 132-133, "The Algorithm"; pp. 291-294, "Regulation Accumulation"; p. 337, "The 69 Core Musk Methods"]

### Deletion needs an explicit recoverability class

The Algorithm deliberately encourages overdeletion and some addback. [E, PDF pp. 134-136, "The Algorithm"]

The broader book also distinguishes test articles that may explode from human-rated systems where failure is unacceptable. [E, PDF pp. 237-240, "You Have to Blow Things Up"]

For agents, in-scope Git-backed code, tests, configuration, abstractions,
dependencies, artifacts, and repository process are a recoverable class. The
agent should reject or delete members that do not serve the current outcome,
even if they might later be useful, and restore only on evidence. Addback is a
normal learning cost. User data, history, uncommitted user work, production,
credentials, money, or external systems remain under their existing authority,
recovery, and Human Gate rules. [A from E, PDF pp. 134-136, "The Algorithm";
pp. 237-240, "You Have to Blow Things Up"]

### Aggressive schedules are forcing functions, not reliable forecasts

The schedule section says internal timelines are set aggressively because work expands to fill them, but it also calls the Model 3 date impossible, admits a habit of optimism, and distinguishes a sincerely believed schedule from a knowingly fake one. [E, PDF pp. 149-151, "Set Aggressive Timelines"]

For agents, a short target can motivate decomposition and concurrency, but status and estimates must remain honest. Missing a target should update the model, not be hidden behind confidence or relabeled as completion. [A from E, PDF pp. 149-151, "Set Aggressive Timelines"]

### Speed is a vector, not a scalar

The urgency section explicitly says high speed must also be in the right direction and requires course correction. [E, PDF p. 143, "Speed Is Both Offense and Defense"]

The Algorithm makes the same point operationally by placing acceleration after requirement correction, deletion, and simplification. [E, PDF pp. 131-138, "The Algorithm"]

For agents, "speed-first" without direction, ownership, and proof can rapidly produce unrelated diffs, false status, premature automation, or unsafe external action. [A from E, PDF p. 143, "Speed Is Both Offense and Defense"; pp. 131-138, "The Algorithm"]

### Failure tolerance is asymmetric

The phrase "failure is essentially irrelevant unless it is catastrophic" is a contextual engineering claim, not permission to ignore all failures. The surrounding text discusses innovation incentives, simulations that cannot cover flight conditions, and learning from real trials. [E, PDF pp. 120-124, "Innovation Needs Permission to Fail"]

The crewed-Dragon counterexample shows that the same organization can appropriately choose near-zero failure tolerance in a high-consequence context. [E, PDF pp. 237-238, "You Have to Blow Things Up"]

Agent policy should therefore classify consequence before choosing speed, TDD depth, review, live proof, approval, or rollback. [A from E, PDF pp. 120-124, "Innovation Needs Permission to Fail"; pp. 237-238, "You Have to Blow Things Up"]

### Founder centralization does not generalize to all authority

The book attributes SpaceX's speed partly to Musk combining engineering and spending decisions in one brain, reducing negotiation between technical and financial roles. [E, PDF pp. 89-90, "Earn Deep Understanding"]

That can reduce handoff latency when one competent owner legitimately holds both authorities. It does not justify an agent combining user, reviewer, security, finance, deployment, and release authority that the user has not granted. [A from E, PDF pp. 89-90, "Earn Deep Understanding"]

### "Special Forces" and likeability language is a poor universal agent contract

The team chapters advocate exceptional ability, demanding performance, and willingness to give hard feedback. They also acknowledge scarcity of talent, the importance of heart and character, and the need to criticize actions rather than people. [E, PDF pp. 103-111, "Building Exceptional Teams"]

For agents, the useful translation is small capable teams, clear goals, direct feedback, and evidence of problem ownership. The language of retaining only "Special Forces" or treating likeability as weakness is unnecessary for file, task, or tool behavior and can distort collaboration. [A from E, PDF pp. 103-111, "Building Exceptional Teams"]

## Fit with the current `AGENTS.md`

The observed contract already owns most of the useful companion behavior:

| Existing policy owner | Source relationship | Disposition |
|---|---|---|
| Git, GitHub Issues, and the live system as distinct sources of truth | Source proximity and reality-based correction [E, PDF pp. 55-60 and 113-117] | Keep. Do not duplicate it as an Elon rule. |
| Evidence-first judgment and explicit fact, inference, estimate, and unknown states | Assume error and correct quickly [E, PDF pp. 69 and 177-180] | Keep. It is more precise than a new first-principles slogan. |
| Reversible assumptions, user-owned dirty work, and one writer per file set | Risk-tiered learning and independent parallel work [E, PDF pp. 120-124 and 144-146] | Keep. These are necessary constraints on deletion and acceleration. |
| Smallest delivery lane and narrow complete work | Staged learning and reduced process [E, PDF pp. 125-138 and 200-202] | Keep. Do not add daily Algorithm meetings or another workflow layer. |
| Fast falsifying checks, required final proof seams, and exact Live Verification | Fast feedback and prototype versus production [E, PDF pp. 82, 157-160, and 177-180] | Split cadence from final proof. Proof is not waste to delete. |
| Human Gates and distinct delivery states | Consequence-sensitive failure and authority [E, PDF pp. 120-124 and 237-240] | Keep. The bare five steps lack these safeguards. |

The best fit is one ordered Work loop. Existing Issue scope, dirty-file
ownership, authority, and Human Gate rules already protect nonrecoverable
state, so a second deletion-warning essay would cancel the intended bias. The
Work loop should own iteration cadence; Proof should own final evidence. Adding
the 69-item list, a new first-principles skill, or a recurring Algorithm
ceremony would create the process accumulation the method is intended to
remove. [A]

## Grok xhigh adversarial design review

The user explicitly requested a Grok consultation with all project knowledge.
The review ran as two prompts in one read-only Grok 4.6 Build session at xhigh
reasoning. The brief included the complete research report, attached PDF path,
both video sources, current and parent `AGENTS.md`, exact branch ancestry,
Issue #6, PR #11, version state, the writing constraints, and the user's
rejection. The session was instructed to remain read-only, and Git status was
clean between the two turns.

The first pass diagnosed six defects in the original two bullets:

1. "Before optimizing" let ordinary implementation bypass the sequence.
2. "Delete unnecessary" was circular because the agent already considered
   retained work necessary.
3. No addback rule tested whether deletion was too timid.
4. The separate danger-framed guardrail neutralized the deletion bias already
   bounded by existing authority rules.
5. Git recoverability was not used to displace just-in-case maintenance.
6. The five clauses formed a one-shot pipeline, not a feedback loop.

The resumed turn was asked to attack its own answer. It resolved the five
stages as an ordered inner sequence, the observe-correct-repeat cadence as the
outer loop, the fastest falsifying check as per-cycle feedback, and the
required or highest practical real seam as final proof. It also added a
positive keep-gate for tests that provide distinct proof of required behavior.
These are design recommendations, not source evidence; the repository owner
and this report retain the final judgment.

## Recommended compact instruction

```markdown
- Apply this order in short, closed loops until required proof passes or a
  blocker requires handoff. Keep each loop to the smallest meaningful
  integrated change or experiment and the fastest available check that can
  falsify the current assumption. Inspect the result, correct the model and
  implementation, expose bad news immediately, then repeat:
  1. Establish the useful outcome. Challenge inherited requirements,
     assumptions, and ownership before accepting the proposed path. The user's
     stated outcome, explicit constraints, governing instructions, and Human
     Gates remain binding.
  2. Reject or delete in-scope Git-backed code, tests, configuration,
     abstractions, dependencies, scope, artifacts, process, and ceremony that
     do not serve the current outcome, even if they might later be useful.
     Rely on committed Git history for later recovery. Restore only when
     evidence shows the removed work is required for the current outcome.
     Addback maps the tested boundary and is a normal cost of learning, not
     proof that deletion was wrong. Keep a test only when it provides distinct
     proof of required behavior.
  3. Simplify only what survives deletion.
  4. After the path is sound, shorten iteration time and attack the current
     constraint.
  5. Automate only a necessary, stable, proven, recurring loop.
```

This keeps the five stages ordered and makes the sequence repeat until proof or
a real blocker. It treats possible future usefulness as an invalid reason to
maintain recoverable work, treats evidence-driven addback as boundary learning,
places constraint focus after direction is sound, and keeps automation last.
The adjacent Proof edit prevents a fast cycle check from being confused with
final proof. [A from P, *Starbase Tour Part 1*, 13:29-24:48; E, PDF pp. 55-60,
110, 120-138, 177-180, and 237-240; W, requested conversation,
11:26-21:45 and 54:10-55:47]

The wording should replace overlap instead of becoming a philosophy section.
The title "Algorithm" can remain in the Issue and research lineage without
requiring every agent to know Musk or McNeill. The loaded instruction itself is
self-explanatory. [A]

## Scenario review

| Case | Expected behavior under the wording | Result |
|---|---|---|
| Git-backed just-in-case abstraction | Reject or delete it when it does not serve the current outcome. Use committed history for recovery. | Future usefulness is not a maintenance requirement. |
| Redundant test | Delete it when it adds no distinct proof of required behavior. | Test count is not the goal; required proof is. |
| Unique regression test | Keep it because it provides distinct proof of required behavior. | Deletion does not erase the last required proof. |
| Evidence-driven addback | Restore the removed path, record the tested boundary, and continue the loop. | Addback is learning, not deletion failure. |
| Fast local falsification check | Run it in the current loop instead of waiting for the full suite. | Feedback arrives at the shortest useful cycle. |
| Final public-seam proof | Run the required seam even after local checks and a broad suite pass. | Fast feedback does not replace final proof. |
| Valid direct user constraint | Challenge the path, not the binding outcome or constraint. | Does not authorize silent reinterpretation. |
| Nonrecoverable or Human-Gated state | Existing dirty-file, authority, and Human Gate rules govern it. | Git deletion bias does not manufacture external authority. |
| One-off task | Perform it without adding a scheduler, skill, hook, or framework. | Automation remains last. |
| Real bottleneck | Delete and simplify first, then attack the current constraint. | Speed receives direction. |

## Final disposition of other methods

### Keep in the always-loaded core through existing rules

1. **Reality and source proximity:** inspect the exact source and user surface;
   evidence beats confidence. [E, PDF pp. 55-60, 113-117, and 177-180; W,
   requested conversation, 11:26-21:45]
2. **Constraint focus:** put the next effort into the blocker that determines
   completion. [E, PDF pp. 157-160; W, requested conversation, 16:57-17:12]
3. **Risk-tiered iteration:** move quickly on reversible experiments and
   protect high-consequence and human-gated boundaries. [E, PDF pp. 120-124
   and 237-240]
4. **Fast bad news:** surface blockers, uncertainty, and unchecked areas early.
   [E, PDF p. 110]
5. **Compact decision updates:** lead with problem, cause, and proposed
   solution when that structure fits. Preserve detail when correctness needs
   it. [W, requested conversation, 39:35-40:50; A]

### Use only for suitable deeper work

1. **First-principles decomposition:** valuable for important novel problems,
   too expensive as a universal ritual. [E, PDF pp. 59-63]
2. **Thinking in limits:** useful for architecture, scale, reliability, and
   edge cases, but task-dependent. [E, PDF pp. 64-67]
3. **Order-of-magnitude design probes:** useful for exposing a redesign, not a
   reliable forecast or default target. [W, requested conversation,
   33:11-38:15; A]
4. **One key metric:** useful when it faithfully represents the outcome and
   dangerous when it is only a proxy. [E, PDF p. 278]
5. **Prototype-first learning:** appropriate for uncertainty when prototype
   status remains explicit and production proof follows. [E, PDF p. 102 and
   pp. 200-202]

### Reject as general agent instructions

1. **Permanent ultra-hardcore work:** the body limits extreme hours to
   emergencies and records their cost. [E, PDF pp. 45-47 and p. 91]
2. **"Empathy is not an asset":** an editorial paraphrase that conflicts with
   body nuance and good collaboration. [E, PDF pp. 109-110 and p. 122; J, PDF
   p. 338]
3. **All requirements are optional:** unsafe under instruction precedence,
   law, safety, and human authority. [E, PDF pp. 132-133 and 291-294; J, PDF
   p. 337]
4. **Universal 10 percent addback:** a rocket-engineering bias correction, not
   a deletion quota for all software state. [P, *Starbase Tour Part 1*,
   13:56-17:17; E, PDF pp. 134-136]
5. **Failure is irrelevant:** false without consequence classification. [E,
   PDF pp. 120-124 and 237-240]
6. **Aggressive dates as completion claims:** the book records optimism and
   impossible schedules. [E, PDF pp. 149-151]
7. **Unauthorized action as initiative:** a successful anecdote does not
   manufacture authority for an agent. [W, requested conversation,
   12:43-15:10; A]
8. **One-person concentration of all decisions:** it may reduce founder
   latency, but it cannot combine user, security, finance, release, and
   deployment authority in an agent. [E, PDF pp. 89-90; A]

## Implementation state

Issue #6 was reimplemented from released v3.1.0 main after the approved
Partnership contract shipped. The replacement preserves the complete
source-checked research and imports its durable conclusions into the stronger
explanatory Algorithm approved by the user. Existing PR #11 remains historical
pre-v3.0.0 evidence and must not be merged.

The exact pre-edit v3.1.0 global contract is preserved in `agentsmd-archive/`.
The final branch owns only the Algorithm, its research and focused contract
test, the archive, and the required SemVer artifacts. Project Direction remains
owned by Issue #20.

## Bottom line

The durable lesson is procedural, not biographical: establish the useful
outcome, challenge the path, delete recoverable work that does not serve it,
simplify the survivors, shorten the loop through the current constraint, and
automate only a stable proven recurrence. Use fast falsification to correct the
model and implementation, and let evidence-driven addback map the deletion
boundary. [P, *Starbase Tour Part 1*, 13:29-24:48; E, PDF pp. 55-60, 110,
131-138, and 177-180]

The useful companions are reality-based observation, explicit final proof,
current-constraint focus, reversible iteration, fast bad news, and compact
decision communication. The right change is one forceful Work loop and one
consolidated Proof rule, not a Musk persona, a 69-rule manifesto, or another
workflow system. [A from the sources above]
