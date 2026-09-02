# Objective

Ship use-grok as one portable ToolboxMD plugin across Codex, Claude Code, and
Grok Build.

Completion requires all three host manifests to share the canonical plugin
identity and version, preserve required portable metadata, omit Codex-only
fields from other hosts, and have contract tests that detect cross-host
identity or version drift while existing Codex behavior remains unchanged.

Non-goals are wrapping Grok in an adapter, changing Grok CLI semantics, or
changing the default unrestricted delegation policy.
