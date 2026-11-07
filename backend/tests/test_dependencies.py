from app.services.dependencies import (
    build_import_graph,
    extract_imports,
    find_reverse_dependencies,
    module_name_for_path,
)


def test_src_layout_maps_to_importable_package_name():
    assert module_name_for_path("src/cattrs/disambiguators.py") == "cattrs.disambiguators"
    assert module_name_for_path("src/cattrs/__init__.py") == "cattrs"


def test_extracts_absolute_and_relative_imports():
    source = "import json\nfrom .services.tasks import TaskService\n"
    imports = extract_imports(source, "app.api")
    assert "json" in imports
    assert "app.services.tasks" in imports
    assert "app.services.tasks.TaskService" in imports


def test_finds_transitive_reverse_dependencies():
    graph = {
        "app.services.tasks": set(),
        "app.api": {"app.services.tasks"},
        "tests.test_api": {"app.api"},
        "app.unrelated": {"json"},
    }
    affected = find_reverse_dependencies(graph, {"app.services.tasks"})
    assert affected == {"app.services.tasks", "app.api", "tests.test_api"}


def test_builds_graph_from_project(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "app" / "api.py").write_text(
        "from app.service import VALUE\n", encoding="utf-8"
    )
    graph = build_import_graph(tmp_path)
    assert "app.service" in graph
    assert "app.service" in graph["app.api"]
