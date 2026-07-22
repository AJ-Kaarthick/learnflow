from pathlib import Path


def get_extension(filename: str) -> str:
    """
    Returns a filename's extension including the leading dot (e.g.
    ".pdf", ".docx", ".png"), or "" if it doesn't have one.

    Deliberately derived from the filename itself rather than a
    hardcoded constant or allow-list, so this works for whatever file
    type a document actually is -- PDF today, and PPTX/DOCX/XLSX/images/
    etc. whenever LearnFlow adds support for them -- without this
    helper (or its callers) needing to change.
    """
    return Path(filename).suffix


def strip_extension(value: str, extension: str) -> str:
    """
    Removes `extension` from the end of `value` if it's there
    (case-insensitive), otherwise returns `value` unchanged.

    Used so a caller can send either just a base name ("Notes") or a
    full name that happens to already end in the correct extension
    ("Notes.pdf") and get the same result, without misinterpreting an
    unrelated trailing dot-suffix (e.g. a base name that legitimately
    ends in ".2" or someone trying to sneak in ".jpg") as the real
    extension.
    """
    if extension and value.lower().endswith(extension.lower()):
        return value[: -len(extension)]
    return value
