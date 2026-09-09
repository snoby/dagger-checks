"""Shared CI checks for viporlab repos (Dagger module).

Each check is an independently-callable, independently-cacheable Dagger
function. A repo "enables" a check by calling it; disabling a check means not
calling it (no dead CI branches).

Run from a workflow against the always-on shared engine, e.g.:
    dagger call --module <this> lint --source=.
"""

import dagger
from dagger import function, object_type

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
            .with_mounted_directory("/src", source)
            .with_workdir("/src")
            .with_exec(["pip", "install", "--quiet", "trufflehog"])
        )
        # Scan the tree (no git required uses --no-update).
        return await container.with_exec(["trufflehog", "filesystem", "--no-update", "."]).stdout()

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
