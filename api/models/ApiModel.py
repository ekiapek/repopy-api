from datetime import datetime
import pytz
from django import forms

class ResponseModel():
    def __init__(self):
        self.ResponseCode = None
        self.ResponseMessage = None
        self.ResponseObject = None

class SearchModel():
    def __init__(self,query,repoID):
        self.query = query
        self.repoID = repoID

class RepositoryIndexRequestModel(object):
    def __init__(self):
        self.RepositoryID = None

class ErrorModel:
    def __init__(self,msg = None, trace = None, module = None):
        self.ErrMsg = msg
        self.Trace = trace
        self.Module = module
        self.Created = datetime.now(tz=pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d %H:%M:%S")

class Repositories():
    def __init__(self):
        self.RepositoryID = None
        self.RepositoryName = None
        self.ImportedDate = None
        self.LastIndexed = None

class FileNodeModel():
    def __init__(self):
        self.id = None
        self.parent = None
        self.text = None
        # self.state = {
        #     'opened':'false',
        #     'disable':'false',
        #     'selected':'false'
        # }
        self.icon = None
        self.li_attr = []
        self.a_attr = []

class SearchResultModel():
    def __init__(self):
        self.Result = None
        self.LineNo = None
        self.ColOffset = None
        self.Filename = None
        self.FileID = None
        self.HasRelation = False
        self.Query = None
        self.Relations = []

class SearchResultRelationModel():
    def __init__(self) -> None:
        self.RelationName = None
        self.Result = None
        self.LineNo = None
        self.ColOffset = None
        self.Filename = None
        self.FileID = None