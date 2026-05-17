import subprocess
import sys


def test_cli_worker_is_registered():
    # Help output rather than actually starting celery.
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "worker" in result.stdout
    assert "migrate" in result.stdout


def test_cli_migrate_dry_run_prints_version():
    result = subprocess.run(
        [sys.executable, "main.py", "migrate", "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "head" in result.stdout.lower() or "revision" in result.stdout.lower()
