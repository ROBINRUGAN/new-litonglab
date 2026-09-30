#!/usr/bin/env bash
# designed by mew
# Install or update a release on Linux with systemd. Run with sudo.
set -Eeuo pipefail
umask 022

APP_ROOT=/srv/litonglab
DATA_ROOT=/var/lib/litonglab
ENV_FILE=/etc/litonglab.env
NGINX_FILE=/etc/nginx/sites-available/litonglab
OLD_RELEASE=
OLD_RUNNING=0
SWITCHED=0
STOPPED_BY_INSTALLER=0
ROLLBACK_SAFE=1
STAGING=
NGINX_BACKUP=
NGINX_CREATED=0
PYTHON_BIN=python3
SQLITE_WORK=

fail() { printf '错误：%s\n' "$*" >&2; return 1; }
log() { printf '\n%s\n' "$*"; }

validate_arguments() {
    [[ $# == 3 ]] || fail '用法：sudo bash install.sh 部署包.tar.gz 官网域名 证书联系邮箱'
    ARCHIVE=$1
    DOMAIN=$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')
    EMAIL=$3
    [[ -f "$ARCHIVE" ]] || fail "部署包不存在：$ARCHIVE"
    [[ ${#DOMAIN} -le 253 && "$DOMAIN" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && "$DOMAIN" == *.* ]] || fail '域名应为完整域名，不含协议、端口或路径。'
    local label
    local -a labels
    IFS=. read -r -a labels <<< "$DOMAIN"
    for label in "${labels[@]}"; do
        [[ ${#label} -le 63 && "$label" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || fail '域名格式无效。'
    done
    if [[ -n "$EMAIL" ]]; then
        [[ "$EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || fail '请填写有效的证书联系邮箱。'
    fi
}

validate_archive() {
    "$PYTHON_BIN" - "$ARCHIVE" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
required = {
    'backend/manage.py', 'backend/requirements.txt', 'frontend/dist/index.html',
    'content/seed/site.json', 'deploy/manage.sh', 'deploy/nginx.conf',
    'deploy/litonglab.service', 'deploy/litonglab-backup.service',
    'deploy/litonglab-backup.timer', 'scripts/restore_backup.py', 'deploy/https.sh',
}
seen = set()
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for item in archive:
        path = PurePosixPath(item.name)
        if path.is_absolute() or '..' in path.parts or '\\' in item.name:
            raise SystemExit('部署包包含非法路径。')
        if not (item.isfile() or item.isdir()) or item.name in seen:
            raise SystemExit('部署包包含链接、特殊文件或重复路径。')
        if path.parts[0] not in {'backend', 'frontend', 'content', 'deploy', 'scripts', 'docs'}:
            raise SystemExit('部署包包含意外的顶层路径。')
        seen.add(item.name)
if not required <= seen:
    raise SystemExit('部署包不完整，缺少：' + ', '.join(sorted(required - seen)))
PY
}

check_nginx_ownership() {
    "$PYTHON_BIN" - "$DOMAIN_LIST" "$NGINX_FILE" <<'PY'
import pathlib, re, subprocess, sys
wanted, target = set(sys.argv[1].split(',')), pathlib.Path(sys.argv[2]).resolve()
def names(text):
    text = re.sub(r'#[^\n]*', '', text)
    return [name for line in re.findall(r'\bserver_name\s+([^;]+);', text) for name in line.split()]
if target.exists():
    existing = names(target.read_text())
    if not existing or any(name not in wanted for name in existing):
        raise SystemExit('已有 litonglab Nginx 配置属于其他域名；请先核对配置，不会自动覆盖。')
result = subprocess.run(['nginx', '-T'], text=True, capture_output=True)
if result.returncode:
    raise SystemExit('已有 Nginx 配置未通过检查，请先运行 nginx -t 修复。')
parts = re.split(r'^# configuration file (.+):\s*$', result.stdout, flags=re.M)
for index in range(1, len(parts), 2):
    if wanted.intersection(names(parts[index + 1])) and pathlib.Path(parts[index]).resolve() != target:
        raise SystemExit('此域名已由其他 Nginx 配置提供服务，不会接管或覆盖：' + parts[index])
PY
}

on_error() {
    local code=$?
    trap - ERR
    set +e
    [[ -z "$STAGING" ]] || rm -rf -- "$STAGING"
    [[ -z "$SQLITE_WORK" ]] || rm -rf -- "$SQLITE_WORK"
    if [[ -n "$NGINX_BACKUP" && -f "$NGINX_BACKUP" ]]; then
        mv -f "$NGINX_BACKUP" "$NGINX_FILE"
    elif [[ "$NGINX_CREATED" == 1 ]]; then
        rm -f "$NGINX_FILE"
    fi
    if [[ ( "$SWITCHED" == 1 || "$STOPPED_BY_INSTALLER" == 1 ) && "$ROLLBACK_SAFE" == 1 && -n "$OLD_RELEASE" ]]; then
        systemctl stop litonglab
        ln -sfn "$OLD_RELEASE" "$APP_ROOT/current.next"
        mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
        [[ "$OLD_RUNNING" == 0 ]] || systemctl restart litonglab
        printf '\n部署失败，程序入口已恢复到上一版本。\n' >&2
    elif [[ "$ROLLBACK_SAFE" == 0 ]]; then
        systemctl stop litonglab
        printf '\n部署失败，数据库迁移已开始，服务保持停止。请先核查日志；完整备份位于 %s/backups/，不要直接切回旧代码。\n' "$DATA_ROOT" >&2
    else
        printf '\n部署未完成。修复上述错误后，可重复执行同一命令继续。\n' >&2
    fi
    exit "$code"
}


read_configuration() {
    local requested_port=${LAB_BACKEND_PORT-} requested_aliases=${LAB_DOMAIN_ALIASES-}
    local aliases_set=${LAB_DOMAIN_ALIASES+x} requested_ip=${LAB_PUBLIC_IP-}
    local requested_cert=${LAB_SSL_CERT_FILE-} requested_key=${LAB_SSL_KEY_FILE-}
    if [[ -f "$ENV_FILE" ]]; then
        [[ ! -L "$ENV_FILE" ]] || fail '生产环境文件不能是符号链接。'
        [[ $(stat -c %u "$ENV_FILE") == 0 ]] || fail '生产环境文件必须由 root 拥有。'
        [[ $((8#$(stat -c %a "$ENV_FILE") & 022)) == 0 ]] || fail '生产环境文件不能允许其他用户写入。'
        # shellcheck disable=SC1090
        . "$ENV_FILE"
    fi
    LAB_BACKEND_PORT=${requested_port:-${LAB_BACKEND_PORT:-8000}}
    [[ "$aliases_set" != x ]] || LAB_DOMAIN_ALIASES=$requested_aliases
    LAB_DOMAIN_ALIASES=${LAB_DOMAIN_ALIASES:-}
    LAB_PUBLIC_IP=${requested_ip:-${LAB_PUBLIC_IP:-}}
    LAB_SSL_CERT_FILE=${requested_cert:-${LAB_SSL_CERT_FILE:-}}
    LAB_SSL_KEY_FILE=${requested_key:-${LAB_SSL_KEY_FILE:-}}
    validate_ssl_paths
    [[ "$LAB_BACKEND_PORT" =~ ^[1-9][0-9]{0,4}$ && "$LAB_BACKEND_PORT" -le 65535 ]] || fail '后台端口必须在 1–65535 之间。'
}

select_runtime() {
    local candidate
    PYTHON_BIN=
    for candidate in "${LAB_PYTHON:-}" python3 python3.12 python3.11 python3.10 /www/server/pyporject_evn/versions/*/bin/python3; do
        [[ -n "$candidate" ]] || continue
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys, venv; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
            PYTHON_BIN=$(command -v "$candidate")
            break
        fi
    done
    [[ -n "$PYTHON_BIN" ]] || fail '需要可用的 Python 3.10+；可用 LAB_PYTHON 指定现有解释器。'
    if [[ -d /www/server/panel/vhost/nginx ]]; then
        NGINX_FILE=${LAB_NGINX_FILE:-/www/server/panel/vhost/nginx/litonglab.conf}
    else
        NGINX_FILE=${LAB_NGINX_FILE:-/etc/nginx/sites-available/litonglab}
    fi
    [[ "$NGINX_FILE" =~ ^/[a-zA-Z0-9/_.-]+$ ]] || fail 'Nginx 配置路径无效。'
    WEB_GROUP=$(nginx -T 2>/dev/null | awk '/^user[[:space:]]/ && !found {gsub(/;/,"",$0); print ($3 ? $3 : $2); found=1}')
    WEB_GROUP=${WEB_GROUP:-www-data}
    getent group "$WEB_GROUP" >/dev/null || fail '没有找到 Nginx 的运行用户组。'
}

validate_domains() {
    DOMAIN_LIST="$DOMAIN${LAB_DOMAIN_ALIASES:+,$LAB_DOMAIN_ALIASES}"
    "$PYTHON_BIN" - "$DOMAIN_LIST" "$LAB_PUBLIC_IP" <<'PY'
import ipaddress, re, sys
for domain in sys.argv[1].split(','):
    if len(domain) > 253 or '.' not in domain or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in domain.split('.')):
        raise SystemExit('域名格式无效：' + domain)
if sys.argv[2]:
    ipaddress.ip_address(sys.argv[2])
PY
}

validate_ssl_paths() {
    if [[ -n ${LAB_SSL_CERT_FILE:-} || -n ${LAB_SSL_KEY_FILE:-} ]]; then
        [[ -n ${LAB_SSL_CERT_FILE:-} && -n ${LAB_SSL_KEY_FILE:-} ]] || fail '证书和私钥路径必须同时填写。'
        local path
        for path in "$LAB_SSL_CERT_FILE" "$LAB_SSL_KEY_FILE"; do
            [[ "$path" =~ ^/[a-zA-Z0-9/_.-]+$ ]] || fail '证书路径必须为绝对路径，不能包含空格或配置指令。'
        done
    fi
}

render_nginx() {
    validate_ssl_paths
    "$PYTHON_BIN" - "$NGINX_FILE" "$DOMAIN_LIST" "$LAB_BACKEND_PORT" "$DOMAIN" "$1" "${LAB_SSL_CERT_FILE:-}" "${LAB_SSL_KEY_FILE:-}" <<'PY'
import os, pathlib, re, shutil, subprocess, sys, tempfile
target, names, port, primary, tls, certificate, private_key = sys.argv[1:]
certificate = certificate or '/etc/letsencrypt/live/' + primary + '/fullchain.pem'
private_key = private_key or '/etc/letsencrypt/live/' + primary + '/privkey.pem'
target = pathlib.Path(target)
names = names.replace(',', ' ')
text = pathlib.Path('deploy/nginx.conf').read_text().replace('lab.example.edu', names).replace('127.0.0.1:8000', '127.0.0.1:' + port)
if tls == '1':
    listeners = ['listen 443 ssl;']
    ssl = [
        'ssl_certificate ' + certificate + ';',
        'ssl_certificate_key ' + private_key + ';',
        'ssl_protocols TLSv1.2 TLSv1.3;',
    ]
    nginx = shutil.which('nginx')
    build = subprocess.run([nginx, '-V'], text=True, capture_output=True) if nginx else None
    features = (build.stdout + build.stderr) if build and build.returncode == 0 else ''
    version = re.search(r'nginx/(\d+)\.(\d+)\.(\d+)', features)
    if '--with-http_v2_module' in features:
        if version and tuple(map(int, version.groups())) >= (1, 25, 1):
            listeners.append('http2 on;')
        else:
            listeners[0] = 'listen 443 ssl http2;'
    if '--with-http_v3_module' in features:
        listeners.append('listen 443 quic;')
        header = "add_header Alt-Svc 'h3=\":443\"; ma=86400' always;"
        ssl.append(header)
        text = text.replace(
            'add_header Cache-Control "no-cache";',
            'add_header Cache-Control "no-cache";\n        ' + header,
        )
    text = text.replace('listen 80;', '\n    '.join(listeners), 1)
    text = text.replace('#SSL-END', '\n    '.join(ssl) + '\n    #SSL-END', 1)
    text += '\nserver {\n    listen 80;\n    server_name ' + names + ';\n    location ^~ /.well-known/acme-challenge/ { root /var/lib/litonglab/acme; }\n    location / { return 308 https://$host$request_uri; }\n}\n'
target.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile('w', dir=target.parent, delete=False) as output:
    output.write(text)
    temporary = pathlib.Path(output.name)
temporary.chmod(0o644)
os.replace(temporary, target)
PY
}

apply_nginx() {
    if [[ -f "$NGINX_FILE" ]]; then
        NGINX_BACKUP=$(mktemp "${NGINX_FILE}.previous-XXXXXX")
        cp -p "$NGINX_FILE" "$NGINX_BACKUP"
    else
        NGINX_CREATED=1
    fi
    render_nginx "$1"
    nginx -t
    if systemctl is-active --quiet nginx; then nginx -s reload; else systemctl start nginx; fi
    [[ -z "$NGINX_BACKUP" ]] || rm -f "$NGINX_BACKUP"
    NGINX_BACKUP=
    NGINX_CREATED=0
}


prepare_sqlite() {
    SQLITE_LIB=
    if "$PYTHON_BIN" -c 'import sqlite3; assert sqlite3.sqlite_version_info >= (3, 31, 0)' >/dev/null 2>&1; then return; fi
    SQLITE_LIB="$APP_ROOT/tools/sqlite/lib"
    if ! LD_LIBRARY_PATH="$SQLITE_LIB" "$PYTHON_BIN" -c 'import sqlite3; assert sqlite3.sqlite_version_info >= (3, 31, 0)' >/dev/null 2>&1; then
        command -v gcc >/dev/null && command -v make >/dev/null || fail '构建独立 SQLite 需要 gcc 和 make。'
        SQLITE_WORK=$(mktemp -d)
        if [[ -n ${LAB_SQLITE_ARCHIVE:-} && -f "$LAB_SQLITE_ARCHIVE" ]]; then
            cp "$LAB_SQLITE_ARCHIVE" "$SQLITE_WORK/source.tar.gz"
        else
            curl --fail --location --retry 2 --max-time 900 -o "$SQLITE_WORK/source.tar.gz" https://www.sqlite.org/2026/sqlite-autoconf-3530400.tar.gz
        fi
        "$PYTHON_BIN" - "$SQLITE_WORK/source.tar.gz" <<'PY'
import hashlib, pathlib, sys
expected = '454e45f61c6bd75b7420e7190732dea03ce6639c63ada47bbc592f67fc340338'
if hashlib.sha3_256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() != expected:
    raise SystemExit('SQLite 下载校验失败。')
PY
        tar -xzf "$SQLITE_WORK/source.tar.gz" -C "$SQLITE_WORK"
        (cd "$SQLITE_WORK/sqlite-autoconf-3530400" && ./configure --prefix="$APP_ROOT/tools/sqlite" --disable-static --disable-readline && make -j2 && make install)
        rm -rf "$SQLITE_WORK"
        SQLITE_WORK=
    fi
    LD_LIBRARY_PATH="$SQLITE_LIB" "$PYTHON_BIN" -c 'import sqlite3; assert sqlite3.sqlite_version_info >= (3, 31, 0)'
}

prepare_certbot() {
    if command -v certbot >/dev/null 2>&1; then
        CERTBOT_BIN=$(command -v certbot)
    else
        CERTBOT_BIN="$APP_ROOT/tools/certbot/bin/certbot"
        if [[ ! -x "$CERTBOT_BIN" ]]; then
            "$PYTHON_BIN" -m venv "$APP_ROOT/tools/certbot"
            "$APP_ROOT/tools/certbot/bin/python" -m pip install 'certbot==5.8.0'
        fi
    fi
    install -d -m 755 "$DATA_ROOT/acme" /etc/letsencrypt /var/lib/letsencrypt /var/log/letsencrypt
}

write_runtime_units() {
    local unit temporary
    for unit in litonglab.service litonglab-backup.service litonglab-backup.timer; do
        temporary=$(mktemp)
        sed -e "s/Group=www-data/Group=$WEB_GROUP/g" -e "s/127.0.0.1:8000/127.0.0.1:$LAB_BACKEND_PORT/g" "deploy/$unit" > "$temporary"
        if ! cmp -s "$temporary" "/etc/systemd/system/$unit"; then install -m 644 "$temporary" "/etc/systemd/system/$unit"; fi
        rm -f "$temporary"
    done
    systemctl daemon-reload
    systemctl enable litonglab litonglab-backup.timer
    systemctl restart litonglab
    systemctl start litonglab-backup.timer
}

main() {
    [[ $EUID == 0 ]] || fail '请通过 sudo 或 root 执行。'
    [[ -d /run/systemd/system ]] || fail '服务器需要使用 systemd。'
    # shellcheck disable=SC1091
    . /etc/os-release
    read_configuration
    validate_arguments "$@"
    exec 9>/run/lock/litonglab-deploy.lock
    flock -n 9 || fail '另一个部署正在执行，请稍后重试。'
    trap on_error ERR
    if command -v apt-get >/dev/null 2>&1; then
        local -a missing=()
        local package
        for package in python3 python3-venv nginx curl iproute2; do
            if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]]; then missing+=("$package"); fi
        done
        if [[ ${#missing[@]} -gt 0 ]]; then apt-get update; apt-get install -y "${missing[@]}"; fi
    fi
    command -v nginx >/dev/null || fail '请先安装 Nginx。'
    select_runtime
    validate_domains
    ARCHIVE=$(readlink -f "$ARCHIVE")
    validate_archive
    check_nginx_ownership
    [[ ! -e "$APP_ROOT/current" || -L "$APP_ROOT/current" ]] || fail 'current 必须是版本目录的符号链接。'
    if [[ -L "$APP_ROOT/current" ]]; then
        OLD_RELEASE=$(readlink -f "$APP_ROOT/current")
        [[ -d "$OLD_RELEASE" ]] || fail 'current 指向的版本目录不存在，请先核对。'
    fi
    if systemctl is-active --quiet litonglab; then
        OLD_RUNNING=1
    elif [[ -n $(ss -H -ltn "sport = :$LAB_BACKEND_PORT") ]]; then
        fail "端口 $LAB_BACKEND_PORT 已被其他服务使用；可用 LAB_BACKEND_PORT 指定其他端口。"
    fi
    id litonglab >/dev/null 2>&1 || useradd --system --home "$DATA_ROOT" --shell /usr/sbin/nologin --gid "$WEB_GROUP" litonglab
    [[ $(id -gn litonglab) == "$WEB_GROUP" ]] || fail "litonglab 用户的主组必须为 $WEB_GROUP。"
    [[ -d "$APP_ROOT/releases" ]] || install -d -m 755 "$APP_ROOT/releases"
    if [[ ! -d "$DATA_ROOT" ]]; then
        install -d -o litonglab -g "$WEB_GROUP" -m 750 "$DATA_ROOT"
    fi
    runuser -u litonglab -- test -w "$DATA_ROOT" || fail 'litonglab 用户不能写入数据目录。'

    local sha release requirements_sha venv_changed=0
    sha=$(sha256sum "$ARCHIVE" | awk '{print $1}')
    release="$APP_ROOT/releases/${sha:0:16}"
    log '准备程序版本和独立 Python 环境……'
    if [[ -f "$release/.package-sha256" ]]; then
        [[ $(cat "$release/.package-sha256") == "$sha" ]] || fail '版本标识冲突，未覆盖现有目录。'
    else
        [[ ! -e "$release" ]] || fail '版本目录已存在但没有校验标记，请先检查。'
        STAGING=$(mktemp -d "$APP_ROOT/releases/.prepare-XXXXXX")
        tar --no-same-owner --no-same-permissions -xzf "$ARCHIVE" -C "$STAGING"
        printf '%s\n' "$sha" > "$STAGING/.package-sha256"
        chmod 755 "$STAGING"
        mv "$STAGING" "$release"
        STAGING=
    fi
    if [[ ! -x "$release/.venv/bin/python" ]] || ! "$release/.venv/bin/python" -m pip --version >/dev/null 2>&1; then
        "$PYTHON_BIN" -m venv "$release/.venv"
        venv_changed=1
    fi
    requirements_sha=$(sha256sum "$release/backend/requirements.txt" | awk '{print $1}')
    if [[ "$venv_changed" == 1 || $(cat "$release/.requirements-sha256" 2>/dev/null || true) != "$requirements_sha" ]]; then
        "$release/.venv/bin/python" -m pip install -r "$release/backend/requirements.txt"
        printf '%s\n' "$requirements_sha" > "$release/.requirements-sha256"
    fi

    prepare_sqlite
    local env_changed
    env_changed=$("$PYTHON_BIN" - "$ENV_FILE" "$DOMAIN" "$DATA_ROOT" "$LAB_DOMAIN_ALIASES" "$LAB_BACKEND_PORT" "$NGINX_FILE" "$LAB_PUBLIC_IP" "$SQLITE_LIB" "$LAB_SSL_CERT_FILE" "$LAB_SSL_KEY_FILE" <<'PY'
import os, pathlib, secrets, sys, tempfile
path, domain, data = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
original = path.read_text() if path.exists() else ''
lines = original.splitlines()
values = dict(line.split('=', 1) for line in lines if line and not line.startswith('#') and '=' in line)
if values.get('LAB_DATA_DIR', data) != data:
    raise SystemExit('已有 LAB_DATA_DIR 不同，请先按实际数据目录人工确认，未修改配置。')
if path.exists() and not values.get('LAB_SECRET_KEY'):
    raise SystemExit('已有配置缺少 LAB_SECRET_KEY，不能生成新密钥替换现有会话。')
updates = {'LAB_ENV': 'production', 'LAB_SECRET_KEY': values.get('LAB_SECRET_KEY') or secrets.token_urlsafe(64),
           'LAB_ALLOWED_HOSTS': domain + (',' + sys.argv[4] if sys.argv[4] else ''),
           'LAB_CSRF_ORIGINS': ','.join('https://' + d for d in [domain] + [a for a in sys.argv[4].split(',') if a]),
           'LAB_DATA_DIR': data, 'LAB_PRIMARY_DOMAIN': domain, 'LAB_DOMAIN_ALIASES': sys.argv[4],
           'LAB_BACKEND_PORT': sys.argv[5], 'LAB_NGINX_FILE': sys.argv[6], 'LAB_PUBLIC_IP': sys.argv[7]}
if sys.argv[8]:
    updates['LD_LIBRARY_PATH'] = sys.argv[8]
updates['LAB_SSL_CERT_FILE'] = sys.argv[9]
updates['LAB_SSL_KEY_FILE'] = sys.argv[10]
result = [line for line in lines if line.split('=', 1)[0] not in updates]
result += [key + '=' + value for key, value in updates.items()]
result = '\n'.join(result) + '\n'
changed = result != original
if changed:
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as output:
        output.write(result)
        temporary = pathlib.Path(output.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)
if path.stat().st_mode & 0o777 != 0o600:
    path.chmod(0o600)
print(int(changed))
PY
    )

    [[ -f "$DATA_ROOT/lab.sqlite3" ]] || touch "$DATA_ROOT/.initializing"
    if [[ -f "$DATA_ROOT/lab.sqlite3" && -n "$OLD_RELEASE" && "$OLD_RELEASE" != "$release" ]]; then
        log '备份现有数据库、账号和素材……'
        sh "$APP_ROOT/current/deploy/manage.sh" backup_site
    fi
    if [[ "$OLD_RELEASE" != "$release" ]]; then
        if [[ "$OLD_RUNNING" == 1 ]]; then
            systemctl stop litonglab
            STOPPED_BY_INSTALLER=1
        fi
        ln -sfn "$release" "$APP_ROOT/current.next"
        mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
        SWITCHED=1
    fi
    cd "$APP_ROOT/current"
    local data_changed=0
    if ! sh deploy/manage.sh migrate --check; then
        ROLLBACK_SAFE=0
        # Also pause an already-active service when resuming an interrupted migration.
        if systemctl is-active --quiet litonglab; then systemctl stop litonglab; fi
        sh deploy/manage.sh migrate --noinput
        data_changed=1
    fi
    if [[ -f "$DATA_ROOT/.initializing" ]]; then
        sh deploy/manage.sh seed_site
        sh deploy/manage.sh bootstrap_admin
        rm "$DATA_ROOT/.initializing"
        data_changed=1
    fi
    sh deploy/manage.sh hydrate_publication_pages
    sh deploy/manage.sh sync_public_media
    data_changed=1
    sh deploy/manage.sh check
    write_runtime_units
    prepare_certbot
    "$PYTHON_BIN" - "$ENV_FILE" "$CERTBOT_BIN" "$EMAIL" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
lines = [line for line in path.read_text().splitlines() if line.split('=', 1)[0] not in {'LAB_CERTBOT_BIN', 'LAB_CERT_EMAIL'}]
lines.extend(['LAB_CERTBOT_BIN=' + sys.argv[2], 'LAB_CERT_EMAIL=' + sys.argv[3]])
path.write_text('\n'.join(lines) + '\n')
path.chmod(0o600)
PY
    local tls=0
    local certificate=${LAB_SSL_CERT_FILE:-/etc/letsencrypt/live/$DOMAIN/fullchain.pem}
    local private_key=${LAB_SSL_KEY_FILE:-/etc/letsencrypt/live/$DOMAIN/privkey.pem}
    if [[ -f "$certificate" && -f "$private_key" ]]; then tls=1; fi
    if [[ "$NGINX_FILE" == /etc/nginx/sites-available/* ]]; then
        install -d -m 755 /etc/nginx/sites-enabled
        if [[ -e /etc/nginx/sites-enabled/litonglab || -L /etc/nginx/sites-enabled/litonglab ]]; then
            [[ $(readlink -f /etc/nginx/sites-enabled/litonglab) == "$NGINX_FILE" ]] || fail '已有 Nginx 入口不属于本项目。'
        else ln -s "$NGINX_FILE" /etc/nginx/sites-enabled/litonglab; fi
    fi
    apply_nginx "$tls"
    curl --fail --silent --show-error --retry 5 --retry-connrefused --max-time 20 \
        -H "Host: $DOMAIN" -H 'X-Forwarded-Proto: https' "http://127.0.0.1:$LAB_BACKEND_PORT/api/health/"
    printf '\n官网：https://%s/\n管理中心：https://%s/admin/\n' "$DOMAIN" "$DOMAIN"
    printf '初始凭据（仅首次安装生成）：%s/initial-admin.txt\n' "$DATA_ROOT"
    printf '请登录后修改初始密码；程序与账号数据分开保存。\n'
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
