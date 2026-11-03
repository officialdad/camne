## Needs you

<!-- One line. What the human must do. Example: Merge, or request changes. -->

## Summary

<!-- 2 to 4 short sentences. What changes and why. -->

## Risk

<!-- One line, or: None known. -->

<details>
<summary>Agent detail</summary>

### Component(s)

<!-- Name the directories or services touched. -->

### Type

<!-- Keep the lines that apply. -->

- [ ] Added
- [ ] Changed
- [ ] Fixed
- [ ] Removed
- [ ] Plumbing (CI, shared config, docs)

### Changes

<!-- One bullet per notable change. -->

-

### Validation

<!-- List each check you ran and its result. -->

- [ ] `go build ./...`, `go test ./...` and `go vet ./...` pass
- [ ] `gofmt -l .` and staticcheck print nothing
- [ ] Non-trivial logic has a table-driven `go test`
- [ ] `internal/safety` tests are not weakened
- [ ] A model or dataset change lists numbers, not examples (see `CLAUDE.md`)
- [ ] A new Go module has a written justification in this PR
- [ ] User-facing text is plain English, and Malay and rojak input still work
- [ ] CI is green

</details>
