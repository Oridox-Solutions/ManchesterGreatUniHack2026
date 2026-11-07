from app.services.diff_parser import parse_changed_lines


def test_parses_added_and_removed_lines():
    patch = """@@ -2,4 +2,5 @@
 context
-old value
+new value
+another value
 context
"""
    result = parse_changed_lines(patch)
    assert result.old == [3]
    assert result.new == [3, 4]


def test_handles_multiple_hunks():
    patch = """@@ -1 +1 @@
-old
+new
@@ -10,2 +10,2 @@
 same
-added
+changed
"""
    result = parse_changed_lines(patch)
    assert result.old == [1, 11]
    assert result.new == [1, 11]


def test_missing_patch_is_empty():
    assert parse_changed_lines(None).new == []
    assert parse_changed_lines("").old == []
