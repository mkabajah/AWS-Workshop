#!/bin/bash
# Lab 06 · EC2 user data: turns a fresh Amazon Linux 2023 server into a web server.
# EC2 runs this once, as root, at the first boot. Its output is in
#   /var/log/cloud-init-output.log
#
# EDIT the next line: the URL of YOUR fork of this repository on GitHub.
REPO_URL="https://github.com/mkabajah/AWS-Workshop.git"

set -euxo pipefail

# 1. Install the web server and git, and apply security updates
dnf upgrade -y
dnf install -y nginx git

# 2. Get the website from GitHub
git clone --depth 1 "$REPO_URL" /opt/website

# 3. A one-command updater: pull the latest version and publish it
cat > /usr/local/bin/update-site <<'SCRIPT'
#!/bin/bash
set -euo pipefail
git -C /opt/website pull --ff-only --quiet
rm -rf /usr/share/nginx/html/*
cp -r /opt/website/site/. /usr/share/nginx/html/

# Tell the page which server answered (IMDSv2: get a token, then ask for the metadata).
# Behind the load balancer, refresh a few times and watch the server change.
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
md() { curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1"; }
echo "{\"stage\": 1, \"deployedWith\": \"EC2 + nginx · server $(md instance-id) in $(md placement/availability-zone)\"}" \
  > /usr/share/nginx/html/config.json

echo "Website updated to commit $(git -C /opt/website rev-parse --short HEAD)"
SCRIPT
chmod +x /usr/local/bin/update-site
/usr/local/bin/update-site

# 4. Production touches: a health check for the load balancer, compression, security headers
cat > /etc/nginx/default.d/website.conf <<'NGINX'
location = /health { access_log off; default_type text/plain; return 200 "ok\n"; }

gzip on;
gzip_types text/css application/javascript image/svg+xml application/json;

add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
NGINX

# 5. Start nginx now and on every boot
nginx -t
systemctl enable --now nginx
