# Git standards

**Applies to:** repository development, not Git data embedded in evaluation
fixtures. Load only the rules relevant to the requested operation.

`MUST` is required; `SHOULD` is the default unless a documented reason justifies
an exception. Examples are illustrative, not exhaustive allowlists. These
standards describe how to perform an operation; they do not authorize creating
branches, commits, tags, or remote updates.

## cs:git.branch.name

- **Level:** MUST
- **Applies when:** creating or renaming a development branch.
- **Requirement:** use `<type>/<description>`. The type communicates intent
  (such as `feat`, `fix`, or `chore`); the description uses kebab-case.
- **Verify:** check that the name has an intent prefix, a `/` separator, and a
  kebab-case description. Use `git check-ref-format --branch <name>` to also
  validate Git syntax; it does not enforce this naming convention.
- **Examples:** `feat/fixture-validation`, `fix/checkpoint-budget`,
  `chore/update-dependencies`.

## cs:git.commit.message

- **Level:** MUST
- **Applies when:** preparing a commit that will land on the main branch.
- **Requirement:** follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
  Use `type(scope): description`; scope is optional. Include `!` or a
  `BREAKING CHANGE:` footer for breaking changes as defined by the specification.
  Write the description so it completes “this commit will…”.
- **Verify:** inspect the subject for a type, optional scope/breaking marker,
  `: ` separator, and a nonempty imperative description. Check any breaking
  change footer against the specification.
- **Examples:** `fix(validator): reject duplicate tool call IDs`,
  `docs: explain continuation budgets`.

## cs:git.commit.scope

- **Level:** SHOULD
- **Applies when:** choosing a scope for a conventional commit.
- **Requirement:** identify the affected package, module, or domain. In a
  monorepo, use the package name without its namespace; in a single-package
  repository, use the module or feature area. Reuse established scopes for
  consistent history. This rule does not make scopes mandatory.
- **Verify:** compare the scope with the changed area and existing history,
  if available.
- **Example:** `fix(validator): reject invalid snapshot paths`.

## cs:git.merge-proposal.description

- **Level:** MUST
- **Applies when:** writing or updating a merge-proposal description.
- **Requirement:** give a brief, reviewer-facing summary of the problem and
  intended outcome. Leave implementation details in the diff. Add a short
  verification note when useful.
- **Verify:** a reviewer can identify the problem and outcome without reading
  a narration of the diff. Any claimed verification was actually performed.

## cs:git.tag.versioning

- **Level:** MUST
- **Applies when:** creating a release tag or configuring release-version tooling.
- **Requirement:** use [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
  with a `v` prefix and an annotated tag, not a lightweight tag. Pre-release
  identifiers follow the patch number after a hyphen. Automated tooling should
  derive bumps from conventional commits: `feat` → minor, `fix` → patch,
  breaking changes → major.
- **Verify:** validate the version against SemVer after removing the `v`
  prefix. For an existing tag, the following read-only check must return
  `tag`, not `commit`:

  ```sh
  git for-each-ref refs/tags/<tag> --format='%(objecttype)'
  ```
- **Examples:** `v1.2.3`, `v2.0.0-rc.1`.

## cs:git.commit.context

- **Level:** SHOULD
- **Applies when:** a coding harness prepares a commit.
- **Requirement:** include relevant task context, considerations, decisions,
  and the scope of any specification used. Put a concise summary in the commit
  body or link to a durable task/specification record. Record decision outcomes,
  not hidden reasoning, credentials, or raw agent transcripts.
- **Verify:** a future maintainer can identify the intended scope, important
  constraints, decisions, and applicable specification without the agent session.
- **Legacy ID:** `cs.git.commit.context`; use `cs:git.commit.context` in new references.
