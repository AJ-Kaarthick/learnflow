from app.utils.filenames import get_extension, strip_extension


def test_get_extension_returns_dot_prefixed_suffix():
    assert get_extension("Workout.pdf") == ".pdf"
    assert get_extension("Slides.pptx") == ".pptx"
    assert get_extension("Notes.docx") == ".docx"
    assert get_extension("chart.PNG") == ".PNG"


def test_get_extension_handles_multiple_dots():
    assert get_extension("Chapter 1.2 Notes.pdf") == ".pdf"


def test_get_extension_returns_empty_string_when_absent():
    assert get_extension("README") == ""


def test_strip_extension_removes_matching_suffix():
    assert strip_extension("Workout.pdf", ".pdf") == "Workout"


def test_strip_extension_is_case_insensitive():
    assert strip_extension("Workout.PDF", ".pdf") == "Workout"
    assert strip_extension("Workout.pdf", ".PDF") == "Workout"


def test_strip_extension_leaves_non_matching_suffix_untouched():
    # A caller trying to sneak in a different extension shouldn't have
    # it silently stripped -- it stays as literal text in the name.
    assert strip_extension("Workout.jpg", ".pdf") == "Workout.jpg"


def test_strip_extension_preserves_internal_dots():
    assert strip_extension("Chapter 1.2 Notes.pdf", ".pdf") == "Chapter 1.2 Notes"


def test_strip_extension_noop_when_extension_is_empty():
    assert strip_extension("README", "") == "README"


def test_strip_extension_can_remove_entire_value():
    assert strip_extension(".pdf", ".pdf") == ""
