"""str_replace_editor tool implementation.

Implements the same file editor interface used in SWE-bench and the SERA
training data. The model was trained to call this tool with 5 commands:

  view         — Display file contents with line numbers (cat -n style)
                 Supports view_range=[start, end] for partial views
                 Also works on directories (lists entries)

  str_replace  — Replace a unique string in a file
                 Requires old_str (must match exactly once) and new_str
                 Rejects ambiguous replacements (multiple matches)
                 Shows context around the edit after applying

  create       — Create a new file with given content
                 Fails if file already exists

  insert       — Insert text at a specific line number
                 Line 0 = before first line, line N = after line N

  undo_edit    — Revert the last edit to a file
                 Maintains a per-file undo stack

Output format matches what the model saw during training:
  "Here's the result of running `cat -n` on /path/to/file:\n..."
  "The file /path has been edited. Here's the result of running..."
"""

from __future__ import annotations

from pathlib import Path


class EditorError(Exception):
    """Raised for recoverable editor errors (shown to the model)."""
    pass


class Editor:
    """File editor with undo support."""

    def __init__(self, working_dir: str = "/"):
        self.working_dir = Path(working_dir)
        self._undo_stack: dict[str, list[str | None]] = {}

    def execute(self, args: dict[str, str]) -> str:
        """Execute an editor command. Returns output string."""
        command = args.get("command", "")
        path_str = args.get("path", "")

        if not command:
            return "ERROR: 'command' parameter is required."
        if not path_str:
            return "ERROR: 'path' parameter is required."

        path = self._resolve(path_str)

        try:
            if command == "view":
                return self._view(path, args.get("view_range"))
            elif command == "str_replace":
                return self._str_replace(path, args.get("old_str", ""), args.get("new_str", ""))
            elif command == "create":
                return self._create(path, args.get("file_text", ""))
            elif command == "insert":
                return self._insert(path, args.get("insert_line", ""), args.get("new_str", ""))
            elif command == "undo_edit":
                return self._undo(path)
            else:
                return f"ERROR: Unknown command '{command}'. Use: view, str_replace, create, insert, undo_edit"
        except EditorError as e:
            return f"ERROR: {e}"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    def _resolve(self, path_str: str) -> Path:
        """Resolve path relative to working dir."""
        p = Path(path_str)
        if not p.is_absolute():
            p = self.working_dir / p
        return p

    def _save_undo(self, path: Path) -> None:
        """Save current file content for undo."""
        key = str(path)
        if key not in self._undo_stack:
            self._undo_stack[key] = []
        if path.exists():
            self._undo_stack[key].append(path.read_text())
        else:
            self._undo_stack[key].append(None)

    def _view(self, path: Path, view_range: str | None) -> str:
        """View file or directory contents."""
        if path.is_dir():
            entries = sorted(path.iterdir())
            lines = [str(e.relative_to(path)) + ("/" if e.is_dir() else "") for e in entries[:100]]
            result = "\n".join(lines)
            if len(entries) > 100:
                result += f"\n... and {len(entries) - 100} more entries"
            return result

        if not path.exists():
            raise EditorError(f"File not found: {path}")

        content = path.read_text()
        lines = content.splitlines(keepends=True)

        if view_range:
            range_str = view_range.strip("[] ")
            parts = [p.strip() for p in range_str.split(",")]
            try:
                start = int(parts[0])
                end = int(parts[1]) if len(parts) > 1 else len(lines)
            except (ValueError, IndexError):
                raise EditorError(f"Invalid view_range: {view_range}. Use [start, end].")
            start = max(1, start)
            end = min(len(lines), end)
            selected = lines[start - 1 : end]
            offset = start
        else:
            selected = lines
            offset = 1

        numbered = []
        for i, line in enumerate(selected):
            line_no = offset + i
            numbered.append(f"{line_no:6d}\t{line.rstrip()}")
        return f"Here's the result of running `cat -n` on {path}:\n" + "\n".join(numbered)

    def _str_replace(self, path: Path, old_str: str, new_str: str) -> str:
        """Replace a unique string in a file."""
        if not path.exists():
            raise EditorError(f"File not found: {path}")
        if not old_str:
            raise EditorError("'old_str' parameter is required for str_replace.")

        content = path.read_text()
        count = content.count(old_str)

        if count == 0:
            lines = content.splitlines()
            snippet = "\n".join(lines[:30])
            raise EditorError(
                f"No match found for old_str in {path}. "
                f"File has {len(lines)} lines. First 30 lines:\n{snippet}"
            )
        if count > 1:
            line_nos = []
            offset = 0
            for _ in range(count):
                idx = content.index(old_str, offset)
                line_no = content[:idx].count("\n") + 1
                line_nos.append(line_no)
                offset = idx + 1
            raise EditorError(
                f"Multiple matches ({count}) found for old_str in {path} "
                f"at lines {line_nos}. Make old_str more specific."
            )

        self._save_undo(path)
        new_content = content.replace(old_str, new_str, 1)
        path.write_text(new_content)

        new_lines = new_content.splitlines()
        replace_start = content.index(old_str)
        start_line = content[:replace_start].count("\n")
        end_line = start_line + new_str.count("\n") + 1
        context_start = max(0, start_line - 3)
        context_end = min(len(new_lines), end_line + 3)
        snippet = "\n".join(f"{i+1:6d}\t{new_lines[i]}" for i in range(context_start, context_end))
        return (
            f"The file {path} has been edited. Here's the result of running "
            f"`cat -n` on a snippet of {path}:\n{snippet}\n"
            f"Review the changes and make sure they are as expected. Edit the file again if necessary."
        )

    def _create(self, path: Path, file_text: str) -> str:
        """Create a new file."""
        if path.exists():
            raise EditorError(f"File already exists: {path}. Use str_replace to edit it.")

        self._save_undo(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file_text)
        return f"File created successfully at: {path}"

    def _insert(self, path: Path, insert_line: str, new_str: str) -> str:
        """Insert text at a specific line number."""
        if not path.exists():
            raise EditorError(f"File not found: {path}")

        try:
            line_no = int(insert_line)
        except (ValueError, TypeError):
            raise EditorError(f"Invalid insert_line: {insert_line}. Must be an integer.")

        content = path.read_text()
        lines = content.splitlines(keepends=True)

        if line_no < 0 or line_no > len(lines):
            raise EditorError(f"insert_line {line_no} out of range [0, {len(lines)}].")

        self._save_undo(path)
        new_lines_to_insert = new_str.splitlines(keepends=True)
        if new_lines_to_insert and not new_lines_to_insert[-1].endswith("\n"):
            new_lines_to_insert[-1] += "\n"

        lines[line_no:line_no] = new_lines_to_insert
        path.write_text("".join(lines))

        ctx_start = max(0, line_no - 3)
        ctx_end = min(len(lines), line_no + len(new_lines_to_insert) + 3)
        snippet = "\n".join(f"{i+1:6d}\t{lines[i].rstrip()}" for i in range(ctx_start, ctx_end))
        return f"The file {path} has been edited. Here's the result of running `cat -n` on a snippet:\n{snippet}"

    def _undo(self, path: Path) -> str:
        """Undo the last edit to a file."""
        key = str(path)
        if key not in self._undo_stack or not self._undo_stack[key]:
            raise EditorError(f"No edit history for {path}.")

        prev = self._undo_stack[key].pop()
        if prev is None:
            if path.exists():
                path.unlink()
            return f"Undo: removed {path} (it didn't exist before the edit)."
        else:
            path.write_text(prev)
            return f"Undo: restored {path} to previous version."
