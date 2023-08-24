import ast
from functools import cached_property
import pkgutil
import os
import subprocess
import importlib


class Pruner:

    def __init__(self, package_name: str, source_dir: str = None, output_dir:str = os.path.join(os.getcwd(), "pypruner_output")):
        self.package_name = package_name
        self.output_dir = output_dir
        self._source_dir = source_dir

    @property
    def source_dir(self):
        if self._source_dir is not None:
            return self._source_dir
        else:
            return subprocess.check_output(["pip", "download", "--no-deps", " --no-binary", ":all:", self.package_name], text=True)

    @cached_property
    def package(self):
        return __import__(self.package_name)

    @cached_property
    def path(self):
        return self.package.__path__[0]

    @cached_property
    def list_modules(self):
        module_list = []
        for _, module_name, _ in pkgutil.iter_modules(self.package.__path__):
            module_path = os.path.join(self.path, module_name + ".py")
            relative_module_path = os.path.relpath(module_path, self.path)
            module_dict = {
                'module_name': module_name,
                'module_path': module_path,
                'relative_module_path': relative_module_path,
                'tree': ast.parse(open(module_path, "r").read()),
                'output_path': os.path.join(self.output_dir, relative_module_path),
                'classes': []
            }
            for node in module_dict['tree'].body:
                if isinstance(node, ast.ClassDef):
                    module_dict['classes'].append(node.name)
            module_list.append(module_dict)
        return module_list

    @cached_property
    def list_callables(self):
        pass


    def get_module(self, module_name):
        # Get the path to the module
        modules = [module for module in self.list_modules if module["module_name"] == module_name]

        # Raise an exception if the module is not found
        if len(modules) == 0:
            raise Exception(f"Module {module_name} not found in package {self.package_name}")
        else:
            return modules[0]

    def remove_class(self, filename, class_name: str, module_name: str = None):
        
        if module_name is None:
            module_list = self.list_modules

        else:
            # Read the code from the file
            module_list = [self.get_module(module_name)]

        for module in module_list:
            # Traverse the AST to find the class definition

            for node in module["tree"].body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    class_def = node
                    module["tree"].body.remove(class_def)

                    new_code = ast.unparse(module["tree"])

                    with open(filename, "w") as outfile:
                        outfile.write(new_code)


                    break

    def remove_method(self, filename, class_name: str, method_name: str, module_name: str = None):
        
        if module_name is None:
            module_list = self.list_modules

        else:
            # Read the code from the file
            module_list = [self.get_module(module_name)]

        for module in module_list:
            # Traverse the AST to find the class definition

            for node in module["tree"].body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:

                    # Traverse the class body to find the method definition
                    for sub_node in node.body:
                        if isinstance(sub_node, ast.FunctionDef) and sub_node.name == method_name:
                            node.body.remove(sub_node)

                            new_code = ast.unparse(module["tree"])

                            with open(module["output_path"], "w") as outfile:
                                outfile.write(new_code)

                            print(f"Method {method_name} removed from class {class_name} in {filename}")

                            break



    def find_all_self_calls(self, class_name: str, method_name: str):
        self_calls = []

        for module in self.list_modules:
            for node in module["tree"].body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for sub_node in node.body:
                        if isinstance(sub_node, ast.FunctionDef) and sub_node.name == method_name:
                            for stmt in ast.walk(sub_node):
                                if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute):
                                    if isinstance(stmt.func.value, ast.Name) and stmt.func.value.id == 'self':
                                        self_calls.append(stmt.func.attr)

        return self_calls

    def find_all_calls(self, class_name: str, method_name: str):
        all_calls = []

        for module in self.list_modules:
            for node in module["tree"].body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for sub_node in node.body:
                        if isinstance(sub_node, ast.FunctionDef) and sub_node.name == method_name:
                            # sub_nodes is a tupe of (statement, target)
                            sub_nodes = [(statement, None) for statement in ast.walk(sub_node)]
                            for stmt, target in sub_nodes:
                                if isinstance(stmt, ast.Assign):
                                    # Adding it back to the list of sub_nodes with a target
                                    if isinstance(stmt.targets[0], ast.Subscript):
                                        target = stmt.targets[0].value.id
                                    else:
                                        target = stmt.targets[0].id
                                    sub_nodes.append((stmt.value, target))
                                if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
                                    # if its a call, put it back in the list
                                    all_calls.append({
                                        "called": stmt.func.id,
                                        "target": target,
                                        "unparsed": ast.unparse(stmt),
                                    })

        return all_calls

    def list_imports(self):
        imported_modules = []
        for module in self.list_modules:
            tree = ast.parse(module["tree"])
            for node in ast.walk(tree):
                this_package = False
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if len(name.name.split("."))>1:
                                import_from = name.name.split(".")[0]
                                import_name = name.name.split(".")[1]
                        else:
                            import_name = name.name
                            import_from= None
                        imported_modules.append({
                            "import_name": import_name,
                            "import_from": import_from,
                            "import_all": False,
                            "origin": importlib.util.find_spec(name.name).origin,
                            "alias": name.asname,
                            "unparsed": ast.unparse(node),
                            })
                elif isinstance(node, ast.ImportFrom):

                    for name in node.names:
                        if node.module is not None:
                                if "from ." in ast.unparse(node):
                                    import_name = node.module
                                    import_from = self.package_name
                                else:
                                    import_from = node.module
                        elif "from ." in ast.unparse(node):
                            import_from = self.package_name
                            origin = self.path
                        else:
                            import_from = None
                            is_relative = False

                        if name.name == "*":
                            import_all = True
                        else:
                            import_all = False
                            import_name = name.name

                        imported_modules.append({
                            "import_name": import_name,
                            "import_from": import_from,
                            "import_all": import_all,
                            "origin": importlib.util.find_spec(import_from).origin,
                            "alias": name.asname,
                            "unparsed": ast.unparse(node),
                            })


        for module in imported_modules:
            # Check if the module is in the package
            if module["import_from"] in [package_module["module_name"] for package_module in self.list_modules]:
                module["this_package"] = True
            else:   
                module["this_package"] = False



        return imported_modules
    
    def find_interdependencies(self, class_name: str, method_name: str):
        interdependent_modules = {}     
        assignments = {}

        for call in self.find_all_calls(class_name, method_name):
            # Finding any called modules
            called_modules = [module for module in self.list_modules if call["called"] in module["classes"]]
            for module in called_modules:
                # If the called module is in the package, add it to the list, or create a list if not exists
                interdependent_modules.setdefault(module["module_name"], []).append(call["called"])
                #TODO: Need to find times the target was called to see what method was used
                if call["target"] is not None:
                    assignments[module["module_name"]] = call["target"]
        # Getting rid of duplicates
        for module in interdependent_modules:
            interdependent_modules[module] = list(set(interdependent_modules[module]))
        
        # Recursively finding interdependencies of interdependencies
        if len(interdependent_modules) > 0:
            print(interdependent_modules)
            for module, classes in interdependent_modules.items():
                for called_class in classes:
                    recursive_dependencies = self.find_interdependencies(module, called_class)
                    print(f"Module: {module}, Class: {called_class}")
                    print(f"Recursive dependencies: {recursive_dependencies}")
                    interdependent_modules[module].extend(
                        recursive_dependencies)


        return interdependent_modules
