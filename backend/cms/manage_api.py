# designed by mew
"""Account and website maintenance behind the same authenticated Vue interface."""

import json
import re
import secrets
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .editor_api import body, editor_endpoint
from .models import KINDS, Revision
from .website_backups import (
    MAX_UPLOAD_BYTES,
    SCOPE,
    create_backup,
    fingerprint,
    restore_snapshot,
    safe_directory,
    validate_archive,
)


def manager_only(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def form_errors(form):
    return [str(error) for errors in form.errors.values() for error in errors]


@require_POST
@editor_endpoint
def password(request):
    data = body(request)
    form = PasswordChangeForm(
        request.user,
        {
            "old_password": data.get("oldPassword"),
            "new_password1": data.get("newPassword"),
            "new_password2": data.get("confirmPassword"),
        },
    )
    if not form.is_valid():
        raise ValidationError(form_errors(form))
    user = form.save()
    update_session_auth_hash(request, user)
    return JsonResponse(
        {"message": "密码已修改，当前登录保持有效。", "csrfToken": get_token(request)}
    )


def user_data(user, current_user=None):
    return {
        "id": user.pk,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "manager": user.is_superuser,
        "active": user.is_active,
        "created": user.date_joined.isoformat(),
        "current": current_user is not None and user.pk == current_user.pk,
    }


@require_http_methods(["GET", "POST"])
@editor_endpoint
def users(request):
    manager_only(request)
    if request.method == "GET":
        return JsonResponse(
            {
                "users": [
                    user_data(user, request.user)
                    for user in get_user_model()
                    .objects.filter(is_staff=True)
                    .order_by("date_joined")
                ],
                "canCreate": True,
            }
        )
    data = body(request)
    if type(data.get("manager", False)) is not bool:
        raise ValidationError("请选择有效的账号角色。")
    name = data.get("name", "")
    if not isinstance(name, str) or len(name) > 150:
        raise ValidationError("姓名不能超过 150 个字符。")
    form = UserCreationForm(
        {
            "username": data.get("username"),
            "password1": data.get("password"),
            "password2": data.get("confirmPassword"),
        }
    )
    if not form.is_valid():
        raise ValidationError(form_errors(form))
    try:
        with transaction.atomic():
            user = form.save(commit=False)
            user.first_name = name.strip()
            user.is_staff = True
            user.is_superuser = data.get("manager", False)
            user.save()
            ensure_editor_permissions(user)
    except IntegrityError as error:
        raise ValidationError("该用户名已被使用，请换一个用户名。") from error
    return JsonResponse(
        {
            "user": user_data(user, request.user),
            "message": "账号已创建，可直接登录并编辑、发布内容。",
        },
        status=201,
    )


def ensure_editor_permissions(user):
    if user.is_superuser:
        return
    group, _ = Group.objects.get_or_create(name="编辑人员")
    codes = [f"{action}_{kind}" for kind, _ in KINDS for action in ("add", "change", "view")]
    codes += ["add_mediaasset", "change_mediaasset", "view_mediaasset", "publish_content"]
    group.permissions.add(
        *Permission.objects.filter(content_type__app_label="cms", codename__in=codes)
    )
    user.groups.add(group)


def preserve_actor_names(user):
    # Keep the historical name before changing or removing an account. New
    # revisions already record it when the editorial action happens.
    for revision in Revision.objects.filter(actor=user).iterator():
        if not revision.snapshot.get("actorName"):
            revision.snapshot["actorName"] = user.get_full_name() or user.username
            revision.save(update_fields=["snapshot"])


@require_http_methods(["PATCH", "POST", "DELETE"])
@editor_endpoint
def user_detail(request, user_id):
    manager_only(request)
    data = {} if request.method == "DELETE" else body(request)
    try:
        with transaction.atomic():
            user = (
                get_user_model()
                .objects.select_for_update()
                .filter(pk=user_id, is_staff=True)
                .first()
            )
            if user is None:
                return JsonResponse({"errors": ["账号不存在，请刷新列表。"]}, status=404)
            current = user.pk == request.user.pk
            manager = data.get("manager", user.is_superuser)
            active = data.get("active", user.is_active)
            if type(manager) is not bool or type(active) is not bool:
                raise ValidationError("账号角色和启用状态无效。")
            deleting = request.method == "DELETE"
            if current and (deleting or not manager or not active):
                raise ValidationError("不能删除、停用或降低当前登录账号的管理员角色。")
            if user.is_superuser and user.is_active and (deleting or not manager or not active):
                if (
                    not get_user_model()
                    .objects.filter(is_superuser=True, is_active=True, is_staff=True)
                    .exclude(pk=user.pk)
                    .exists()
                ):
                    raise ValidationError("必须保留至少一个启用的管理员账号。")
            preserve_actor_names(user)
            if deleting:
                user.delete()
                return JsonResponse({"message": "账号已删除，网站内容和编辑记录均已保留。"})
            if "username" in data:
                if not isinstance(data["username"], str):
                    raise ValidationError("用户名格式无效。")
                user.username = data["username"].strip()
            if "name" in data:
                if not isinstance(data["name"], str) or len(data["name"]) > 150:
                    raise ValidationError("姓名不能超过 150 个字符。")
                user.first_name = data["name"].strip()
                user.last_name = ""
            user.is_superuser = manager
            user.is_active = active
            new_password = data.get("newPassword")
            if new_password:
                if not isinstance(new_password, str) or new_password != data.get("confirmPassword"):
                    raise ValidationError("两次输入的新密码不一致。")
                validate_password(new_password, user)
                user.set_password(new_password)
            elif data.get("confirmPassword"):
                raise ValidationError("请输入新密码。")
            user.full_clean()
            user.save()
            ensure_editor_permissions(user)
        if current and new_password:
            update_session_auth_hash(request, user)
    except IntegrityError as error:
        raise ValidationError("该用户名已被使用，请换一个用户名。") from error
    return JsonResponse(
        {
            "user": user_data(user, request.user),
            "message": "账号信息已更新。",
            "csrfToken": get_token(request),
        }
    )


def backups_directory():
    return safe_directory(Path(settings.DATA_DIR) / "backups" / "web")


@require_GET
@editor_endpoint
def backups(request):
    files = []
    if request.user.is_superuser:
        for path in sorted(backups_directory().glob("website-*.zip"), reverse=True)[:20]:
            files.append(
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "url": "/api/manage/backups/download/?name=" + path.name,
                }
            )
    return JsonResponse(
        {
            "scope": SCOPE,
            "maxUploadBytes": MAX_UPLOAD_BYTES,
            "canBackup": request.user.is_superuser,
            "canRestore": request.user.is_superuser,
            "files": files,
        }
    )


@require_GET
@editor_endpoint
def download(request):
    manager_only(request)
    name = request.GET.get("name")
    if name:
        if not re.fullmatch(r"website-\d{8}T\d{12}Z\.zip", name):
            raise ValidationError("备份名称无效。")
        path = backups_directory() / name
        if not path.is_file() or path.is_symlink():
            raise ValidationError("备份文件不存在。")
    else:
        path = create_backup(backups_directory())
    return FileResponse(
        path.open("rb"), as_attachment=True, filename=path.name, content_type="application/zip"
    )


def pending_directory():
    return safe_directory(Path(settings.DATA_DIR) / "restore-previews")


@require_POST
@editor_endpoint
def restore(request):
    manager_only(request)
    if request.content_type == "application/json":
        data = body(request)
        token = data.get("token")
        if (
            data.get("confirm") is not True
            or not isinstance(token, str)
            or not re.fullmatch(r"[a-f0-9]{48}", token)
            or request.session.get("restore_token") != token
        ):
            raise ValidationError("请先上传备份、检查预览，并明确确认还原。")
        directory = pending_directory() / token
        meta_file = directory / "preview.json"
        if not meta_file.is_file():
            raise ValidationError("备份预览已失效，请重新上传。")
        meta = json.loads(meta_file.read_text())
        if meta["user"] != request.user.pk or meta["expires"] < timezone.now().timestamp():
            shutil.rmtree(directory, ignore_errors=True)
            raise ValidationError("备份预览已过期，请重新上传。")
        if fingerprint() != meta["fingerprint"]:
            from .editor_api import EditConflict

            raise EditConflict("预览后网站已被修改，请重新上传备份并确认，避免覆盖最新修改。")
        safety = create_backup(backups_directory())
        restore_snapshot(directory, request.user, meta["fingerprint"])
        request.session.pop("restore_token", None)
        shutil.rmtree(directory, ignore_errors=True)
        return JsonResponse(
            {
                "message": "网站内容和素材已还原，账号与当前登录保持不变。",
                "scope": SCOPE,
                "safetyBackup": "/api/manage/backups/download/?name=" + safety.name,
            }
        )
    upload = request.FILES.get("file")
    if upload is None or upload.size > MAX_UPLOAD_BYTES or not upload.name.lower().endswith(".zip"):
        raise ValidationError("请选择不超过 512 MiB 的网站备份 ZIP。")
    root = pending_directory()
    # Expired previews are private temporary files, never persistent site data.
    for old in root.iterdir():
        if (
            old.is_dir()
            and re.fullmatch(r"[a-f0-9]{48}", old.name)
            and old.stat().st_mtime < (timezone.now() - timedelta(hours=1)).timestamp()
        ):
            shutil.rmtree(old, ignore_errors=True)
    previous = request.session.pop("restore_token", None)
    if isinstance(previous, str) and re.fullmatch(r"[a-f0-9]{48}", previous):
        shutil.rmtree(root / previous, ignore_errors=True)
    token = secrets.token_hex(24)
    directory = root / token
    directory.mkdir(mode=0o700)
    archive = directory / "upload.zip"
    try:
        with archive.open("wb") as output:
            for chunk in upload.chunks():
                output.write(chunk)
        summary = validate_archive(archive, directory)
        archive.unlink()
        expires = timezone.now() + timedelta(minutes=30)
        (directory / "preview.json").write_text(
            json.dumps(
                {
                    "user": request.user.pk,
                    "fingerprint": fingerprint(),
                    "expires": expires.timestamp(),
                }
            )
        )
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    request.session["restore_token"] = token
    return JsonResponse(
        {"token": token, "summary": summary, "scope": SCOPE, "expiresAt": expires.isoformat()}
    )
