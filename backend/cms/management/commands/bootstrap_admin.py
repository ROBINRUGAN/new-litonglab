# designed by mew
"""Create the first manager without embedding a shared password in source code."""

import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "仅在没有管理员时创建初始账号；凭据写入数据目录下权限 600 的文件。"

    def handle(self, *args, **options):
        users = get_user_model()
        if users.objects.filter(is_superuser=True, is_active=True).exists():
            self.stdout.write("已有管理者，不再生成初始账号。")
            return
        username = "admin"
        if users.objects.filter(username=username).exists():
            username += "-" + secrets.token_hex(3)
        password = secrets.token_urlsafe(20)
        users.objects.create_superuser(username=username, password=password)
        origin = next(iter(settings.CSRF_TRUSTED_ORIGINS), "")
        admin_url = f"{origin.rstrip('/')}/admin/"
        path = settings.DATA_DIR / "initial-admin.txt"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(
                f"后台入口：{admin_url}\n用户名：{username}\n初始密码：{password}\n\n首次登录后请在管理界面的“修改密码”标签修改密码，然后删除本文件。\n"
            )
        self.stdout.write(f"管理员已创建。凭据保存在 {path}（未输出密码）。")
