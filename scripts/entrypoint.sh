#!/bin/bash
# Starts the Mumble server and, once its Ice port answers, the mumo bot.
# Both run in the foreground; if either dies the container stops, so Docker's
# restart policy brings the pair back together.
set -euo pipefail

DATA=/data
INI="$DATA/mumble-server.ini"

mkdir -p "$DATA/mumo/modules-enabled" "$DATA/logs"

# mumble-server drops root and runs as mumble-server; the bind-mounted
# directory belongs to the host user, so hand it over or the database
# cannot be created.
chown -R mumble-server:mumble-server "$DATA"

if [[ ! -f "$INI" ]]; then
    echo "entrypoint: $INI is missing; mount the data directory" >&2
    exit 1
fi

# A missing database means a fresh server: mumble-server creates it empty,
# then scripts/setup_channels.py builds the channels and the mumo map.
db="$(sed -nE 's/^[[:space:]]*database[[:space:]]*=[[:space:]]*(.+)$/\1/p' "$INI" | tail -1)"
if [[ -n "$db" && ! -f "$db" ]]; then
    echo "entrypoint: database $db not found, starting a fresh server"
    echo "entrypoint: then run: python3 /opt/scripts/setup_channels.py"
fi

term() {
    echo "entrypoint: stopping"
    [[ -n "${MUMO_PID:-}" ]] && kill "$MUMO_PID" 2>/dev/null || true
    [[ -n "${SRV_PID:-}" ]] && kill "$SRV_PID" 2>/dev/null || true
    wait || true
}
trap term SIGTERM SIGINT

echo "entrypoint: mumble-server $(dpkg-query -W -f='${Version}' mumble-server)"
mumble-server -fg -ini "$INI" &
SRV_PID=$!

# Wait for Ice before starting mumo, otherwise it logs a connection refused
# and retries on its own schedule.
ice_port="$(sed -nE 's/.*-p[[:space:]]+([0-9]+).*/\1/p' <<<"$(grep -E '^[[:space:]]*ice[[:space:]]*=' "$INI" | tail -1)")"
ice_port="${ice_port:-6504}"
for _ in $(seq 1 30); do
    if (echo >"/dev/tcp/127.0.0.1/$ice_port") 2>/dev/null; then
        break
    fi
    kill -0 "$SRV_PID" 2>/dev/null || { echo "entrypoint: server exited during start" >&2; wait "$SRV_PID"; }
    sleep 1
done

cd /opt/mumo
echo "entrypoint: starting mumo"
python3 mumo.py -i "$DATA/mumo/mumo.ini" &
MUMO_PID=$!

# Exit as soon as either one does.
wait -n "$SRV_PID" "$MUMO_PID"
term
