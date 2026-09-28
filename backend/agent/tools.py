from pathlib import Path

from langchain_core.tools import tool
from .workspace import emit, project_root

def safe_read_file(path: str) -> str:
    """
    Read an existing UTF-8 file without raising an exception.

    Returns an empty string when the path is invalid,
    missing, or is not a regular file.
    """

    try:
        safe_file = safe_path_for_project(path)
    except ValueError:
        return ""

    if not safe_file.exists():
        return ""

    if not safe_file.is_file():
        return ""

    try:
        return safe_file.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError):
        return ""


def safe_path_for_project(path: str = ".") -> Path:
    """
    Resolve a path inside generated_project.

    Accepted:
    - .
    - index.html
    - src/components/App.jsx
    - generated_project/index.html
    - an absolute path already inside generated_project

    Rejected:
    - ../secret.txt
    - absolute paths outside generated_project
    """

    root = project_root()
    raw_path = str(path or ".").strip()

    if not raw_path:
        raw_path = "."

    candidate = Path(raw_path)

    # Évite generated_project/generated_project/file
    if (
        not candidate.is_absolute()
        and candidate.parts
        and candidate.parts[0].lower()
        in {root.name.lower(), "generated_project"}
    ):
        candidate = Path(*candidate.parts[1:])

    if candidate.is_absolute():
        resolved_path = candidate.resolve()
    else:
        resolved_path = (
            root / candidate
        ).resolve()

    try:
        resolved_path.relative_to(root)
    except ValueError as error:
        raise ValueError(
            "Path must be relative to generated_project. "
            f"Received: {path!r}. "
            "Use paths such as '.', 'index.html', "
            "'src/App.jsx' or 'styles/main.css'."
        ) from error

    return resolved_path


@tool
def list_files(directory: str = ".") -> str:
    """
    List files and directories inside generated_project.

    Always use project-relative paths such as "." or "src".
    """

    try:
        safe_directory = safe_path_for_project(directory)
    except ValueError as error:
        return f"Invalid directory path. {error}"

    if not safe_directory.exists():
        return (
            f"Directory does not exist: {directory!r}. "
            'Use list_files(".") to inspect the project root.'
        )

    if not safe_directory.is_dir():
        relative_path = safe_directory.relative_to(
            project_root()
        ).as_posix()

        return (
            f"'{relative_path}' is a file, not a directory. "
            f"Use read_file('{relative_path}') instead."
        )

    entries = sorted(
        safe_directory.iterdir(),
        key=lambda item: (
            not item.is_dir(),
            item.name.lower(),
        ),
    )

    if not entries:
        relative_directory = safe_directory.relative_to(
            project_root()
        ).as_posix()

        return (
            f"Directory is empty: "
            f"{relative_directory or '.'}"
        )

    results: list[str] = []

    for item in entries:
        relative_path = item.relative_to(
            project_root()
        ).as_posix()

        item_type = (
            "directory"
            if item.is_dir()
            else "file"
        )

        results.append(
            f"{item_type}: {relative_path}"
        )

    return "\n".join(results)


@tool
def read_file(path: str) -> str:
    """
    Read a UTF-8 file inside generated_project.
    Use a project-relative path.
    """

    try:
        safe_file = safe_path_for_project(path)
    except ValueError as error:
        return f"Invalid file path. {error}"

    if not safe_file.exists():
        return (
            f"File does not exist: {path!r}. "
            "It may need to be created."
        )

    if not safe_file.is_file():
        relative_path = safe_file.relative_to(
            project_root()
        ).as_posix()

        return (
            f"'{relative_path}' is a directory. "
            f"Use list_files('{relative_path}') instead."
        )

    try:
        return safe_file.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return (
            f"Unable to read {path!r}: "
            "the file is not valid UTF-8 text."
        )
    except OSError as error:
        return f"Unable to read {path!r}: {error}"


@tool
def write_file(path: str, content: str) -> str:
    """
    Create or overwrite a UTF-8 file inside generated_project.
    Use a project-relative path.
    """

    if len(content.encode("utf-8")) > 1_000_000:
        return "File is too large. Keep each file below 1 MB."

    try:
        safe_file = safe_path_for_project(path)
    except ValueError as error:
        return f"Invalid file path. {error}"

    if safe_file.exists() and safe_file.is_dir():
        return (
            f"Cannot write to {path!r}: "
            "the path is a directory."
        )

    try:
        safe_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_file.write_text(
            content,
            encoding="utf-8",
            newline="\n",
        )
    except OSError as error:
        return f"Unable to write {path!r}: {error}"

    relative_path = safe_file.relative_to(
        project_root()
    ).as_posix()

    emit({"type": "file", "path": relative_path, "content": content})

    return (
        f"File written successfully: {relative_path}"
    )


@tool
def get_current_directory() -> str:
    """
    Return instructions about the generated-project root.
    """

    return (
        "The tool workspace is generated_project. "
        "All tool paths must be relative to this root. "
        "Use '.' to represent the root directory. "
        "Do not send an absolute filesystem path."
    )
