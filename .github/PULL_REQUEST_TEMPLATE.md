## Summary

<!-- 1?? bullets describing the change and the problem it solves. -->

## Changes

- [ ] Code change(s)
- [ ] Tests added or updated
- [ ] Docs updated (CHANGELOG, README, docs/*)

## Verification

<!--
How did you test this? Devnet transaction signatures, before/after metrics,
or local test commands.
-->

```bash
cargo test --workspace
cd sdk && npm test
```

## Checklist

- [ ] Followed conventional commit format
- [ ] No security-sensitive changes (or, if so, coordinated via SECURITY.md)
- [ ] No accidental program-id / account-layout changes that break callers
