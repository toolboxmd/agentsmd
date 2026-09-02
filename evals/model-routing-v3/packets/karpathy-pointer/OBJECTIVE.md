# Objective

Preserve old wiki paths as pointer pages without allowing those pointers to
distort discovery or navigation.

Completion requires pointer-tagged pages to remain on disk and resolve to their
playbooks while staying out of category rows, recursive counts and previews,
discovery counts and depth, and the root index. Pages whose pointer status
cannot be proven because frontmatter is malformed or unreadable remain
conservatively visible without crashing the indexer.

Non-goals are deleting pointer pages, rewriting their bodies, changing
playbook synthesis, or changing the wiki schema.
