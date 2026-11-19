#!/usr/bin/env bash
# Run as root with the dedicated public key's base64 field as the only argument.
set -euo pipefail
key=$1
[[ $key =~ ^[A-Za-z0-9+/=]+$ ]]
[[ $(sshd -T | awk '$1=="gatewayports" {print $2}') == no ]]
test -x /usr/lib/systemd/systemd-socket-proxyd
# Release a stale reverse listener when the PC sleeps or changes networks.
keepalive=/etc/ssh/sshd_config.d/97-newsfinder-query.conf
printf '%s\n' 'Match User newsfinder-query' '    ClientAliveInterval 15' '    ClientAliveCountMax 3' 'Match all' > "$keepalive"
sshd -t
systemctl reload ssh
account=newsfinder-query
home=/var/lib/newsfinder-query
if ! id "$account" >/dev/null 2>&1; then
    useradd --system --home-dir "$home" --shell /bin/sh "$account"
fi
test "$(getent passwd "$account" | cut -d: -f6)" = "$home"
install -d -m 0755 "$home" "$home/.ssh"
entry="restrict,port-forwarding,permitopen=\"127.0.0.1:1\",permitlisten=\"127.0.0.1:21439\",command=\"/bin/cat\" ssh-ed25519 $key newsfinder-query"
touch "$home/.ssh/authorized_keys"
grep -Fqx "$entry" "$home/.ssh/authorized_keys" || printf '%s\n' "$entry" >> "$home/.ssh/authorized_keys"
chmod 0644 "$home/.ssh/authorized_keys"
install -d -m 0700 /opt/newsfinder/imports/ollama-query
cat > /etc/systemd/system/newsfinder-ollama-query.socket <<'UNIT'
[Unit]
Description=Private Ollama query socket for NewsFinder
[Socket]
ListenStream=/opt/newsfinder/imports/ollama-query/ollama.sock
SocketMode=0600
RemoveOnStop=yes
[Install]
WantedBy=sockets.target
UNIT
cat > /etc/systemd/system/newsfinder-ollama-query.service <<'UNIT'
[Unit]
Description=Forward NewsFinder queries to the PC tunnel
[Service]
ExecStart=/usr/lib/systemd/systemd-socket-proxyd --exit-idle-time=60s 127.0.0.1:21439
DynamicUser=yes
NoNewPrivileges=yes
UNIT
systemctl daemon-reload
systemctl enable --now newsfinder-ollama-query.socket
envfile=/opt/newsfinder/production.env
url=unix:///imports/ollama-query/ollama.sock
if grep -q '^OLLAMA_URL=' "$envfile"; then
    sed -i "s|^OLLAMA_URL=.*|OLLAMA_URL=$url|" "$envfile"
else
    printf '\nOLLAMA_URL=%s\n' "$url" >> "$envfile"
fi

