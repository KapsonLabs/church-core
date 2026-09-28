#!/usr/bin/env bash

# Church production deployment for children.church.iolabz.ug.
# Source repositories are expected at the paths below. Run with:
#   SSL_EMAIL=admin@example.com sudo -E bash deploy.sh

set -Eeuo pipefail

APP_DOMAIN="children.church.iolabz.ug"
PROJECT_ROOT="/root/projects/Church"
PROJECT_DIR="$PROJECT_ROOT/church-core"
FRONTEND_ROOT="$PROJECT_ROOT/church-frontend"
VENV_PATH="$PROJECT_DIR/.venv"
STATIC_DIR="$PROJECT_DIR/staticfiles"
MEDIA_DIR="$PROJECT_DIR/media"
ENV_FILE="$PROJECT_DIR/.env"
SOCKET_PATH="/run/church/daphne.sock"

WEB_SERVICE="church.service"
WORKER_SERVICE="church-celery.service"
BEAT_SERVICE="church-celery-beat.service"
NGINX_SITE="/etc/nginx/sites-available/church"

log() { printf '\n[Church] %s\n' "$1"; }
fail() { printf '\n[Church ERROR] %s\n' "$1" >&2; exit 1; }
trap 'fail "Deployment stopped at line $LINENO."' ERR

preflight() {
    [ "${EUID}" -eq 0 ] || fail "Run this script with sudo/root privileges."
    [ -n "${SSL_EMAIL:-}" ] || fail "SSL_EMAIL is required for Let’s Encrypt."
    [ -d "$PROJECT_DIR" ] || fail "Backend directory not found: $PROJECT_DIR"
    [ -d "$FRONTEND_ROOT" ] || fail "Frontend directory not found: $FRONTEND_ROOT"
    [ -f "$ENV_FILE" ] || fail "Production environment file not found: $ENV_FILE"
    [ -f "$FRONTEND_ROOT/dist/index.html" ] || fail "Committed frontend build not found: $FRONTEND_ROOT/dist/index.html"
    for command in python3 systemctl curl apt-get; do
        command -v "$command" >/dev/null 2>&1 || fail "Required command is not installed: $command"
    done
    grep -Eq '^SECRET_KEY=.+$' "$ENV_FILE" || fail "SECRET_KEY must be configured in $ENV_FILE"
    grep -Eq '^DATABASE_URL=.+$' "$ENV_FILE" || fail "DATABASE_URL must be configured in $ENV_FILE"
    grep -Eq '^REDIS_URL=.+$' "$ENV_FILE" || fail "REDIS_URL must be configured in $ENV_FILE"
    grep -Eq '^ALLOWED_HOSTS=.+$' "$ENV_FILE" || fail "ALLOWED_HOSTS must be configured in $ENV_FILE"
    grep -Eq '^CORS_ALLOWED_ORIGINS=.+$' "$ENV_FILE" || fail "CORS_ALLOWED_ORIGINS must be configured in $ENV_FILE"
}

install_system_packages() {
    log "Installing Nginx and Certbot"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx
}

setup_backend() {
    log "Installing backend dependencies"
    if [ ! -x "$VENV_PATH/bin/python" ]; then
        python3 -m venv "$VENV_PATH"
    fi
    "$VENV_PATH/bin/pip" install --upgrade pip
    "$VENV_PATH/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

    log "Validating production configuration and migrations"
    cd "$PROJECT_DIR"
    DJANGO_SETTINGS_MODULE=config.settings.production "$VENV_PATH/bin/python" manage.py check --deploy --fail-level WARNING
    DJANGO_SETTINGS_MODULE=config.settings.production "$VENV_PATH/bin/python" manage.py makemigrations --check --dry-run
    DJANGO_SETTINGS_MODULE=config.settings.production "$VENV_PATH/bin/python" manage.py migrate --noinput
    # DJANGO_SETTINGS_MODULE=config.settings.production "$VENV_PATH/bin/python" manage.py seed_permissions
    DJANGO_SETTINGS_MODULE=config.settings.production "$VENV_PATH/bin/python" manage.py seed_watoto_sample_data

    install -d -m 0755 "$STATIC_DIR" "$MEDIA_DIR"
    DJANGO_SETTINGS_MODULE=config.settings.production STATIC_ROOT="$STATIC_DIR" MEDIA_ROOT="$MEDIA_DIR" "$VENV_PATH/bin/python" manage.py collectstatic --noinput
}

write_services() {
    log "Writing systemd services"
    cat > "/etc/systemd/system/$WEB_SERVICE" <<EOF
[Unit]
Description=Church Daphne web service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
Environment=STATIC_ROOT=$STATIC_DIR
Environment=MEDIA_ROOT=$MEDIA_DIR
RuntimeDirectory=church
RuntimeDirectoryMode=0755
ExecStart=$VENV_PATH/bin/daphne -u $SOCKET_PATH --access-log - --proxy-headers config.asgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    cat > "/etc/systemd/system/$WORKER_SERVICE" <<EOF
[Unit]
Description=Church Celery worker
After=network.target redis-server.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=$VENV_PATH/bin/celery -A config worker --loglevel=info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    cat > "/etc/systemd/system/$BEAT_SERVICE" <<EOF
[Unit]
Description=Church Celery Beat scheduler
After=network.target redis-server.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
StateDirectory=church-celery
ExecStart=$VENV_PATH/bin/celery -A config beat --loglevel=info --schedule=/var/lib/church-celery/beat-schedule
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$WEB_SERVICE" "$WORKER_SERVICE" "$BEAT_SERVICE"
    systemctl restart "$WEB_SERVICE" "$WORKER_SERVICE" "$BEAT_SERVICE"
}

write_nginx() {
    log "Configuring Nginx"
    cat > "$NGINX_SITE" <<EOF
upstream church_asgi {
    server unix:$SOCKET_PATH;
}

server {
    listen 80;
    listen [::]:80;
    server_name $APP_DOMAIN;
    root $FRONTEND_ROOT/dist;
    index index.html;
    client_max_body_size 10M;

    location /api/ {
        proxy_pass http://church_asgi;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /admin/ {
        proxy_pass http://church_asgi;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /health/ { proxy_pass http://church_asgi; proxy_set_header Host \$host; proxy_set_header X-Forwarded-Proto \$scheme; }
    location = /ready/ { proxy_pass http://church_asgi; proxy_set_header Host \$host; proxy_set_header X-Forwarded-Proto \$scheme; }
    location /static/ { alias $STATIC_DIR/; expires 30d; add_header Cache-Control "public, immutable"; }
    location /media/ { alias $MEDIA_DIR/; expires 7d; }
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
    ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/church
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl enable nginx
    systemctl restart nginx
}

configure_https() {
    log "Obtaining or renewing the Let’s Encrypt certificate"
    certbot --nginx --domain "$APP_DOMAIN" --email "$SSL_EMAIL" --agree-tos --non-interactive --redirect --keep-until-expiring
    nginx -t
    systemctl reload nginx
}

verify() {
    log "Verifying services"
    systemctl is-active --quiet "$WEB_SERVICE"
    systemctl is-active --quiet "$WORKER_SERVICE"
    systemctl is-active --quiet "$BEAT_SERVICE"
    systemctl is-active --quiet nginx
    curl --fail --silent --show-error "https://$APP_DOMAIN/health/" >/dev/null
    curl --fail --silent --show-error "https://$APP_DOMAIN/ready/" >/dev/null
    log "Deployment complete: https://$APP_DOMAIN"
    printf 'Create the first superuser when needed with:\n  DJANGO_SETTINGS_MODULE=config.settings.production %s/bin/python %s/manage.py createsuperuser\n' "$VENV_PATH" "$PROJECT_DIR"
}

main() {
    preflight
    install_system_packages
    setup_backend
    write_services
    write_nginx
    configure_https
    verify
}

main "$@"
