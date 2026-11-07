import re
from dataclasses import dataclass, field


_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


@dataclass
class ChangedLines:
    old: list[int] = field(default_factory=list)
    new: list[int] = field(default_factory=list)


def parse_changed_lines(patch: str | None) -> ChangedLines:
    result = ChangedLines()
    if not patch:
        return result

    old_line = new_line = None
    for line in patch.splitlines():
        match = _HUNK_HEADER.match(line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            continue
        if old_line is None or new_line is None or line.startswith("\\ No newline"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result.new.append(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            result.old.append(old_line)
            old_line += 1
        else:
            old_line += 1
            new_line += 1

    return result
