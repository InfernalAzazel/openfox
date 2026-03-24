import subprocess


def run_shell(command: str) -> str:
    """
    Run a local shell command.

    Args:
        command: Full shell command to run (user confirmation is required before execution).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=60,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stderr:
            return f"STDERR:\n{stderr}\n\nSTDOUT:\n{stdout}"

        return stdout or "(no output)"

    except Exception as e:
        return f"Execution failed: {e}"
