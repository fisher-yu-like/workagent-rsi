"""Lexical checks happen before any path resolution or export side effect."""
from pathlib import Path, PurePosixPath
import stat


def checked_path(path: str | Path) -> Path:
    path = Path(path).absolute()
    for segment in (*reversed(path.parents), path):
        if segment.exists() or segment.is_symlink():
            info = segment.lstat()
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                raise ValueError('symlink or reparse point is not allowed in an exported path')
    return path


def relative_reference(value: str) -> PurePosixPath:
    if (not isinstance(value, str) or not value or value.startswith('/') or '\\' in value or ':' in value
            or any(p in {'', '.', '..'} for p in value.split('/'))):
        raise ValueError('paths must be relative POSIX paths without traversal or empty components')
    return PurePosixPath(value)


def ordinary_file(path: Path) -> Path:
    path = checked_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('export source must be an ordinary file with one link')
    return path
