import django_heroku
from api.models import ApiModel
from api.models.models import FileModel
from datetime import date, datetime
from os import path
from repopy.settings import ENVIRONMENT, GS_MEDIA_BUCKET_NAME, MEDIA_ROOT, REDISEARCH_INSTANCE, REDISGRAPH_INSTANCE, REPO_BASE_PATH, REPO_EXTRACTED_PATH, REPO_RAW_PATH, RESPONSE_ERROR, RESPONSE_SUCCESS, USE_GCP
from django import conf
from django.http import HttpResponse,JsonResponse
from django.conf import settings
from django.http.response import HttpResponseNotAllowed, HttpResponseServerError
from api.models.ApiModel import ResponseModel,RepositoryIndexRequestModel,ErrorModel
from api.models import Repositories
from django.conf import settings
from logic import parser
from logic import indexer as idx
import jsons
import logging
import traceback
from os.path import expanduser
from django.views.decorators.csrf import csrf_exempt
import zipfile
import magic
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import pathlib
import cloudpathlib
from transparentpath import TransparentPath

redisearch_instance = REDISEARCH_INSTANCE
redisgraph_instance = REDISGRAPH_INSTANCE
def indexRepoDirectory(request):
    if (request.method == "POST"):
        if(request.POST != None):
            req = jsons.loads(request.body,RepositoryIndexRequestModel)
            repoID = uuid.UUID(req.RepositoryID)
            repoModel = Repositories.objects.get(RepositoryID=repoID)
            if(repoModel != None):
                try:
                    parsedRepo = parser.parseCode(repoModel.RepositoryBaseDir,str(repoModel.RepositoryID))
                    indexedRepo = idx.indexRepo(parsedRepo,rediSearchConn=redisearch_instance,redisGraphConn=redisgraph_instance)
                    repoModel.LastIndexed = datetime.now()
                    repoModel.save()

                    reposModel = ApiModel.Repositories()

                    reposModel.RepositoryID = repoModel.RepositoryID
                    reposModel.RepositoryName = repoModel.RepositoryName
                    reposModel.ImportedDate = repoModel.ImportedDate
                    reposModel.LastIndexed = repoModel.LastIndexed

                    resp = ResponseModel()
                    resp.ResponseCode = RESPONSE_SUCCESS
                    resp.ResponseMessage = "success"
                    resp.ResponseObject = jsons.dump(reposModel)
                    retrmodel = jsons.dump(resp)
                    return JsonResponse(retrmodel,safe=False)
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
                    # return JsonResponse(retrmodelerr,safe=False)

    else:
        return HttpResponseNotAllowed("Not Allowed!")

def indexRepo(request):
    if (request.method == "POST"):
        if(request.POST != None):
            repoID = uuid.UUID(request.POST.get("RepositoryID"))
            repoModel = Repositories.objects.get(RepositoryID=repoID)
            if(repoModel != None):
                try:
                    parsedRepo = parser.parseCode(repoModel.RepositoryBaseDir,repoModel.RepositoryName)
                    # indexedRepo = idx.indexRepo(parsedRepo,redis)
                    retrmodel = jsons.dump(parsedRepo)
                    return JsonResponse(retrmodel,safe=False)
                except Exception as e:
                    errmsg = traceback.format_exc(limit=1)
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
                    # return JsonResponse(retrmodelerr,safe=False)

    else:
        return HttpResponseNotAllowed("Not Allowed!")

# @csrf_exempt
def repoUpload(request):
    print(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
    if (request.method == "POST"):
        if(request.FILES != None):
            userHome = expanduser("~")
            rawFileDestinationPath = path.join(MEDIA_ROOT, REPO_RAW_PATH,'')
            extractedDirectoryPath = path.join(MEDIA_ROOT, REPO_EXTRACTED_PATH)
            try:
                uploadedFile = request.FILES.get("RepoFile")
                filename = request.FILES.get("RepoFile").name
                filetypeFromName = filename.split('.')
                generatedName = str(uuid.uuid4())
                newFileName = generatedName +"."+ filetypeFromName[-1]
                pathSave = default_storage.save(rawFileDestinationPath+newFileName,uploadedFile)

                with default_storage.open(pathSave, 'wb+') as destination:
                     #move uploaded file to raw folder destination as chunk
                    for chunk in uploadedFile.chunks():
                        destination.write(chunk)
                
                # check if zip file
                fileType = magic.from_buffer(default_storage.open(rawFileDestinationPath + newFileName,"rb").read(2048))

                if ("zip" in fileType.lower()):             
                   
                    #unzip file to extracted path
                    with default_storage.open(pathSave, 'r') as raw_source:
                        with zipfile.ZipFile(raw_source) as zip_ref:
                            # zip_ref.extractall(raw_source)
                            for contentfilename in zip_ref.namelist():
                                contentfile = zip_ref.read(contentfilename)
                                with default_storage.open(path.join(extractedDirectoryPath,generatedName,contentfilename), 'wb+') as destination:
                                    destination.write(contentfile)

                    #insert repository to database
                    repository = Repositories()
                    repository.RepositoryName = request.POST.get("RepositoryName")
                    repository.RepositoryBaseDir = path.join(extractedDirectoryPath,generatedName,'')
                    repository.ImportedDate = datetime.now()
                    repository.RepositoryID = uuid.UUID(generatedName)
                    repository.save()

                    #insert file to database
                    if ENVIRONMENT == 'live' and USE_GCP:
                        TransparentPath.set_global_fs("gcs",bucket=GS_MEDIA_BUCKET_NAME)
                        # x = cloudpathlib.CloudPath("gs://"+GS_MEDIA_BUCKET_NAME+"/"+repository.RepositoryBaseDir)
                        TransparentPath()
                        y = TransparentPath.glob("**/*")
                        for pfile in y:
                            file = FileModel()
                            file.FileID = uuid.uuid4()
                            file.Filename = pfile.name
                            file.FilePath = pfile
                            file.IsDirectory = pfile.is_dir()
                            file.RepositoryID = repository.RepositoryID
                            file.DateAdded = datetime.now()
                            file.save()
                    else:
                        for pfile in pathlib.Path(repository.RepositoryBaseDir).glob('**/*'):
                            file = FileModel()
                            file.FileID = uuid.uuid4()
                            file.Filename = pfile.name
                            file.FilePath = pfile
                            file.IsDirectory = pfile.is_dir()
                            file.RepositoryID = repository.RepositoryID
                            file.DateAdded = datetime.now()
                            file.save()

                    response = ResponseModel()
                    response.ResponseCode = RESPONSE_SUCCESS
                    response.ResponseMessage = "OK"
                    response.ResponseObject = str(repository.RepositoryID)
                    retrmodel = jsons.dump(response)
                    return JsonResponse(retrmodel,safe=False)
                else:
                    default_storage.delete(rawFileDestinationPath+newFileName)
                    response = ResponseModel()
                    response.ResponseCode = RESPONSE_ERROR
                    response.ResponseMessage = "Filetype not allowed"
                    retrmodel = jsons.dump(response)
                    return JsonResponse(retrmodel,safe=False)
                

            except Exception as e:
                response = ResponseModel()
                response.ResponseCode = RESPONSE_ERROR
                response.ResponseMessage = "Upload error"
                errmsg = traceback.format_exc(limit=1)
                tb = traceback.format_tb(e.__traceback__)
                err = ErrorModel(msg=errmsg, trace=tb,module="Indexer")
                retrmodelerr = jsons.dumps(err)
                django_heroku.logging.error(retrmodelerr)
                retrmodel = jsons.dump(response)
                return JsonResponse(retrmodel,safe=False)

    else:
        return HttpResponseNotAllowed("Not Allowed!")

# def parseRepo(request):
