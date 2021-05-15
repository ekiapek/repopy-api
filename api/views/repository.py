import re
import traceback

import django_heroku
from api.models import Repositories, ApiModel
from django.http import HttpResponse,JsonResponse, response
import jsons
from repopy.settings import NO_REPOSITORY_FOUND, RESPONSE_ERROR,RESPONSE_SUCCESS

def getLatestIndexedRepository(request):
    # repositoryID = request.GET["RepositoryID"]
    try:
        repository = Repositories.objects.exclude(LastIndexed=None).order_by('-LastIndexed').first()
        if(repository != None):
            repoModel = ApiModel.Repositories()

            repoModel.RepositoryID = repository.RepositoryID
            repoModel.RepositoryName = repository.RepositoryName
            repoModel.ImportedDate = repository.ImportedDate
            repoModel.LastIndexed = repository.LastIndexed

            responseModel = ApiModel.ResponseModel()
            responseModel.ResponseCode = RESPONSE_SUCCESS
            responseModel.ResponseMessage = "OK"
            responseModel.ResponseObject = jsons.dump(repoModel,cls=ApiModel.Repositories, strict=False)
            retrmodel = jsons.dump(responseModel)
            return JsonResponse(retrmodel,safe=False)
        else:
            responseModel = ApiModel.ResponseModel()
            responseModel.ResponseCode = NO_REPOSITORY_FOUND
            responseModel.ResponseMessage = "Repository Not Found"
            retrmodel = jsons.dump(responseModel)
            return JsonResponse(retrmodel,safe=False)
    except Exception as e:
        errmsg = traceback.format_exc(limit=1)
        tb = traceback.format_tb(e.__traceback__)
        err = ApiModel.ErrorModel(msg=errmsg, trace=tb,module="Indexer")
        retrmodelerr = jsons.dumps(err)
        # django_heroku.logging.error(retrmodelerr)
        print(retrmodelerr)
        responseModel = ApiModel.ResponseModel()
        responseModel.ResponseCode = RESPONSE_ERROR
        responseModel.ResponseMessage = "Error getting repository"
        retrmodel = jsons.dump(responseModel)
        return JsonResponse(retrmodel,safe=False)

def getRepository(request,repositoryID):
    try:
        repository = Repositories.objects.get(RepositoryID = repositoryID)
        if(repository != None):
            repoModel = ApiModel.Repositories()

            repoModel.RepositoryID = repository.RepositoryID
            repoModel.RepositoryName = repository.RepositoryName
            repoModel.ImportedDate = repository.ImportedDate
            repoModel.LastIndexed = repository.LastIndexed
            retrmodel = jsons.dump(repoModel)
            return JsonResponse(retrmodel,safe=False)
    except Exception as e:
        responseModel = ApiModel.ResponseModel()
        responseModel.ResponseCode = RESPONSE_ERROR
        responseModel.ResponseMessage = "Error getting repository"
        retrmodel = jsons.dump(responseModel)
        # django_heroku.logging.error(retrmodelerr)
        print(retrmodel)
        return response.HttpResponseServerError()