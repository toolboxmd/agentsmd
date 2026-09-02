# Task: Keep Pointer Pages Out of Indexes

Pointer pages preserve old wiki paths after their useful content moves into a
playbook. Keep those files on disk, but omit pages whose parsed frontmatter has
a `pointer` tag from generated navigation and discovery statistics.

Required behavior:

- recognize the `pointer` tag case-insensitively and after trimming whitespace;
- omit proven pointer pages from category page rows;
- omit them from recursive subdirectory counts and title previews;
- omit them from discovery counts and maximum depth;
- make the root index reflect the filtered discovery counts and depth;
- keep pointer files unchanged on disk;
- keep ordinary pages visible; and
- treat missing, malformed, non-mapping, filesystem-unreadable, or non-UTF-8
  frontmatter conservatively as not proven to be a pointer, without crashing.

Allowed paths:

- `scripts/wiki-build-index.py`
- `scripts/wiki-discover.py`
- `tests/unit/test-build-index.sh`

Public verifier:

```bash
/usr/bin/python3 -B .benchmark/public/karpathy_pointer_smoke.py --workspace .
```

The public verifier is read-only benchmark input. Candidate-owned tests are
supplemental evidence only. Do not delete or rewrite wiki content, change the
wiki schema, modify discovery output shape, or change the public verifier.
