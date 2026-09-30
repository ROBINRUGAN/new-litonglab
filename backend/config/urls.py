# designed by mew
from cms import editor_api, history_api, manage_api, views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path

urlpatterns = [
    path("api/editor/session/", editor_api.session),
    path("api/editor/login/", editor_api.sign_in),
    path("api/editor/logout/", editor_api.sign_out),
    path("api/editor/changes/", editor_api.save_changes),
    path("api/editor/items/<str:kind>/<str:key>/action/", editor_api.item_action),
    path("api/editor/items/<str:kind>/<str:key>/history/", editor_api.history),
    path("api/manage/password/", manage_api.password),
    path("api/manage/users/", manage_api.users),
    path("api/manage/users/<int:user_id>/", manage_api.user_detail),
    path("api/manage/history/", history_api.history),
    path("api/manage/backups/", manage_api.backups),
    path("api/manage/backups/download/", manage_api.download),
    path("api/manage/restore/", manage_api.restore),
    path("api/site/", views.site_data),
    path("api/media/", views.media_list),
    path("api/media/upload/", views.media_upload),
    path("api/media/<int:asset_id>/", views.media_detail),
    path("api/health/", views.health),
    path("admin/", views.frontend),
    re_path(r"^admin/(?P<path>.*)$", views.frontend),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [re_path(r"^(?!api/|admin/|media/|static/)(?P<path>.*)$", views.frontend)]
