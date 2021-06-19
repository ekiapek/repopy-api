from os.path import basename
import astroid
import glob

import jsons
from logic.RepositoryModel import ClassModel, RepositoryModel, ParentClassModel, DocumentModel, ImportModuleModel, FunctionModel
import os
import jsonpickle


def parseCode(base_dir, repository_id):
    # root_dir needs a trailing slash (i.e. /root/dir/)
    repo = RepositoryModel()
    repo.RepositoryID = repository_id
    repo.BasePath = base_dir

    # f = open(base_dir+"demoparse.txt", "a")
    for filename in glob.iglob(base_dir + '**/*.py', recursive=True):
        file = open(filename).read()
        code = astroid.parse(file)
        document = DocumentModel()
        document.DocumentPath = filename
        document.DocumentName = os.path.basename(filename)
        # print(code.repr_tree())
    #     f.write("FILE: "+filename+"\n")
    #     f.write(code.repr_tree())
    #     f.write("\n\n")
    # f.close
        for node in code.body:
            # print()
            if(isinstance(node, astroid.ImportFrom)):
                for mn in node.names:
                    importedModule = ImportModuleModel()
                    importedModule.ModulePackageName = node.modname
                    importedModule.ModuleName = mn[0]
                    importedModule.ModuleAliasName = mn[1]
                    document.Imports.append(importedModule)

            if(isinstance(node, astroid.Import)):
                for mn in node.names:
                    importedModule = ImportModuleModel()
                    importedModule.ModuleName = mn[0]
                    importedModule.ModuleAliasName = mn[1]
                    document.Imports.append(importedModule)

            if(isinstance(node, astroid.ClassDef)):
                namespace = os.path.splitext(document.DocumentName)[0]
                classNode = parseClassOnly(node=node, imports=document.Imports, namespace=namespace)
                document.Classes += classNode

            if(isinstance(node,astroid.FunctionDef)):
                for funcbody in node.body:
                    if(isinstance(funcbody,astroid.ClassDef)):
                        namespace = ".".join([os.path.splitext(document.DocumentName)[0],node.name])
                        classNode = parseClassOnly(node=funcbody, imports=document.Imports, namespace=namespace)
                        document.Classes += classNode                

        repo.Documents.append(document)
    # f = open("hasil_parse.json","a")
    # f.write(jsons.dumps(repo))
    # f.close()
    return repo

def parseClassOnly(node, imports, namespace=None):
    # print("\n"+filename)
    returnedClass = []
    classNode = ClassModel()
    classNode.Name = node.name
    classNode.LineNo = node.blockstart_tolineno
    classNode.ColOffset = node.col_offset
    classNode.Type = node.type
    classNode.Namespace = namespace

    if(len(node.bases) > 0):
        # print(node.name+" line: "+str(node.blockstart_tolineno)+" col: "+str(node.col_offset)+" Parent: ")
        for base in node.bases:
            if(isinstance(base, astroid.Attribute)):
                for basename in node.basenames:
                    if base.attrname in basename:
                        attrNode = ParentClassModel()
                        attrNode.Name = basename
                        attrNode.Type = "attribute"
                        classNode.Parents.append(attrNode)
                        break
                # attrNode.Name = 
                # if(isinstance(base.expr, astroid.Name)):
                    # for x in imports:
                    #     if(x.ModuleAliasName != None):
                    #         if(x.ModuleAliasName == base.expr.name):
                    #             attrNode = ParentClassModel()
                    #             if x.ModulePackageName != None:
                    #                 attrNode.Name = x.ModulePackageName + "." + \
                    #                                 x.ModuleAliasName + "." + base.attrname
                    #             else:
                    #                 attrNode.Name = x.ModuleAliasName + "." + base.attrname
                    #             attrNode.Type = "attribute"
                    #             classNode.Parents.append(attrNode)
                    #             break
                    #         else:
                    #             attrNode = ParentClassModel()
                    #             attrNode.Name = base.attrname
                    #             attrNode.Type = "attribute"
                    #             classNode.Parents.append(attrNode)
                    #     else:
                    #         if(x.ModuleName == base.expr.name):
                    #             attrNode = ParentClassModel()
                    #             if x.ModulePackageName != None:
                    #                 attrNode.Name = x.ModulePackageName + "." + x.ModuleName + "." + base.attrname
                    #             else:
                    #                 attrNode.Name = x.ModuleName + "." + base.attrname
                    #             attrNode.Type = "attribute"
                    #             classNode.Parents.append(attrNode)
                    #             break
                    #         else:
                    #             attrNode = ParentClassModel()
                    #             attrNode.Name = base.attrname
                    #             attrNode.Type = "attribute"
                    #             classNode.Parents.append(attrNode)

                # print(base.attrname+" col: "+str(base.col_offset))
            elif(isinstance(base, astroid.Call)):
                funcNode = ParentClassModel()
                funcNode.Name = base.func.name
                funcNode.Type = "function"
                classNode.Parents.append(funcNode)
            else:
                parentNode = ParentClassModel()
                parentNode.Name = base.name
                parentNode.Type = "class"
                classNode.Parents.append(parentNode)

    if(len(node.body) > 0):
        for clsbody in node.body:
            if(isinstance(clsbody, astroid.FunctionDef)):
                func = FunctionModel()
                func.Name = clsbody.name
                func.ColOffset = clsbody.col_offset
                func.LineNo = clsbody.lineno
                classNode.Functions.append(func)

                for funcbody in clsbody.body:
                    if(isinstance(funcbody,astroid.ClassDef)):
                        returnedClass += parseClassOnly(funcbody,imports,".".join([namespace,classNode.Name,func.Name]))
            
            if(isinstance(clsbody,astroid.ClassDef)):
                returnedClass += parseClassOnly(clsbody,imports,".".join([namespace,classNode.Name]))

    returnedClass.append(classNode)
    return returnedClass