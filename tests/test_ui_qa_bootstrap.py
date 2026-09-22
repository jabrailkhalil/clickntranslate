"""The screenshot harness must preserve native Windows import ordering."""
import ast
from pathlib import Path


def test_screenshot_harness_imports_main_before_any_qt_dependency():
    source = (Path(__file__).resolve().parents[1] / 'tools' / 'qa_ui_polish.py').read_text(encoding='utf-8')
    imports = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.lineno, node.module or ''))
    main_line = next(line for line, name in imports if name == 'main')
    qt_imports = [line for line, name in imports
                  if name.startswith('PyQt5') or name in ('ui_scaling', 'qt_layout_test_support')]
    assert qt_imports
    assert all(main_line < line for line in qt_imports)
