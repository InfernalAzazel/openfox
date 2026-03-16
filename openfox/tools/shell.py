import subprocess



def run_shell(command: str) -> str:
    """
    执行本地 shell 命令。

    参数:
        command: 要执行的完整 shell 命令（执行前会要求用户确认）。
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
        return f"执行失败: {e}"