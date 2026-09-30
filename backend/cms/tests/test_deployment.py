# designed by mew
import shlex
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from django.conf import settings


class DeploymentConfigurationTests(TestCase):
    def run_script(self, commands):
        installer = settings.BASE_DIR / "deploy/install.sh"
        return subprocess.run(
            ["bash", "-c", f"source {shlex.quote(str(installer))}; {commands}"],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
        )

    def render(self, tls, certificate=None, private_key=None):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "litonglab.conf"
            command = (
                f"PYTHON_BIN={shlex.quote(sys.executable)}; "
                f"NGINX_FILE={shlex.quote(str(target))}; "
                "DOMAIN=www.lab.example.edu; "
                "DOMAIN_LIST=www.lab.example.edu,lab.example.edu; "
                f"LAB_BACKEND_PORT=8011; "
                f"LAB_SSL_CERT_FILE={shlex.quote(certificate or '')}; "
                f"LAB_SSL_KEY_FILE={shlex.quote(private_key or '')}; "
                f"render_nginx {tls}"
            )
            result = self.run_script(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            return target.read_text()

    def test_custom_port_and_all_domains_reach_same_application(self):
        config = self.render(0)
        self.assertIn("server_name www.lab.example.edu lab.example.edu;", config)
        self.assertNotIn("127.0.0.1:8000", config)
        self.assertEqual(config.count("proxy_pass http://127.0.0.1:8011;"), 3)
        self.assertIn("location ^~ /.well-known/acme-challenge/", config)
        self.assertNotIn("listen 443", config)

    def test_https_keeps_acme_available_and_redirects_http(self):
        config = self.render(1)
        self.assertIn("listen 443 ssl;", config)
        self.assertIn("/etc/letsencrypt/live/www.lab.example.edu/fullchain.pem;", config)
        self.assertIn("return 308 https://$host$request_uri;", config)
        self.assertIn("listen 80;", config)
        self.assertEqual(config.count("location ^~ /.well-known/acme-challenge/"), 2)

    def test_existing_certificate_is_reused_for_https(self):
        certificate = "/managed/certificates/lab/fullchain.pem"
        private_key = "/managed/certificates/lab/privkey.pem"
        config = self.render(1, certificate, private_key)
        self.assertIn(f"ssl_certificate {certificate};", config)
        self.assertIn(f"ssl_certificate_key {private_key};", config)
        self.assertNotIn("/etc/letsencrypt/live/", config)
        self.assertIn("server_name www.lab.example.edu lab.example.edu;", config)

    def test_certificate_paths_cannot_inject_nginx_directives(self):
        result = self.run_script(
            "LAB_SSL_CERT_FILE='/tmp/cert; include /tmp/other.conf'; "
            "LAB_SSL_KEY_FILE=/tmp/key; validate_ssl_paths"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("证书路径必须为绝对路径", result.stderr)

    def test_external_certificate_requires_a_matching_key_path(self):
        result = self.run_script(
            "LAB_SSL_CERT_FILE=/tmp/cert; LAB_SSL_KEY_FILE=; validate_ssl_paths"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("证书和私钥路径必须同时填写", result.stderr)

    def test_domain_alias_cannot_inject_nginx_directives(self):
        result = self.run_script(
            f"PYTHON_BIN={shlex.quote(sys.executable)}; DOMAIN=lab.example.edu; "
            "LAB_DOMAIN_ALIASES='bad.example.edu; include /tmp/other.conf'; "
            "LAB_PUBLIC_IP=182.92.75.97; validate_domains"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("域名格式无效", result.stderr)

    def test_invalid_port_is_rejected_before_configuration_changes(self):
        with TemporaryDirectory() as directory:
            result = self.run_script(
                f"ENV_FILE={shlex.quote(str(Path(directory) / 'absent.env'))}; "
                "LAB_BACKEND_PORT=65536; read_configuration"
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("后台端口必须", result.stderr)

    def test_modern_sqlite_reuses_existing_runtime(self):
        with TemporaryDirectory() as directory:
            result = self.run_script(
                f"PYTHON_BIN={shlex.quote(sys.executable)}; "
                f"APP_ROOT={shlex.quote(directory)}; prepare_sqlite; "
                'test -z "$SQLITE_LIB"'
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
