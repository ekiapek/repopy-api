from django.urls import path,include
from api.views import files, search, indexing, repository

urlpatterns = [
    path(r'search/SearchSuggest/', search.searchSuggest),
    # path(r'search/SelectRepository/', search.selectRepo),
    path(r'search/Search/', search.search),
    path(r'indexing/IndexRepoDirectory/', indexing.indexRepoDirectory),
    path(r'indexing/IndexRepo/', indexing.indexRepo),
    path(r'indexing/UploadRepository/', indexing.repoUpload),
    path(r'indexing/DeleteAllIndex/', indexing.deleteAllIndex),
    path(r'files/Get/', files.getFile),
    path(r'files/GetFilesInRepository/', files.getFilesInRepo),
    path(r'repository/GetLatestIndexedRepository/', repository.getLatestIndexedRepository),
    path(r'repository/GetRepository/<str:repositoryID>/', repository.getRepository)
    
]