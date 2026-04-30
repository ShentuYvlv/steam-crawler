
cat >/etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.1panel.live"
  ]
}
EOF

systemctl restart docker
docker info
docker pull python:3.12-slim

