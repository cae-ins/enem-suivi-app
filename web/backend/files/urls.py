from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ExecutionViewSet, StoredFileViewSet, health, module_catalog

router = DefaultRouter()
router.register("files", StoredFileViewSet, basename="files")
router.register("executions", ExecutionViewSet, basename="executions")
urlpatterns = [path("health/", health, name="health"), path("modules/", module_catalog, name="modules"),
               path("", include(router.urls))]
