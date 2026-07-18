import shutil
import subprocess


CODE_QUESTION_TYPES = {"code_writing", "debugging", "error_identification"}


def execute_python_in_isolated_sandbox(source: str) -> dict:
    """Run learner code only through a disposable, network-disabled Docker container.

    The web process never executes learner code directly. If Docker or the configured
    Python image is unavailable, grading can continue but the result must be reviewed.
    """
    if not shutil.which("docker"):
        return {
            "status": "unavailable",
            "message": "The isolated execution service is unavailable; teacher review is required.",
        }

    image_check = subprocess.run(
        ["docker", "image", "inspect", "python:3.12-alpine"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if image_check.returncode != 0:
        return {
            "status": "unavailable",
            "message": "The isolated Python sandbox image is not installed; teacher review is required.",
        }

    command = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--memory=128m",
        "--cpus=0.5",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m",
        "python:3.12-alpine",
        "python",
        "-I",
        "-c",
        source,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "unavailable" if isinstance(exc, OSError) else "failed",
            "message": "The isolated execution service could not complete safely.",
        }

    return {
        "status": "succeeded" if completed.returncode == 0 else "failed",
        "return_code": completed.returncode,
        "stdout": completed.stdout[:4000],
        "stderr": completed.stderr[:4000],
    }


def execution_context_for_submission(submission, question_type: str) -> dict:
    if question_type not in CODE_QUESTION_TYPES:
        return {}
    result = execute_python_in_isolated_sandbox(submission.answer_text)
    submission.execution_status = result["status"]
    submission.execution_result = result
    submission.save(update_fields=["execution_status", "execution_result"])
    return result
