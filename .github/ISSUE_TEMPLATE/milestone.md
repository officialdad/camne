---
name: Milestone
about: Track a milestone with enough context to resume on any machine
title: "milestone N: <name>"
labels: milestone
---

<!--
Fill every section. The test for a good milestone issue: someone (or an agent)
on a fresh machine, with only this issue + the repo, can start working in
under five minutes without asking anything.
-->

## Goal

<!-- One paragraph. What exists when this closes that does not exist now. -->

## Spec

<!-- What defines this milestone: the behaviour it must have when it closes. -->

## State when this issue was written

<!-- Repo commit, what is already merged that this builds on, and anything
     half-done. Name exact packages/files/consts the work touches. -->

## Machine / resource requirements

<!-- GPU? Disk? Wall time? Network? Accounts (HF, GitHub)? Anything the
     target machine must have before starting. "None special" is a valid
     answer. -->

## Deliverables

<!-- Checklist. Each item independently verifiable. Numbers required where
     CLAUDE.md demands them (model work: eval + perf tables, McNemar, seeds). -->

- [ ]

## How to resume

<!-- Exact first commands on a fresh machine: clone, build, test, then the
     first real step of the work. Include verification commands that prove
     the starting state is healthy. -->

```sh
git clone https://github.com/officialdad/camne && cd camne
go build ./... && go test ./...
```

## References

<!-- Prior art, datasets, model cards, upstream docs. Pin versions/tags. -->
