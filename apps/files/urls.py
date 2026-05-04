from config.routers import IntegerPkRouter
from . import views

router = IntegerPkRouter()
router.register(r'categories', views.FileCategoryViewSet)
router.register(r'files', views.CompanyFileViewSet)

urlpatterns = router.urls
