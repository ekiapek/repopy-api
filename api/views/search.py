import traceback
from typing import Tuple
import django_heroku
from redisgraph.graph import Graph
from repopy.settings import REDISEARCH_CLIENT, REDISEARCH_INSTANCE, REDISGRAPH_INSTANCE, RESERVED_KEYWORDS, RESPONSE_ERROR, RESPONSE_SUCCESS
from api.views import repository
from django.http import HttpResponse,JsonResponse, response
from django.conf import settings
import os
import jsons
from redisearch import *
import redisearch.aggregation as aggregations
import redisearch.reducers as reducers
from api.models.ApiModel import ErrorModel, ResponseModel,SearchResultModel,SearchResultRelationModel
import redis
from django.utils.html import escape

redisearch_instance = REDISEARCH_INSTANCE
redisgraph_instance = REDISGRAPH_INSTANCE

def searchSuggest(request):
    if 'q' in request.GET and 'Repository' in request.GET:
        searchQ = request.GET['q']
        repository = request.GET['Repository']
        ac = AutoCompleter(repository,conn=redisearch_instance)
        res = ac.get_suggestions(searchQ,fuzzy=True)
        retr = jsons.dump(res)
        return JsonResponse(retr,safe=False)
        

# def selectRepo(request):
#     if request.method == 'POST' and 'repository' in request.POST:
#         repo = request.POST['repository']
#         try:
#             if rclient == None:
#                 rclient = Client(repo,conn=redis_instance)
#                 response = ResponseModel()
#                 response.ResponseCode = RESPONSE_SUCCESS
#                 response.ResponseMessage = "Success select repository"
#                 return JsonResponse(response)
#             else:
#                 rclient.index_name = repo
#                 response = ResponseModel()
#                 response.ResponseCode = RESPONSE_SUCCESS
#                 response.ResponseMessage = "Success select repository"
#                 return JsonResponse(response)
#         except:
#             response = ResponseModel()
#             response.ResponseCode = RESPONSE_ERROR
#             response.ResponseMessage = "Error select repository"
#             return JsonResponse(response)

def search(request):
    if 'q' in request.GET and 'Repository' in request.GET:
        listResult = []

        searchQ = str(request.GET['q'])
        repository = str(request.GET['Repository'])

        try:        
            client = Client(repository,conn=redisearch_instance)
            graphName = repository + "-Relations"
            graph = Graph(graphName,redisgraph_instance)
            clientTerms = Client(repository+"-Terms",conn=redisearch_instance)
            
            splitQuery = searchQ.split()
            splitQuery2 = searchQ.split()

            relatedWithQ = []
            parentOfQ = []
            childOfQ = []
            functionInQ = []
            #region query extraction
            if ":related-with" in splitQuery:
                foundAnotherReserved = False
                i = splitQuery.index(":related-with")
                i += 1
                while i<len(splitQuery) and not foundAnotherReserved:
                    if splitQuery[i] in RESERVED_KEYWORDS:
                        foundAnotherReserved = True
                    else:
                        relatedWithQ.append(splitQuery[i])
                    i += 1

                x = splitQuery.index(":related-with")
                if foundAnotherReserved:
                    del splitQuery[x:i-1]
                else:
                    del splitQuery[x:i]

            if ":parent-of" in splitQuery:
                foundAnotherReserved = False
                i = splitQuery.index(":parent-of")
                i += 1
                while i<len(splitQuery) and not foundAnotherReserved:
                    if splitQuery[i] in RESERVED_KEYWORDS:
                        foundAnotherReserved = True
                    else:
                        parentOfQ.append(splitQuery[i])
                    i+=1
                
                x = splitQuery.index(":parent-of")
                if foundAnotherReserved:
                    del splitQuery[x:i-1]
                else:
                    del splitQuery[x:i]

            if ":child-of" in splitQuery:
                foundAnotherReserved = False
                i = splitQuery.index(":child-of")
                i += 1
                while i<len(splitQuery) and not foundAnotherReserved:
                    if splitQuery[i] in RESERVED_KEYWORDS:
                        foundAnotherReserved = True
                    else:
                        childOfQ.append(splitQuery[i])
                    i+=1

                x = splitQuery.index(":child-of")
                if foundAnotherReserved:
                    del splitQuery[x:i-1]
                else:
                    del splitQuery[x:i]
                
            if (":function" and ":in" in splitQuery) and (splitQuery.index(":function") < splitQuery.index(":in")):
                functions = []
                classes = []

                foundAnotherReserved = False
                foundAnotherReserved2 = False

                i = splitQuery.index(":function")
                i += 1
                while i<len(splitQuery) and not foundAnotherReserved:
                    if splitQuery[i] in RESERVED_KEYWORDS:
                        foundAnotherReserved = True
                    else:
                        functions.append(splitQuery[i])
                    i+=1

                j = splitQuery.index(":in")
                j += 1
                while j<len(splitQuery) and not foundAnotherReserved2:
                    if splitQuery[j] in RESERVED_KEYWORDS:
                        foundAnotherReserved = True
                    else:
                        classes.append(splitQuery[j])
                    j+=1

                for a in functions:
                    for b in classes:
                        tupFuncClass = [a,b]
                        functionInQ.append(tupFuncClass)

                x = splitQuery.index(":function")
                del splitQuery[x:i-1]

                y = splitQuery.index(":in")
                if foundAnotherReserved2:
                    del splitQuery[y:j-(i-1)]
                else:
                    del splitQuery[x:i]
            #endregion

            if len(relatedWithQ) > 0:
                rediSearchRes = []                
                
                for query in relatedWithQ:
                    qTerm = Query(str(query).lower())
                    resTerms = clientTerms.search(qTerm)
                    for result in resTerms.docs:
                        rediSearchRes.append(result)

                if len(rediSearchRes)>0:
                    for res in rediSearchRes:
                        if res.ClassName != "":
                            resgraphClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}}) RETURN n""".format(res.ClassName,res.FileID))
                            for graphRes in resgraphClassOnly.result_set:
                                ressClass = graphRes[0].properties
                                resModel = SearchResultModel()
                                resModel.Result = ressClass['ClassName']
                                resModel.LineNo = ressClass['LineNo']
                                resModel.ColOffset = ressClass['ColOffset']
                                resModel.FileID = ressClass['FileID']
                                resModel.Filename = ressClass['Filename']
                                
                                resRelatedAsParent = findParentRecursive(graph=graph,currentClass=ressClass,level=1)
                                if resRelatedAsParent is not None and len(resRelatedAsParent) > 0:
                                    resModel.HasRelation = True
                                    resModel.Relations += resRelatedAsParent

                                resRelatedAsChild = findChildRecursive(graph=graph,currentClass=ressClass,level=1)
                                if resRelatedAsChild is not None and len(resRelatedAsChild) > 0:
                                    resModel.HasRelation = True
                                    resModel.Relations += resRelatedAsChild

                                listResult.append(resModel)

            if len(parentOfQ) > 0:
                rediSearchRes = []                
                
                for query in parentOfQ:
                    qTerm = Query(str(query).lower())
                    resTerms = clientTerms.search(qTerm)
                    for result in resTerms.docs:
                        rediSearchRes.append(result)

                if len(rediSearchRes)>0:
                    for res in rediSearchRes:
                        if res.ClassName != "":
                            resgraphClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}}) RETURN n""".format(res.ClassName,res.FileID))
                            for graphRes in resgraphClassOnly.result_set:
                                ressClass = graphRes[0].properties
                                resModel = SearchResultModel()
                                resModel.Result = ressClass['ClassName']
                                resModel.LineNo = ressClass['LineNo']
                                resModel.ColOffset = ressClass['ColOffset']
                                resModel.FileID = ressClass['FileID']
                                resModel.Filename = ressClass['Filename']

                                # resRelatedAsChild = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})<-[r:parentOf]-(m:Class) RETURN m""".format(ressClass['ClassName'],ressClass['FileID']))
                                # if len(resRelatedAsChild.result_set) > 0:
                                #     resModel.HasRelation = True
                                #     for resParent in resRelatedAsChild.result_set:
                                #         parent = resParent[0].properties
                                        
                                #         parentModel = SearchResultRelationModel()
                                #         parentModel.RelationName = "parent"
                                #         parentModel.Result = parent['ClassName']
                                #         parentModel.LineNo = parent['LineNo']
                                #         parentModel.ColOffset = parent['ColOffset']
                                #         parentModel.Filename = parent['Filename']
                                #         parentModel.FileID = parent['FileID']

                                #         resModel.Relations.append(parentModel)

                                resRelatedAsParent = findParentRecursive(graph=graph,currentClass=ressClass,level=1)
                                if resRelatedAsParent is not None and len(resRelatedAsParent) > 0:
                                    resModel.HasRelation = True
                                    resModel.Relations += resRelatedAsParent

                                listResult.append(resModel)

            if len(childOfQ) > 0:
                rediSearchRes = []                
                
                for query in childOfQ:
                    qTerm = Query(str(query).lower())
                    resTerms = clientTerms.search(qTerm)
                    for result in resTerms.docs:
                        rediSearchRes.append(result)

                if len(rediSearchRes)>0:
                    for res in rediSearchRes:
                        if res.ClassName != "":
                            resgraphClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}}) RETURN n""".format(res.ClassName,res.FileID))
                            for graphRes in resgraphClassOnly.result_set:
                                ressClass = graphRes[0].properties
                                resModel = SearchResultModel()
                                resModel.Result = ressClass['ClassName']
                                resModel.LineNo = ressClass['LineNo']
                                resModel.ColOffset = ressClass['ColOffset']
                                resModel.FileID = ressClass['FileID']
                                resModel.Filename = ressClass['Filename']
                                
                                # resRelatedAsParent = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})-[r:parentOf]->(m:Class) RETURN m""".format(ressClass['ClassName'],ressClass['FileID']))
                                # if len(resRelatedAsParent.result_set) > 0:
                                #     resModel.HasRelation = True
                                #     for resChild in resRelatedAsParent.result_set:
                                #         child = resChild[0].properties

                                #         childModel = SearchResultRelationModel()
                                #         childModel.RelationName = "child"
                                #         childModel.Result = child['ClassName']
                                #         childModel.LineNo = child['LineNo']
                                #         childModel.ColOffset = child['ColOffset']
                                #         childModel.Filename = child['Filename']
                                #         childModel.FileID = child['FileID']

                                #         resModel.Relations.append(childModel)

                                resRelatedAsChild = findChildRecursive(graph=graph,currentClass=ressClass,level=1)
                                if resRelatedAsChild is not None and len(resRelatedAsChild) > 0:
                                    resModel.HasRelation = True
                                    resModel.Relations += resRelatedAsChild

                                listResult.append(resModel)

            if len(functionInQ) > 0:
                rediSearchRes = []                
                
                for query in functionInQ:
                    qTermFunction = Query(str(query[0]).lower())
                    qTermClass = Query(str(query[1]).lower())
                    resFunction = clientTerms.search(qTermFunction)
                    resClass = clientTerms.search(qTermClass)
                    for resultFunction in resFunction.docs:
                        for resultClass in resClass.docs:
                            tupResult = [resultFunction,resultClass]
                            if not any(tupResult[0].FunctionName == x[0].FunctionName and tupResult[0].FileID == x[0].FileID and tupResult[1].ClassName == x[1].ClassName and tupResult[1].FileID == x[1].FileID for x in rediSearchRes):
                                rediSearchRes.append(tupResult)

                for tupRedisResult in rediSearchRes:
                    resFunc = tupRedisResult[0]
                    resCls = tupRedisResult[1]
                    resGraph = graph.query("""MATCH (n:Function{{Name:"{0}",FileID:"{1}"}})<-[r:HasFunction]-(m:Class{{ClassName:"{2}",FileID:"{3}"}}) RETURN n,m""".format(resFunc.FunctionName,resFunc.FileID,resCls.ClassName,resCls.FileID))
                    if resGraph is not None and len(resGraph.result_set) > 0:
                        for graphRes in resGraph.result_set:
                            ressFunc = graphRes[0].properties
                            ressClass = graphRes[1].properties
                            resModel = SearchResultModel()
                            resModel.Result = ressFunc['Name']
                            resModel.LineNo = ressFunc['LineNo']
                            resModel.ColOffset = ressFunc['ColOffset']
                            resModel.FileID = ressFunc['FileID']
                            resModel.Filename = ressFunc['Filename']
                            resModel.HasRelation = True

                            resRelationModel = SearchResultRelationModel()
                            resRelationModel.Result = ressClass['ClassName']
                            resRelationModel.LineNo = ressClass['LineNo']
                            resRelationModel.ColOffset = ressClass['ColOffset']
                            resRelationModel.FileID = ressClass['FileID']
                            resRelationModel.Filename = ressClass['Filename']
                            resRelationModel.RelationName = "class"

                            resModel.Relations.append(resRelationModel)

                            listResult.append(resModel)
                    else:
                        #finding function definition in parent class
                        resgraphCurrentClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}}) RETURN n""".format(resCls.ClassName,resCls.FileID))                        
                        if resgraphCurrentClassOnly is not None and len(resgraphCurrentClassOnly.result_set) > 0:
                            for cls in resgraphCurrentClassOnly.result_set:
                                currCls = cls[0].properties
                                ressFunction = findFunctionInParentRecursive(graph=graph,currentClass=currCls,currentFunction=resFunc)
                                if ressFunction is not None and len(ressFunction) > 0:
                                    listResult.extend(ressFunction)

            if len(splitQuery) > 0:
                rediSearchRes = []  #contains indexed terms in RediSearch
                
                #search terms in RediSearch indexed terms
                for query in splitQuery:
                    qTerm = Query(str(query).lower())
                    resTerms = clientTerms.search(qTerm)
                    for result in resTerms.docs:
                        rediSearchRes.append(result)

                if len(rediSearchRes)>0:
                    for res in rediSearchRes:
                        if res.ClassName != "":
                            resgraphClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}}) RETURN n""".format(res.ClassName,res.FileID))
                            for graphRes in resgraphClassOnly.result_set:
                                ressClass = graphRes[0].properties
                                resModel = SearchResultModel()
                                resModel.Result = ressClass['ClassName']
                                resModel.LineNo = ressClass['LineNo']
                                resModel.ColOffset = ressClass['ColOffset']
                                resModel.FileID = ressClass['FileID']
                                resModel.Filename = ressClass['Filename']
                                
                                resRelatedAsChild = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})-[r:parentOf]->(m:Class) RETURN m""".format(ressClass['ClassName'],ressClass['FileID']))
                                if resRelatedAsChild is not None and len(resRelatedAsChild.result_set) > 0:
                                    resModel.HasRelation = True
                                    for resChild in resRelatedAsChild.result_set:
                                        child = resChild[0].properties
                                        childModel = SearchResultRelationModel()
                                        childModel.RelationName = "child"
                                        childModel.Result = child['ClassName']
                                        childModel.LineNo = child['LineNo']
                                        childModel.ColOffset = child['ColOffset']
                                        childModel.Filename = child['Filename']
                                        childModel.FileID = child['FileID']

                                        resModel.Relations.append(childModel)

                                resRelatedAsParent = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})<-[r:parentOf]-(m:Class) RETURN m""".format(ressClass['ClassName'],ressClass['FileID']))
                                if len(resRelatedAsParent.result_set) > 0:
                                    resModel.HasRelation = True
                                    for resParent in resRelatedAsParent.result_set:
                                        parent = resParent[0].properties
                                        
                                        parentModel = SearchResultRelationModel()
                                        parentModel.RelationName = "parent"
                                        parentModel.Result = parent['ClassName']
                                        parentModel.LineNo = parent['LineNo']
                                        parentModel.ColOffset = parent['ColOffset']
                                        parentModel.Filename = parent['Filename'] if 'Filename' in parent else ""
                                        parentModel.FileID = parent['FileID'] if 'FileID' in parent else ""

                                        resModel.Relations.append(parentModel)

                                if not foundDuplicateInSearchResult(obj=resModel,listResult=listResult):
                                    listResult.append(resModel)

                        if res.FunctionName != "":
                            resgraphFuncOnly = graph.query("""MATCH (n:Function{{Name:"{0}"}}) RETURN n""".format(res.FunctionName))
                            for graphRes in resgraphFuncOnly.result_set: 
                                ressFunc = graphRes[0].properties                               
                                resRelatedClass = graph.query("""MATCH (n:Function{{Name:"{0}",FileID:"{1}"}})<-[r:HasFunction]-(m:Class) RETURN n,m""".format(ressFunc['Name'],ressFunc['FileID']))
                                if len(resRelatedClass.result_set) > 0:
                                    for resClass in resRelatedClass.result_set:
                                        fun = resClass[0].properties
                                        cls = resClass[1].properties
                                        if fun['Name']==ressFunc['Name'] and fun['LineNo']==ressFunc['LineNo'] and fun['ColOffset']==ressFunc['ColOffset'] and fun['FileID']==ressFunc['FileID'] and fun['Filename']==ressFunc['Filename']:
                                            resModel = SearchResultModel()
                                            resModel.Result = ressFunc['Name']
                                            resModel.LineNo = ressFunc['LineNo']
                                            resModel.ColOffset = ressFunc['ColOffset']
                                            resModel.FileID = ressFunc['FileID']
                                            resModel.Filename = ressFunc['Filename']
                                            resModel.HasRelation = True
                                            clsModel = SearchResultRelationModel()
                                            clsModel.RelationName = "class"
                                            clsModel.Result = cls['ClassName']
                                            clsModel.LineNo = cls['LineNo']
                                            clsModel.ColOffset = cls['ColOffset']
                                            clsModel.Filename = cls['Filename']
                                            clsModel.FileID = cls['FileID']

                                            resModel.Relations.append(clsModel)
                                            if not foundDuplicateInSearchResult(obj=resModel,listResult=listResult):
                                                listResult.append(resModel)

                                
            
                #region search in all document indexed by RediSearch
                qOther = Query("%"+str(" ".join(splitQuery)+"%").lower()).summarize(fields="Content",context_len=5,num_frags=1)
                resOther = client.search(qOther)
                for result in resOther.docs:
                    if not any(x.FileID == result.id[4:] for x in listResult):
                        resModel = SearchResultModel()
                        resModel.Result = escape(result.Content)
                        resModel.FileID = result.id[4:]
                        resModel.Filename = result.DocumentName
                        resModel.Query = " ".join(splitQuery)
                        listResult.append(resModel)

                for another in splitQuery:
                    qOther = Query(str(another).lower()).summarize(fields="Content",context_len=5,num_frags=1)
                    resOther = client.search(qOther)
                    for result in resOther.docs:
                        if not any(x.FileID == result.id[4:] for x in listResult):
                            resModel = SearchResultModel()
                            resModel.Result = escape(result.Content)
                            resModel.FileID = result.id[4:]
                            resModel.Filename = result.DocumentName
                            resModel.Query = str(another)
                            listResult.append(resModel)
                #endregion

            #region search remaining query term in all document indexed by RediSearch
            # listForAnotherQuery = list(filter(lambda x: x not in RESERVED_KEYWORDS and x not in splitQuery ,splitQuery2))
            # for another in listForAnotherQuery:
            #     qOther = Query(str(another).lower()).summarize(fields="Content",context_len=5,num_frags=1)
            #     resOther = client.search(qOther)
            #     for result in resOther.docs:
            #         if not any(x.FileID == result.id[4:] for x in listResult):
            #             resModel = SearchResultModel()
            #             resModel.Result = escape(result.Content)
            #             resModel.FileID = result.id[4:]
            #             resModel.Filename = result.DocumentName
            #             listResult.append(resModel)
            #endregion

            # q = Query(str(searchQ).lower()).paging(0,100).with_scores().highlight()
            # qTerm = Query(str(searchQ).lower())

            # resgraphClassOnly = graph.query("""MATCH (n:Class{{ClassName:"{0}"}}) RETURN n""".format(searchQ))
            # resgraphFuncOnly = graph.query("""MATCH (n:Function{{Name:"{0}"}}) RETURN n""".format(searchQ))
            # resgraph = graph.query("MATCH (n)-[]->(m) RETURN n,m")
            # res = client.search(q)
            # resTerms = clientTerms.search(qTerm)
            # retr = jsons.dump([resTerms,res,resgraph.result_set,resgraphClassOnly.result_set],strict=False)
            retr = jsons.dump(listResult,strict=False)
            return JsonResponse(retr,safe=False)
        except Exception as e:
            errmsg = traceback.format_exc(limit=1)
            tb = traceback.format_tb(e.__traceback__)
            err = ErrorModel(msg=errmsg, trace=tb,module="Indexer")
            retrmodelerr = jsons.dumps(err)
            django_heroku.logging.error(retrmodelerr)
            resp = ResponseModel()
            resp.ResponseCode = RESPONSE_ERROR
            resp.ResponseMessage = "error"
            retrmodel = jsons.dump(resp)
            return JsonResponse(retrmodel,safe=False)

def findFuntionInParent(graph,parentClass,currentFunction):
    listResFunc = []
    resGraphFunction = graph.query("""MATCH (n:Function{{Name:"{0}",FileID:"{1}"}})<-[r:HasFunction]-(m:Class{{ClassName:"{2}",FileID:"{3}"}}) RETURN n,m""".format(currentFunction.FunctionName,currentFunction.FileID,parentClass['ClassName'],parentClass['FileID']))
    if resGraphFunction is not None and len(resGraphFunction.result_set)>0:
        for resFunc in  resGraphFunction.result_set:
            listResFunc.append(resFunc[0].properties)
    else:
        return None

    return listResFunc

def findParentRecursive(graph,currentClass,level):
    listResParent = []
    resGraphParent = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})<-[r:parentOf]-(m:Class) RETURN m""".format(currentClass['ClassName'],currentClass['FileID']))
    if resGraphParent is not None and len(resGraphParent.result_set) > 0:
        for resParents in resGraphParent.result_set:
            currClass = resParents[0].properties
            # listResParent.append(resParents[0].properties)
            parentModel = SearchResultRelationModel()
            parentModel.Result = currClass['ClassName']
            parentModel.LineNo = currClass['LineNo']
            parentModel.ColOffset = currClass['ColOffset']
            parentModel.Filename = currClass['Filename'] if 'Filename' in currClass else ""
            parentModel.FileID = currClass['FileID'] if 'FileID' in currClass else ""
            if level > 1:
                parentModel.RelationName = "parent-"+str(level)
            else:
                parentModel.RelationName = "parent"
            listResParent.append(parentModel)

            resGraphParent2 = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})<-[r:parentOf]-(m:Class) RETURN m""".format(currClass['ClassName'],currClass['FileID']))
            if len(resGraphParent2.result_set) > 0:
                ressFindParent = findParentRecursive(graph=graph,currentClass=currClass,level=level+1)
                if ressFindParent is not None and len(ressFindParent) > 0:
                    listResParent += ressFindParent
    else:
        return None
    
    return listResParent

def findChildRecursive(graph,currentClass,level):
    listResChild = []
    resGraphChild = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})-[r:parentOf]->(m:Class) RETURN m""".format(currentClass['ClassName'],currentClass['FileID']))
    if resGraphChild is not None and len(resGraphChild.result_set) > 0:
        for reshild in resGraphChild.result_set:
            currClass = reshild[0].properties
            # listResParent.append(resParents[0].properties)
            childModel = SearchResultRelationModel()
            childModel.Result = currClass['ClassName']
            childModel.LineNo = currClass['LineNo']
            childModel.ColOffset = currClass['ColOffset']
            childModel.Filename = currClass['Filename']
            childModel.FileID = currClass['FileID']
            if level > 1:
                childModel.RelationName = "child-"+str(level)
            else:
                childModel.RelationName = "child"
            listResChild.append(childModel)

            resGraphChild2 = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})-[r:parentOf]->(m:Class) RETURN m""".format(currClass['ClassName'],currClass['FileID']))
            if resGraphChild2 is not None and len(resGraphChild2.result_set) > 0:
                ressFindChild = findChildRecursive(graph=graph,currentClass=currClass,level=level+1)
                if ressFindChild is not None and len(ressFindChild) > 0:
                    listResChild += ressFindChild
    else:
        return None
    
    return listResChild

def findFunctionInParentRecursive(graph,currentClass,currentFunction):
    listResult = []
    resGraphParent = graph.query("""MATCH (n:Class{{ClassName:"{0}",FileID:"{1}"}})<-[r:parentOf]-(m:Class) RETURN m""".format(currentClass['ClassName'],currentClass['FileID']))
    if len(resGraphParent.result_set) > 0:
        for resParents in resGraphParent.result_set:
            currClass = resParents[0].properties
            resFunc = findFuntionInParent(graph=graph,parentClass=currClass,currentFunction=currentFunction)
            if resFunc is not None and len(resFunc) > 0:
                # listResult = resFunc
                for func in resFunc:
                    resModel = SearchResultModel()
                    resModel.Result = func['Name']
                    resModel.LineNo = func['LineNo']
                    resModel.ColOffset = func['ColOffset']
                    resModel.FileID = func['FileID']
                    resModel.Filename = func['Filename']
                    resModel.HasRelation = True

                    resRelationModel = SearchResultRelationModel()
                    resRelationModel.Result = currClass['ClassName']
                    resRelationModel.LineNo = currClass['LineNo']
                    resRelationModel.ColOffset = currClass['ColOffset']
                    resRelationModel.FileID = currClass['FileID']
                    resRelationModel.Filename = currClass['Filename']
                    resRelationModel.RelationName = "class"

                    resModel.Relations.append(resRelationModel)

                    listResult.append(resModel)
            else:
                findFunctionInParentRecursive(graph=graph,currentClass=currClass,currentFunction=currentFunction)
    else:
        return None
    
    return listResult

def foundDuplicateInSearchResult(obj,listResult):
    if any(x.Result == obj.Result and x.Filename == obj.Filename and x.FileID == obj.FileID and x.LineNo == obj.LineNo and x.ColOffset == obj.ColOffset and x.HasRelation == obj.HasRelation for x in listResult):
        for item in listResult:
            if any(x.Result == y.Result and x.RelationName == y.RelationName and x.FileID == y.FileID and x.Filename == y.Filename and x.ColOffset == y.ColOffset and x.LineNo == y.LineNo for x in item.Relations for y in obj.Relations):
                return True

    return False