#!/usr/bin/env bash
# Kurage 設計下書き（kcadprep）のデモの公開。https://proto.exbridge.jp/kcadprep/
# 画面（PHP・JS）を heteml に置く。設計の処理は 0.3 の kcadprep.service（:18388）。
# API トークンはこのスクリプトが kcadprep_config.php に書き込む（リポジトリに置かない）。
set -euo pipefail
cd "$(dirname "$0")/.."
for f in public/*.php; do /usr/bin/php -l "$f" >/dev/null; done
TOKEN=$(grep -m1 '^KCADPREP_API_TOKEN=' .env | cut -d= -f2)
[ -n "$TOKEN" ] || { echo "KCADPREP_API_TOKEN が .env にない" >&2; exit 1; }
curl -s -m 8 http://127.0.0.1:18388/api/health | grep -q '"ok":true' || { echo "kcadprep.service が動いていない" >&2; exit 1; }
set -a; . /home/kojima/work/aixec/.env; set +a
remote="/web/proto_exbridge_jp/kcadprep"
up() { curl --fail --silent --show-error --ftp-create-dirs -T "$1" "ftp://${FTP_USER}:${FTP_PASS}@${FTP_HOST}${remote}/${2}"; echo "up: $2"; }
tmp=$(mktemp)
printf "<?php\nreturn ['api' => 'http://exbridge.ddns.net:18388', 'token' => '%s'];\n" "$TOKEN" > "$tmp"
up "$tmp" kcadprep_config.php
rm -f "$tmp"
up public/.htaccess .htaccess
up public/api.php api.php
up public/app.js app.js
up public/index.php index.php
[ -f public/kcadprep-ogp.png ] && up public/kcadprep-ogp.png kcadprep-ogp.png
echo "published: https://proto.exbridge.jp/kcadprep/"
