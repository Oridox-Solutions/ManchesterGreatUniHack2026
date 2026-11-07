import json
import posixpath
import re
from pathlib import Path
from typing import Literal, TypedDict

from app.services.code_analysis import analyse_python_impact
from app.services.dependencies import (
    IGNORED_PARTS,
    extract_imports,
    module_name_for_path,
)
from app.services.test_discovery import discover_project_tests


Language = Literal[
    "python", "javascript", "java", "kotlin", "csharp", "ruby", "php", "dart",
    "go", "elixir", "clojure", "powershell",
]
Impact = TypedDict(
    "Impact",
    {
        "changed_functions": list[str],
        "changed_classes": list[str],
        "module_level_change": bool,
        "analysis_status": str,
    },
)

JAVASCRIPT_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
SUPPORTED_CODE_EXTENSIONS = {
    ".py", ".java", ".kt", ".kts", ".cs", ".rb", ".php", ".dart", ".go",
    ".ex", ".exs", ".clj", ".cljs", ".cljc", ".ps1", ".psm1",
    *JAVASCRIPT_EXTENSIONS,
}

_JS_TEST = re.compile(
    r"\b(?P<kind>test|it)\s*\(\s*(?P<quote>['\"])(?P<name>.*?)(?P=quote)\s*,",
    re.DOTALL,
)
_JS_IMPORT = re.compile(
    r"(?:import\s+(?:[\s\S]*?\s+from\s+)?|export\s+[\s\S]*?\s+from\s+|"
    r"require\s*\()\s*['\"](?P<module>[^'\"]+)['\"]"
)
_JS_FUNCTION = re.compile(
    r"(?:\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+"
    r"|(?:^|[;{}\n])\s*(?:export\s+)?(?:const|let|var)\s+)"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"(?:\([^;{}]*\)(?:\s*:\s*[^={]+)?"
    r"|=\s*(?:async\s*)?\([^;{}]*\)(?:\s*:\s*[^={]+)?\s*=>)"
    r"\s*\{",
    re.MULTILINE,
)
_JS_METHOD = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|static|async|get|set|readonly|"
    r"abstract|override)\s+)*(?P<name>(?!(?:if|for|while|switch|catch)\b)"
    r"[A-Za-z_$][\w$]*)\s*\([^;{}]*\)(?:\s*:\s*[^={]+)?\s*\{"
)
_JS_CLASS = re.compile(
    r"\b(?:export\s+)?(?:default\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{"
)
_JAVA_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;?", re.MULTILINE)
_JAVA_IMPORT = re.compile(
    r"^\s*import\s+(?:static\s+)?([\w.]+)(?:\.\*)?\s*;?",
    re.MULTILINE,
)
_JAVA_CLASS = re.compile(
    r"\b(?:class|interface|enum|record)\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{"
)
_JAVA_METHOD = re.compile(
    r"(?m)^[ \t]*(?:@\w+(?:\([^)]*\))?[ \t]*\n[ \t]*)*"
    r"(?:(?:public|protected|private|static|final|synchronized|abstract|native|default)\s+)*"
    r"(?:<[^>{}]+>\s+)?[\w$<>\[\],.?]+\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{}]*\)"
    r"(?:\s+throws\s+[\w$.,\s]+)?\s*\{"
)
_KOTLIN_CLASS = re.compile(
    r"\b(?:(?:data|sealed|abstract|open|enum|annotation)\s+)?"
    r"(?:class|interface|object)\s+(?P<name>[A-Za-z_$][\w$]*)[^\{]*\{"
)
_KOTLIN_FUNCTION = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|internal|open|final|abstract|"
    r"override|inline|tailrec|operator|infix|external|suspend)\s+)*"
    r"fun\s+(?:<[^>{}]+>\s*)?(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"\([^{}]*\)(?:\s*:\s*[^={]+)?\s*\{"
)
_CSHARP_NAMESPACE = re.compile(
    r"^\s*namespace\s+([A-Za-z_][\w.]*)\s*[;{]",
    re.MULTILINE,
)
_CSHARP_IMPORT = re.compile(
    r"^\s*using\s+(?:static\s+)?(?:[A-Za-z_]\w*\s*=\s*)?"
    r"([A-Za-z_][\w.]*)\s*;",
    re.MULTILINE,
)
_CSHARP_CLASS = re.compile(
    r"\b(?:class|interface|record|struct)\s+"
    r"(?P<name>[A-Za-z_][\w]*)[^\{]*\{"
)
_CSHARP_METHOD = re.compile(
    r"(?m)^[ \t]*(?:\[[^\]\n]+\][ \t]*\n[ \t]*)*"
    r"(?:(?:public|private|protected|internal|static|virtual|abstract|override|"
    r"sealed|async|new|extern|partial)\s+)*"
    r"[A-Za-z_][\w.<>,?\[\] ]*\s+"
    r"(?P<name>[A-Za-z_][\w]*)\s*\([^;{}]*\)"
    r"(?:\s+where\s+[^\{]+)?\s*\{"
)
_RUBY_REQUIRE = re.compile(
    r"^\s*require(?P<relative>_relative)?\s*\(?\s*['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
_RUBY_CLASS = re.compile(
    r"(?m)^[ \t]*class\s+(?P<name>[A-Z][\w:]*)"
)
_RUBY_DEF = re.compile(
    r"(?m)^[ \t]*def\s+(?:(?:self\.)?)(?P<name>[A-Za-z_]\w*[!?=]?)"
)
_PHP_NAMESPACE = re.compile(
    r"^\s*namespace\s+([A-Za-z_\\][\w\\]*)\s*;",
    re.MULTILINE,
)
_PHP_IMPORT = re.compile(
    r"^\s*use\s+(?:function\s+|const\s+)?"
    r"([A-Za-z_\\][\w\\]*)(?:\s+as\s+\w+)?\s*;",
    re.MULTILINE,
)
_PHP_CLASS = re.compile(
    r"\b(?:class|interface|trait|enum)\s+"
    r"(?P<name>[A-Za-z_][\w]*)[^\{]*\{"
)
_PHP_METHOD = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|static|final|abstract|readonly)\s+)*"
    r"function\s+&?\s*(?P<name>[A-Za-z_][\w]*)\s*\([^;{}]*\)"
    r"(?:\s*:\s*[^\{=]+)?\s*\{"
)
_DART_IMPORT = re.compile(
    r"^\s*import\s+['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
_DART_EXPORT = re.compile(
    r"^\s*export\s+['\"](?P<module>[^'\"]+)['\"]",
    re.MULTILINE,
)
_DART_CLASS = re.compile(
    r"\b(?:class|mixin|enum|extension)\s+"
    r"(?P<name>[A-Za-z_][\w]*)[^\{]*\{"
)
_DART_FUNCTION = re.compile(
    r"(?m)^[ \t]*(?:(?:static|external|abstract|covariant)\s+)*"
    r"(?:[A-Za-z_][\w<>,?. ]*\s+)?"
    r"(?P<name>(?!(?:if|for|while|switch|catch)\b)[A-Za-z_][\w]*)"
    r"\s*\([^;{}]*\)(?:\s+async)?\s*\{"
)
_GO_PACKAGE = re.compile(r"^\s*package\s+([A-Za-z_]\w*)", re.MULTILINE)
_GO_FUNCTION = re.compile(
    r"(?m)^\s*func\s+(?:\([^)]*\)\s*)?"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^{}]*\)"
    r"(?:\s*\([^{}]*\)|\s+[A-Za-z_*\[\].][^{}]*)?\s*\{"
)
_GO_TYPE = re.compile(
    r"(?m)^\s*type\s+(?P<name>[A-Za-z_]\w*)\s+"
    r"(?:struct|interface)\s*\{"
)
_ELIXIR_MODULE = re.compile(
    r"(?m)^\s*defmodule\s+(?P<name>[A-Z][\w.]*)\s+do\b"
)
_ELIXIR_FUNCTION = re.compile(
    r"(?m)^\s*defp?\s+(?P<name>[a-z_][\w!?]*)\b"
)
_ELIXIR_IMPORT = re.compile(
    r"(?m)^\s*(?:alias|import|use)\s+([A-Z][\w.]*)"
)
_CLOJURE_NAMESPACE = re.compile(
    r"\(\s*ns\s+(?P<name>[A-Za-z_][\w.\-]*)"
)
_CLOJURE_FUNCTION = re.compile(
    r"\(\s*defn-?\s+(?P<name>[A-Za-z_][\w!?*+./<>\-]*)"
)
_CLOJURE_TYPE = re.compile(
    r"\(\s*(?:defrecord|deftype)\s+(?P<name>[A-Za-z_][\w\-]*)"
)
_CLOJURE_TEST = re.compile(
    r"\(\s*deftest\s+(?P<name>[A-Za-z_][\w!?*+./<>\-]*)"
)
_POWERSHELL_FUNCTION = re.compile(
    r"(?im)^\s*function\s+(?P<name>[A-Za-z_][\w-]*)\s*\{"
)
_POWERSHELL_IMPORT = re.compile(
    r"(?im)^\s*(?:Import-Module|\.|&)\s+"
    r"(?P<quote>['\"])(?P<module>.*?)(?P=quote)"
)
_PESTER_TEST = re.compile(
    r"(?im)^\s*It\s+(?P<quote>['\"])(?P<name>.*?)(?P=quote)"
    r"(?:\s+-[^\{]+)?\s*\{"
)
_CALL = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
_IGNORED_CALLS = {
    "describe", "test", "it", "expect", "beforeEach", "afterEach", "beforeAll",
    "afterAll", "function", "if", "for", "while", "switch", "catch", "return",
    "new", "super", "this", "assert", "assertEquals", "assertTrue", "assertFalse",
}


def language_for_path(path: str | Path) -> Language | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in JAVASCRIPT_EXTENSIONS:
        return "javascript"
    if suffix == ".java":
        return "java"
    if suffix in {".kt", ".kts"}:
        return "kotlin"
    if suffix == ".cs":
        return "csharp"
    if suffix == ".rb":
        return "ruby"
    if suffix == ".php":
        return "php"
    if suffix == ".dart":
        return "dart"
    if suffix == ".go":
        return "go"
    if suffix in {".ex", ".exs"}:
        return "elixir"
    if suffix in {".clj", ".cljs", ".cljc"}:
        return "clojure"
    if suffix in {".ps1", ".psm1"}:
        return "powershell"
    return None


def is_supported_code_path(path: str | Path) -> bool:
    return language_for_path(path) is not None


def is_test_path(path: str | Path) -> bool:
    value = Path(path).as_posix()
    file = Path(value)
    lower = value.lower()
    name = file.name.lower()
    suffix = file.suffix.lower()

    if suffix == ".py":
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix in JAVASCRIPT_EXTENSIONS:
        stem = name[: -len(suffix)]
        return (
            stem.endswith((".test", ".spec"))
            or any(part.lower() in {"test", "tests", "__tests__"} for part in file.parts)
        )
    if suffix in {".java", ".kt", ".kts"}:
        return (
            name.endswith(
                (
                    "test.java", "tests.java", "it.java",
                    "test.kt", "tests.kt", "it.kt",
                    "test.kts", "tests.kts",
                )
            )
            or "/src/test/" in f"/{lower}"
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix == ".cs":
        return (
            name.endswith(("test.cs", "tests.cs", "spec.cs"))
            or any(
                part.lower() in {"test", "tests"}
                or part.lower().endswith((".test", ".tests"))
                for part in file.parts
            )
        )
    if suffix == ".rb":
        return (
            name.endswith(("_test.rb", "_spec.rb"))
            or any(part.lower() in {"test", "tests", "spec"} for part in file.parts)
        )
    if suffix == ".php":
        return (
            name.endswith(("test.php", "tests.php"))
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix == ".dart":
        return (
            name.endswith("_test.dart")
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix == ".go":
        return name.endswith("_test.go")
    if suffix in {".ex", ".exs"}:
        return (
            name.endswith("_test.exs")
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix in {".clj", ".cljs", ".cljc"}:
        return (
            "_test." in name
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    if suffix in {".ps1", ".psm1"}:
        return (
            name.endswith(".tests.ps1")
            or any(part.lower() in {"test", "tests"} for part in file.parts)
        )
    return False


def discover_repository_tests(project_root: str | Path) -> list[dict]:
    root = Path(project_root)
    tests = discover_project_tests(root)
    tests.extend(_discover_javascript_tests(root))
    tests.extend(_discover_java_tests(root))
    tests.extend(_discover_kotlin_tests(root))
    tests.extend(_discover_csharp_tests(root))
    tests.extend(_discover_ruby_tests(root))
    tests.extend(_discover_php_tests(root))
    tests.extend(_discover_dart_tests(root))
    tests.extend(_discover_go_tests(root))
    tests.extend(_discover_elixir_tests(root))
    tests.extend(_discover_clojure_tests(root))
    tests.extend(_discover_pester_tests(root))
    return sorted(tests, key=lambda item: item["node_id"])


def build_repository_import_graph(
    project_root: str | Path,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    root = Path(project_root)
    graph: dict[str, set[str]] = {}
    modules_by_path: dict[str, str] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        language = language_for_path(path)
        if language is None:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        module = module_identifier(relative, language, source)
        modules_by_path[relative] = module
        graph.setdefault(module, set()).update(
            extract_language_imports(source, module, language)
        )

    return graph, modules_by_path


def module_identifier(
    path: str | Path,
    language: Language | None = None,
    source: str = "",
) -> str:
    value = Path(path).as_posix()
    language = language or language_for_path(value)
    if language == "python":
        return module_name_for_path(value)
    if language == "javascript":
        for extension in sorted(JAVASCRIPT_EXTENSIONS, key=len, reverse=True):
            if value.lower().endswith(extension):
                value = value[: -len(extension)]
                break
        if value.endswith("/index"):
            value = value[:-6]
        return value.strip("/")
    if language in {"java", "kotlin"}:
        package = _JAVA_PACKAGE.search(source)
        stem = Path(value).stem
        return f"{package.group(1)}.{stem}" if package else stem
    if language == "csharp":
        namespace = _CSHARP_NAMESPACE.search(source)
        stem = Path(value).stem
        return f"{namespace.group(1)}.{stem}" if namespace else stem
    if language == "ruby":
        return _normalise_ruby_module(value)
    if language == "php":
        namespace = _PHP_NAMESPACE.search(source)
        stem = Path(value).stem
        if namespace:
            prefix = namespace.group(1).replace("\\", ".")
            return f"{prefix}.{stem}"
        return stem
    if language == "dart":
        return _normalise_dart_module(value)
    if language == "go":
        parent = posixpath.dirname(value)
        if parent and parent != ".":
            return parent.strip("/")
        package = _GO_PACKAGE.search(source)
        return package.group(1) if package else Path(value).stem
    if language == "elixir":
        module = _ELIXIR_MODULE.search(source)
        return module.group("name") if module else Path(value).stem
    if language == "clojure":
        namespace = _CLOJURE_NAMESPACE.search(source)
        return namespace.group("name") if namespace else Path(value).stem
    if language == "powershell":
        return _normalise_powershell_module(value)
    return value


def extract_language_imports(
    source: str,
    current_module: str,
    language: Language,
) -> set[str]:
    if language == "python":
        return extract_imports(source, current_module)
    if language == "javascript":
        imports: set[str] = set()
        for match in _JS_IMPORT.finditer(source):
            specifier = match.group("module")
            if specifier.startswith("."):
                imports.add(_resolve_js_import(current_module, specifier))
            else:
                imports.add(specifier)
        return imports
    if language in {"java", "kotlin"}:
        return set(_JAVA_IMPORT.findall(source))
    if language == "csharp":
        return set(_CSHARP_IMPORT.findall(source))
    if language == "ruby":
        imports: set[str] = set()
        for match in _RUBY_REQUIRE.finditer(source):
            requested = match.group("module")
            if match.group("relative"):
                imports.add(_resolve_ruby_import(current_module, requested))
            else:
                imports.add(_normalise_ruby_module(requested))
        return imports
    if language == "php":
        return {
            imported.replace("\\", ".")
            for imported in _PHP_IMPORT.findall(source)
        }
    if language == "dart":
        return {
            _resolve_dart_import(current_module, match.group("module"))
            for pattern in (_DART_IMPORT, _DART_EXPORT)
            for match in pattern.finditer(source)
        }
    if language == "go":
        return _extract_go_imports(source) | {current_module}
    if language == "elixir":
        return set(_ELIXIR_IMPORT.findall(source))
    if language == "clojure":
        return _extract_clojure_imports(source)
    if language == "powershell":
        return {
            _resolve_powershell_import(current_module, match.group("module"))
            for match in _POWERSHELL_IMPORT.finditer(source)
        }
    return set()


def analyse_source_impact(
    language: Language,
    source: str,
    changed_lines: list[int],
) -> Impact:
    if language == "python":
        return analyse_python_impact(source, changed_lines)
    if language == "javascript":
        symbols = _symbol_ranges(source, _JS_FUNCTION, _JS_CLASS)
        symbols.extend(_ranges_for_pattern(source, _JS_METHOD, "function"))
    elif language == "java":
        symbols = _symbol_ranges(source, _JAVA_METHOD, _JAVA_CLASS)
    elif language == "kotlin":
        symbols = _symbol_ranges(source, _KOTLIN_FUNCTION, _KOTLIN_CLASS)
    elif language == "csharp":
        symbols = _symbol_ranges(source, _CSHARP_METHOD, _CSHARP_CLASS)
    elif language == "ruby":
        symbols = _ruby_symbol_ranges(source)
    elif language == "php":
        symbols = _symbol_ranges(source, _PHP_METHOD, _PHP_CLASS)
    elif language == "dart":
        symbols = _symbol_ranges(source, _DART_FUNCTION, _DART_CLASS)
    elif language == "go":
        symbols = _symbol_ranges(source, _GO_FUNCTION, _GO_TYPE)
    elif language == "elixir":
        symbols = _elixir_symbol_ranges(source)
    elif language == "clojure":
        symbols = _clojure_symbol_ranges(source)
    else:
        symbols = _ranges_for_pattern(
            source, _POWERSHELL_FUNCTION, "function"
        )
    return _analyse_ranges(source, changed_lines, symbols)


def _discover_javascript_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix.lower() not in JAVASCRIPT_EXTENSIONS
            or any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        framework = _javascript_framework(path.parent, root)
        module = module_identifier(relative, "javascript", source)
        imports = sorted(extract_language_imports(source, module, "javascript"))
        for match in _JS_TEST.finditer(source):
            open_paren = source.find("(", match.start())
            end_offset = _balanced_end(source, open_paren, "(", ")")
            if end_offset is None:
                end_offset = len(source) - 1
            body = source[match.end(): end_offset + 1]
            called = _called_names(body)
            start_line = _line_number(source, match.start())
            records.append(
                {
                    "test_file": relative,
                    "test_name": match.group("name"),
                    "test_class": None,
                    "node_id": f"{relative}::{match.group('name')}",
                    "framework": framework,
                    "imports": imports,
                    "referenced_names": called,
                    "called_names": called,
                    "start_line": start_line,
                    "end_line": _line_number(source, end_offset),
                }
            )
    return records


def _discover_java_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    annotation = re.compile(
        r"(?m)^[ \t]*@(?P<annotation>Test|ParameterizedTest|RepeatedTest)"
        r"(?:\([^)]*\))?[ \t]*\n"
        r"(?:[ \t]*@\w+(?:\([^)]*\))?[ \t]*\n)*"
        r"[ \t]*(?:(?:public|protected|private|static|final|synchronized)\s+)*"
        r"(?:<[^>{}]+>\s+)?[\w$<>\[\],.?]+\s+"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{}]*\)[^{;]*\{"
    )
    for path in sorted(root.rglob("*.java")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "java", source)
        imports = sorted(extract_language_imports(source, module, "java"))
        framework = "testng" if "org.testng" in source else "junit"
        class_match = _JAVA_CLASS.search(source)
        class_name = class_match.group("name") if class_match else Path(relative).stem
        for match in annotation.finditer(source):
            open_brace = source.find("{", match.start(), match.end())
            end_offset = _balanced_end(source, open_brace, "{", "}")
            if end_offset is None:
                end_offset = len(source) - 1
            body = source[open_brace + 1: end_offset]
            called = _called_names(body)
            start_line = _line_number(source, match.start())
            records.append(
                {
                    "test_file": relative,
                    "test_name": match.group("name"),
                    "test_class": class_name,
                    "node_id": f"{relative}::{class_name}::{match.group('name')}",
                    "framework": framework,
                    "imports": imports,
                    "referenced_names": called,
                    "called_names": called,
                    "start_line": start_line,
                    "end_line": _line_number(source, end_offset),
                }
            )
    return records



def _discover_kotlin_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    pattern = re.compile(
        r"(?m)^[ \t]*@(?:[\w.]*)(?:Test|ParameterizedTest|RepeatedTest)"
        r"(?:\([^)]*\))?[ \t]*\n"
        r"(?:[ \t]*@\w+(?:\([^)]*\))?[ \t]*\n)*"
        r"[ \t]*(?:(?:public|private|protected|internal|suspend)\s+)*"
        r"fun\s+(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{}]*\)"
        r"(?:\s*:\s*[^={]+)?\s*\{"
    )
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix.lower() not in {".kt", ".kts"}
            or any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "kotlin", source)
        imports = sorted(extract_language_imports(source, module, "kotlin"))
        framework = "testng" if "org.testng" in source else "junit"
        class_match = _KOTLIN_CLASS.search(source)
        class_name = class_match.group("name") if class_match else None
        for match in pattern.finditer(source):
            record = _brace_test_record(
                source, relative, match, class_name, framework, imports
            )
            if record:
                records.append(record)
    return records


def _discover_csharp_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    pattern = re.compile(
        r"(?m)^(?P<attributes>(?:[ \t]*\[[^\]\n]+\][ \t]*\n)+)"
        r"[ \t]*(?:(?:public|private|protected|internal|static|virtual|override|"
        r"sealed|async|new|partial)\s+)*"
        r"[A-Za-z_][\w.<>,?\[\] ]*\s+"
        r"(?P<name>[A-Za-z_][\w]*)\s*\([^;{}]*\)"
        r"(?:\s+where\s+[^\{]+)?\s*\{"
    )
    test_marker = re.compile(
        r"\b(?:Fact|Theory|Test|TestCase|TestMethod|DataTestMethod)\b"
    )
    for path in sorted(root.rglob("*.cs")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "csharp", source)
        imports = sorted(extract_language_imports(source, module, "csharp"))
        framework = _csharp_framework(source)
        class_match = _CSHARP_CLASS.search(source)
        class_name = class_match.group("name") if class_match else Path(relative).stem
        for match in pattern.finditer(source):
            if not test_marker.search(match.group("attributes")):
                continue
            record = _brace_test_record(
                source, relative, match, class_name, framework, imports
            )
            if record:
                records.append(record)
    return records


def _discover_ruby_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    example_pattern = re.compile(
        r"(?m)^[ \t]*(?:it|specify)\s*(?:\(\s*)?"
        r"(?P<quote>['\"])(?P<name>.*?)(?P=quote)[^\n]*\bdo\b"
    )
    for path in sorted(root.rglob("*.rb")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "ruby", source)
        imports = sorted(extract_language_imports(source, module, "ruby"))
        class_match = _RUBY_CLASS.search(source)
        class_name = (
            class_match.group("name").split("::")[-1]
            if class_match else None
        )

        for match in example_pattern.finditer(source):
            start_line = _line_number(source, match.start())
            end_line = _ruby_end_line(source, start_line)
            body = "\n".join(source.splitlines()[start_line:end_line])
            called = _ruby_called_names(body)
            records.append(
                _test_record(
                    relative,
                    match.group("name"),
                    None,
                    "rspec",
                    imports,
                    called,
                    start_line,
                    end_line,
                )
            )

        for kind, name, start_line, end_line in _ruby_symbol_ranges(source):
            if kind != "function" or not name.startswith("test_"):
                continue
            body = "\n".join(source.splitlines()[start_line:end_line])
            called = _ruby_called_names(body)
            records.append(
                _test_record(
                    relative,
                    name,
                    class_name,
                    "minitest",
                    imports,
                    called,
                    start_line,
                    end_line,
                )
            )
    return records


def _discover_php_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*.php")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "php", source)
        imports = sorted(extract_language_imports(source, module, "php"))
        class_match = _PHP_CLASS.search(source)
        class_name = class_match.group("name") if class_match else Path(relative).stem

        for match in _PHP_METHOD.finditer(source):
            name = match.group("name")
            prefix = source[max(0, match.start() - 400):match.start()]
            annotated = bool(
                re.search(r"(?:#\[\s*(?:\\?PHPUnit\\Framework\\Attributes\\)?Test\b|@test\b)\s*$", prefix)
            )
            if not name.lower().startswith("test") and not annotated:
                continue
            record = _brace_test_record(
                source, relative, match, class_name, "phpunit", imports
            )
            if record:
                records.append(record)
    return records



def _discover_dart_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*.dart")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "dart", source)
        imports = sorted(extract_language_imports(source, module, "dart"))
        for match in _JS_TEST.finditer(source):
            if match.group("kind") != "test":
                continue
            open_paren = source.find("(", match.start())
            end_offset = _balanced_end(source, open_paren, "(", ")")
            if end_offset is None:
                continue
            body = source[match.end():end_offset + 1]
            called = _called_names(body)
            records.append(
                _test_record(
                    relative,
                    match.group("name"),
                    None,
                    "dart_test",
                    imports,
                    called,
                    _line_number(source, match.start()),
                    _line_number(source, end_offset),
                )
            )
    return records



def _discover_go_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    pattern = re.compile(
        r"(?m)^\s*func\s+(?P<name>(?:Test[A-Z0-9_]\w*|Example\w*))"
        r"\s*\([^{}]*\)\s*\{"
    )
    for path in sorted(root.rglob("*_test.go")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "go", source)
        imports = sorted(extract_language_imports(source, module, "go"))
        for match in pattern.finditer(source):
            record = _brace_test_record(
                source, relative, match, None, "go_test", imports
            )
            if record:
                records.append(record)
    return records


def _discover_elixir_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    pattern = re.compile(
        r"(?m)^\s*test\s+(?P<quote>['\"])(?P<name>.*?)(?P=quote)"
        r"(?:\s*,\s*[^\\n]+)?\s+do\b"
    )
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix.lower() not in {".ex", ".exs"}
            or any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "elixir", source)
        imports = sorted(extract_language_imports(source, module, "elixir"))
        module_match = _ELIXIR_MODULE.search(source)
        class_name = module_match.group("name") if module_match else None
        lines = source.splitlines()
        for match in pattern.finditer(source):
            start_line = _line_number(source, match.start())
            end_line = _elixir_end_line(source, start_line)
            body = "\n".join(lines[start_line:end_line])
            called = _called_names(body)
            records.append(
                _test_record(
                    relative,
                    match.group("name"),
                    class_name,
                    "exunit",
                    imports,
                    called,
                    start_line,
                    end_line,
                )
            )
    return records


def _discover_clojure_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix.lower() not in {".clj", ".cljs", ".cljc"}
            or any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "clojure", source)
        imports = sorted(extract_language_imports(source, module, "clojure"))
        for match in _CLOJURE_TEST.finditer(source):
            end_offset = _clojure_balanced_end(source, match.start())
            if end_offset is None:
                continue
            body = source[match.end():end_offset]
            called = _clojure_called_names(body)
            records.append(
                _test_record(
                    relative,
                    match.group("name"),
                    None,
                    "clojure_test",
                    imports,
                    called,
                    _line_number(source, match.start()),
                    _line_number(source, end_offset),
                )
            )
    return records


def _discover_pester_tests(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*.ps1")):
        if (
            any(part in IGNORED_PARTS for part in path.parts)
            or not is_test_path(path.relative_to(root))
        ):
            continue
        source = _read_source(path)
        if source is None:
            continue
        relative = path.relative_to(root).as_posix()
        module = module_identifier(relative, "powershell", source)
        imports = sorted(
            extract_language_imports(source, module, "powershell")
        )
        for match in _PESTER_TEST.finditer(source):
            open_brace = source.find("{", match.start(), match.end())
            end_offset = _balanced_end(source, open_brace, "{", "}")
            if end_offset is None:
                continue
            body = source[open_brace + 1:end_offset]
            called = _powershell_called_names(body)
            records.append(
                _test_record(
                    relative,
                    match.group("name"),
                    None,
                    "pester",
                    imports,
                    called,
                    _line_number(source, match.start()),
                    _line_number(source, end_offset),
                )
            )
    return records


def _brace_test_record(
    source: str,
    relative: str,
    match: re.Match[str],
    class_name: str | None,
    framework: str,
    imports: list[str],
) -> dict | None:
    open_brace = source.find("{", match.start(), match.end())
    end_offset = _balanced_end(source, open_brace, "{", "}")
    if open_brace < 0 or end_offset is None:
        return None
    body = source[open_brace + 1:end_offset]
    return _test_record(
        relative,
        match.group("name"),
        class_name,
        framework,
        imports,
        _called_names(body),
        _line_number(source, match.start()),
        _line_number(source, end_offset),
    )


def _test_record(
    relative: str,
    name: str,
    class_name: str | None,
    framework: str,
    imports: list[str],
    called: list[str],
    start_line: int,
    end_line: int,
) -> dict:
    parts = [relative]
    if class_name:
        parts.append(class_name)
    parts.append(name)
    return {
        "test_file": relative,
        "test_name": name,
        "test_class": class_name,
        "node_id": "::".join(parts),
        "framework": framework,
        "imports": imports,
        "referenced_names": called,
        "called_names": called,
        "start_line": start_line,
        "end_line": end_line,
    }


def _csharp_framework(source: str) -> str:
    if "Xunit" in source or re.search(r"\[(?:Fact|Theory)\b", source):
        return "xunit"
    if "Microsoft.VisualStudio.TestTools" in source or re.search(
        r"\[(?:TestMethod|DataTestMethod)\b", source
    ):
        return "mstest"
    return "nunit"


def _ruby_symbol_ranges(source: str) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    for kind, pattern in (("function", _RUBY_DEF), ("class", _RUBY_CLASS)):
        for match in pattern.finditer(source):
            start_line = _line_number(source, match.start())
            symbols.append(
                (
                    kind,
                    match.group("name").split("::")[-1],
                    start_line,
                    _ruby_end_line(source, start_line),
                )
            )
    return symbols


def _ruby_end_line(source: str, start_line: int) -> int:
    lines = source.splitlines()
    depth = 0
    opened = False
    opener = re.compile(
        r"^(?:class|module|def|if|unless|case|begin|while|until|for)\b|\bdo\b"
    )
    for index in range(start_line - 1, len(lines)):
        line = re.sub(r"#.*$", "", lines[index]).strip()
        if not line:
            continue
        additions = len(opener.findall(line))
        if additions:
            depth += additions
            opened = True
        endings = len(re.findall(r"(?:^|;)\s*end\b", line))
        if endings:
            depth -= endings
        if opened and depth <= 0:
            return index + 1
    return len(lines)


def _ruby_called_names(source: str) -> list[str]:
    names = set(_called_names(source))
    names.update(re.findall(r"\.\s*([A-Za-z_]\w*[!?=]?)", source))
    return sorted(name for name in names if name not in _IGNORED_CALLS)


def _normalise_ruby_module(value: str) -> str:
    normalised = Path(value).as_posix()
    if normalised.endswith(".rb"):
        normalised = normalised[:-3]
    normalised = normalised.strip("/")
    if normalised.startswith("lib/"):
        normalised = normalised[4:]
    return normalised


def _resolve_ruby_import(current_module: str, requested: str) -> str:
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(current_module), requested)
    )
    return _normalise_ruby_module(resolved)



def _normalise_dart_module(value: str) -> str:
    normalised = Path(value).as_posix()
    if normalised.endswith(".dart"):
        normalised = normalised[:-5]
    normalised = normalised.strip("/")
    if normalised.startswith("lib/"):
        normalised = normalised[4:]
    return normalised


def _resolve_dart_import(current_module: str, requested: str) -> str:
    if requested.startswith("dart:"):
        return requested
    if requested.startswith("package:"):
        package_path = requested.split(":", 1)[1]
        _, _, module_path = package_path.partition("/")
        return _normalise_dart_module(module_path)
    resolved = posixpath.normpath(
        posixpath.join(posixpath.dirname(current_module), requested)
    )
    return _normalise_dart_module(resolved)



def _extract_go_imports(source: str) -> set[str]:
    imports = set(
        re.findall(
            r'(?m)^\s*import\s+(?:[A-Za-z_]\w*\s+)?"([^"]+)"',
            source,
        )
    )
    for block in re.findall(r"(?s)\bimport\s*\((.*?)\)", source):
        imports.update(re.findall(r'"([^"]+)"', block))
    return imports


def _elixir_symbol_ranges(source: str) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    for kind, pattern in (
        ("function", _ELIXIR_FUNCTION),
        ("class", _ELIXIR_MODULE),
    ):
        for match in pattern.finditer(source):
            start_line = _line_number(source, match.start())
            symbols.append(
                (
                    kind,
                    match.group("name"),
                    start_line,
                    _elixir_end_line(source, start_line),
                )
            )
    return symbols


def _elixir_end_line(source: str, start_line: int) -> int:
    lines = source.splitlines()
    depth = 0
    opened = False
    for index in range(start_line - 1, len(lines)):
        line = re.sub(r"#.*$", "", lines[index])
        if not opened and re.search(r"\bdo\s*:", line):
            return index + 1
        additions = len(re.findall(r"\bdo\b(?!\s*:)", line))
        additions += len(re.findall(r"\bfn\b", line))
        if additions:
            depth += additions
            opened = True
        depth -= len(re.findall(r"\bend\b", line))
        if opened and depth <= 0:
            return index + 1
    return len(lines)


def _extract_clojure_imports(source: str) -> set[str]:
    namespace = _CLOJURE_NAMESPACE.search(source)
    if not namespace:
        return set()
    end = _clojure_balanced_end(source, namespace.start())
    if end is None:
        return set()
    namespace_form = source[namespace.start():end + 1]
    return set(
        re.findall(r"\[\s*([A-Za-z_][\w.\-]*)", namespace_form)
    )


def _clojure_symbol_ranges(
    source: str,
) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    for kind, pattern in (
        ("function", _CLOJURE_FUNCTION),
        ("class", _CLOJURE_TYPE),
    ):
        for match in pattern.finditer(source):
            end = _clojure_balanced_end(source, match.start())
            if end is None:
                continue
            symbols.append(
                (
                    kind,
                    match.group("name"),
                    _line_number(source, match.start()),
                    _line_number(source, end),
                )
            )
    return symbols


def _clojure_called_names(source: str) -> list[str]:
    names = {
        match.rsplit("/", 1)[-1]
        for match in re.findall(
            r"\(\s*([A-Za-z_][\w!?*+./<>\-]*)",
            source,
        )
    }
    return sorted(
        name
        for name in names
        if name not in {"is", "testing", "let", "do", "fn"}
    )


def _clojure_balanced_end(source: str, start: int) -> int | None:
    depth = 0
    quote = False
    escaped = False
    comment = False
    for index in range(start, len(source)):
        char = source[index]
        if comment:
            if char == "\n":
                comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quote = False
            continue
        if char == ";":
            comment = True
        elif char == '"':
            quote = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _normalise_powershell_module(value: str) -> str:
    normalised = Path(value.replace("\\", "/")).as_posix()
    for extension in (".psm1", ".ps1"):
        if normalised.lower().endswith(extension):
            normalised = normalised[: -len(extension)]
            break
    return normalised.strip("./")


def _resolve_powershell_import(
    current_module: str,
    requested: str,
) -> str:
    value = requested.replace("\\", "/")
    value = re.sub(r"(?i)\$PSScriptRoot", ".", value)
    if value.startswith("."):
        value = posixpath.normpath(
            posixpath.join(posixpath.dirname(current_module), value)
        )
    return _normalise_powershell_module(value)


def _powershell_called_names(source: str) -> list[str]:
    names = set(
        re.findall(
            r"(?im)(?:^|[|;&])\s*([A-Za-z_][\w-]*)",
            source,
        )
    )
    ignored = {
        "describe", "context", "it", "should", "beforeall",
        "beforeeach", "afterall", "aftereach", "foreach", "if",
        "else", "return", "throw", "write-output",
    }
    return sorted(name for name in names if name.lower() not in ignored)


def _read_source(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

def _javascript_framework(start: Path, root: Path) -> str:
    directories = [start, *start.parents]
    for directory in directories:
        try:
            directory.relative_to(root)
        except ValueError:
            break
        package = directory / "package.json"
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if directory == root:
                break
            continue
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            break

        dependencies = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
        }
        scripts = " ".join(data.get("scripts", {}).values())
        combined = " ".join([*dependencies.keys(), scripts]).lower()
        if "vitest" in combined:
            return "vitest"
        if "mocha" in combined:
            return "mocha"
        return "jest"
    return "jest"


def _symbol_ranges(
    source: str,
    function_pattern: re.Pattern[str],
    class_pattern: re.Pattern[str],
) -> list[tuple[str, str, int, int]]:
    return [
        *_ranges_for_pattern(source, function_pattern, "function"),
        *_ranges_for_pattern(source, class_pattern, "class"),
    ]


def _ranges_for_pattern(
    source: str,
    pattern: re.Pattern[str],
    kind: str,
) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    for match in pattern.finditer(source):
        open_brace = source.find("{", match.start(), match.end())
        if open_brace < 0:
            continue
        end = _balanced_end(source, open_brace, "{", "}")
        if end is None:
            continue
        symbols.append(
            (
                kind,
                match.group("name"),
                _line_number(source, match.start()),
                _line_number(source, end),
            )
        )
    return symbols


def _analyse_ranges(
    source: str,
    changed_lines: list[int],
    symbols: list[tuple[str, str, int, int]],
) -> Impact:
    if not changed_lines:
        return {
            "changed_functions": [],
            "changed_classes": [],
            "module_level_change": True,
            "analysis_status": "file_level",
        }

    changed = set(changed_lines)
    covered: set[int] = set()
    functions: set[str] = set()
    classes: set[str] = set()
    for kind, name, start, end in symbols:
        overlap = {line for line in changed if start <= line <= end}
        if not overlap:
            continue
        covered.update(overlap)
        (classes if kind == "class" else functions).add(name)

    source_lines = source.splitlines()
    meaningful_uncovered = {
        line
        for line in changed - covered
        if 0 < line <= len(source_lines)
        and source_lines[line - 1].strip()
        and not source_lines[line - 1].lstrip().startswith(("//", "/*", "*"))
    }
    return {
        "changed_functions": sorted(functions),
        "changed_classes": sorted(classes),
        "module_level_change": bool(meaningful_uncovered),
        "analysis_status": "analysed",
    }


def _called_names(source: str) -> list[str]:
    return sorted(
        {
            name
            for name in _CALL.findall(source)
            if name not in _IGNORED_CALLS
        }
    )


def _resolve_js_import(current_module: str, specifier: str) -> str:
    base = posixpath.dirname(current_module)
    resolved = posixpath.normpath(posixpath.join(base, specifier))
    for extension in sorted(JAVASCRIPT_EXTENSIONS, key=len, reverse=True):
        if resolved.lower().endswith(extension):
            resolved = resolved[: -len(extension)]
            break
    if resolved.endswith("/index"):
        resolved = resolved[:-6]
    return resolved.strip("./")


def _balanced_end(
    source: str,
    start: int,
    opening: str,
    closing: str,
) -> int | None:
    if start < 0:
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = start
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', chr(96)}:
            quote = char
        elif char == "/" and next_char == "/":
            line_comment = True
            index += 2
            continue
        elif char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, max(offset, 0)) + 1
