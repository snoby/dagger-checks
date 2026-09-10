"""Shared CI checks for viporlab repos (Dagger module).

Each check is an independently-callable, independently-cacheable Dagger
function. A repo "enables" a check by calling it; disabling a check means not
calling it (no dead CI branches).

Run from a workflow against the always-on shared engine, e.g.:
    dagger call --module <this> lint --source=.
"""

import dagger
from dagger import dag, function, object_type

# Base image with linting/static-analysis tooling. Kept on a stable tag so
# layer caching stays warm.
LINT_IMAGE = "python:3.12-slim"
TEST_IMAGE = "python:3.12-slim"
BUILD_IMAGE = "python:3.12-slim"


@object_type
class Checks:
    @function
    async def lint(self, source: dagger.Directory) -> str:
        """Run static analysis/linting over a source directory.

        Returns formatted tool output (e.g. ruff) that fails the step on a
        non-zero exit. Cacheable per input tree.
        """
        return await (
            dag.container()
            .from_(LINT_IMAGE)
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "--no-install-recommends", "git"])
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["pip", "install", "--quiet", "ruff"])
            .with_exec(["ruff", "check", "."])
            .stdout()
        )

    @function
    async def pii_scan(self, source: dagger.Directory) -> str:
        """Scan source for likely secrets / PII.

        Uses gitleaks-style regexes (trufflehog lightweight) via a small scan.
        Returns a report; exits non-zero if secrets/PII are found.
        """
        container = (
            dag.container()
            .from_(LINT_IMAGE)
            .with_exec(["apt-get", "update"])
            .with_exec(["apt-get", "install", "-y", "--no-install-recommends", "git"])
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["pip", "install", "--quiet", "trufflehog"])
        )
        # Scan the tree directory in-place (truffleHog 2.x CLI; no git needed).
        return await container.with_exec(["trufflehog", "--regex", "--entropy=False", "."]).stdout()

    @function
    async def test(self, source: dagger.Directory) -> str:
        """Run the unit test suite (pytest) inside a container."""
        return await (
            dag.container()
            .from_(TEST_IMAGE)
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["pip", "install", "--quiet", "pytest"])
            .with_exec(["pytest", "-q"])
            .stdout()
        )

    @function
    async def build(self, source: dagger.Directory) -> dagger.Container:
        """Build a container image of the project (Docker-style) and return it.

        The resulting container is exportable/cacheable (a buildkit layer),
        so unchanged sources skip the rebuild on subsequent runs.
        """
        return (
            dag.container()
            .from_(BUILD_IMAGE)
            .with_directory("/app", source)
            .with_default_args(["python", "app.py"])
        )

    @function
    async def static_analyzer(self, source: dagger.Directory) -> str:
        """Run a static analyzer over the source.

        STUB: placeholder for a real static-analysis gate (e.g. bandit /
        semgrep / sonarqube). Returns a no-op report and exits 0; wire the
        real tool + ruleset here and fail the step on findings.
        """
        return await (
            dag.container()
            .from_(LINT_IMAGE)
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["sh", "-c", "echo '[static-analyzer] STUB: no analyzer configured'; exit 0"])
            .stdout()
        )

    @function
    async def private_key_check(self, source: dagger.Directory) -> str:
        """Check the source for exposed private keys / seed material.

        STUB: placeholder for a private-key / wallet-seed detector (e.g.
        gitleaks 'privatekey' rule, yara, or a wallet-privkey scanner).
        Exits 0 regardless pending the real detector.
        """
        return await (
            dag.container()
            .from_(LINT_IMAGE)
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["sh", "-c", "echo '[private-key-check] STUB: no private-key detector configured'; exit 0"])
            .stdout()
        )

    @function
    async def format(self, source: dagger.Directory) -> str:
        """Format-check the source.

        STUB: placeholder for a formatter/diff gate (e.g. black --check /
        ruff format --check / clang-format). Exits 0 pending a real formatter;
        when wired, return non-zero with a diff if formatting is required.
        """
        return await (
            dag.container()
            .from_(LINT_IMAGE)
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["sh", "-c", "echo '[format] STUB: no formatter configured'; exit 0"])
            .stdout()
        )
