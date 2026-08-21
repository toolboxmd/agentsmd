# versionctl

`versionctl` is the deterministic mechanics layer for repository SemVer. It
reads `.version-policy.json`, treats the root `VERSION` file as canonical,
synchronizes declared JSON and TOML mirrors, maintains `CHANGELOG.md`, and
validates exact Git release identity.

Run it from an adopted repository through the bundled launcher:

```sh
tools/versionctl/bin/versionctl doctor
tools/versionctl/bin/versionctl prepare patch --reason "Correct documentation"
tools/versionctl/bin/versionctl release-check
```

The runtime has no third-party Python dependencies. Python 3.11 or newer and
Git are required.
