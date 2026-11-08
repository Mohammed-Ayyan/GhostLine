import ast
import os
import sys

def check_duplicates(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except Exception as e:
            print(f'Parse error in {filepath}: {e}')
            return False

    errors = []
    class ScopeVisitor(ast.NodeVisitor):
        def visit_Module(self, node):
            self.check_scope(node.body, filepath, 'module')
            self.generic_visit(node)
        def visit_ClassDef(self, node):
            self.check_scope(node.body, filepath, f'class {node.name}')
            self.generic_visit(node)
        def check_scope(self, body, path, scope_name):
            seen = {}
            for item in body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = item.name
                    if name in seen:
                        is_prop = any(isinstance(d, ast.Attribute) and d.attr == 'setter' for d in getattr(item, 'decorator_list', []))
                        if not is_prop:
                            errors.append(f'{path}:{item.lineno}: duplicate definition of "{name}" in {scope_name} (first defined at line {seen[name]})')
                    else:
                        seen[name] = item.lineno

    ScopeVisitor().visit(tree)
    if errors:
        for err in errors:
            print(err)
        return False
    return True

if __name__ == '__main__':
    all_clean = True
    for root, dirs, files in os.walk('ghostline'):
        for f in files:
            if f.endswith('.py'):
                if not check_duplicates(os.path.join(root, f)):
                    all_clean = False

    if all_clean:
        print('Duplicate-definition check: ALL CLEAN (0 duplicates)')
        sys.exit(0)
    else:
        sys.exit(1)
