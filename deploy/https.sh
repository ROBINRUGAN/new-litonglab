#!/usr/bin/env bash
# designed by mew
# Configure HTTPS after DNS is ready. Run manually.
set -Eeuo pipefail
cd /srv/litonglab/current
. deploy/install.sh
read_configuration
DOMAIN=$LAB_PRIMARY_DOMAIN
DOMAIN_LIST="$DOMAIN${LAB_DOMAIN_ALIASES:+,$LAB_DOMAIN_ALIASES}"
PYTHON_BIN=/srv/litonglab/current/.venv/bin/python
NGINX_FILE=$LAB_NGINX_FILE
certificate=${LAB_SSL_CERT_FILE:-/etc/letsencrypt/live/$DOMAIN/fullchain.pem}
private_key=${LAB_SSL_KEY_FILE:-/etc/letsencrypt/live/$DOMAIN/privkey.pem}
IFS=, read -r -a domains <<< "$DOMAIN_LIST"
if [[ -n "$LAB_SSL_CERT_FILE" ]]; then
    [[ -f "$certificate" && -f "$private_key" ]] || fail '配置的证书或私钥文件不存在。'
    openssl x509 -in "$certificate" -noout -checkend 0 >/dev/null || fail '配置的证书已过期或无法读取。'
    for domain in "${domains[@]}"; do
        openssl x509 -in "$certificate" -noout -checkhost "$domain" >/dev/null || fail "证书不包含域名：$domain"
    done
fi
if [[ -f "$certificate" ]] && openssl x509 -in "$certificate" -noout -checkend 2592000 >/dev/null 2>&1 && grep -Eq 'listen[^;]*443[^;]*ssl' "$NGINX_FILE"; then exit 0; fi
if [[ -n "$LAB_PUBLIC_IP" ]]; then
    if ! "$PYTHON_BIN" - "$DOMAIN_LIST" "$LAB_PUBLIC_IP" <<'PY'
import socket, sys
for domain in sys.argv[1].split(','):
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(domain, 80, type=socket.SOCK_STREAM)}
    except OSError:
        raise SystemExit(1)
    if addresses != {sys.argv[2]}:
        raise SystemExit(1)
PY
    then printf '请先将全部域名解析到当前服务器，再运行本命令。\n' >&2; exit 1; fi
fi
check_nginx_ownership
trap on_error ERR
if [[ -z "$LAB_SSL_CERT_FILE" ]]; then
    args=(certonly --webroot -w "$DATA_ROOT/acme" --cert-name "$DOMAIN" --non-interactive --agree-tos --keep-until-expiring --expand)
    for domain in "${domains[@]}"; do args+=(-d "$domain"); done
    if [[ -n ${LAB_CERT_EMAIL:-} ]]; then args+=(--email "$LAB_CERT_EMAIL"); else args+=(--register-unsafely-without-email); fi
    "$LAB_CERTBOT_BIN" "${args[@]}"
fi
apply_nginx 1
curl --fail --silent --show-error --max-time 20 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health/"
printf '\nHTTPS 已启用：%s\n' "$DOMAIN_LIST"
