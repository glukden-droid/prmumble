#!/bin/bash
# Creates the PR channel tree on the running server and writes the mumo
# channel map (data/mumo/modules-enabled/prbf2.ini), then restarts the
# container so mumo picks the map up.
#
# Game servers come from data/games.txt (one per line:
# "name | channel title | ip:port", see config/games.txt); without that file
# the GAMES list at the top of scripts/setup_channels.py is used.
#
#   scripts/createchannel.sh           only on an empty server
#   scripts/createchannel.sh --force   add another tree anyway
set -euo pipefail

CONTAINER="${CONTAINER:-prmurmur15}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

# Wait for Ice: mumo.ini holds its port.
for _ in $(seq 1 30); do
    if docker exec "$CONTAINER" bash -c \
        'p=$(sed -nE "s/^port *= *([0-9]+)/\1/p" /data/mumo/mumo.ini); echo >/dev/tcp/127.0.0.1/$p' 2>/dev/null; then
        break
    fi
    sleep 1
done

games=()
if [[ -f "$HERE/data/secret.txt" ]]; then
    games+=(-e "PRMUMBLE_SECRET=$(tr -d '\r\n' < "$HERE/data/secret.txt")")
    echo "createchannel: identity secret from data/secret.txt"
fi
if [[ -f "$HERE/data/games.txt" ]]; then
    games+=(-e PRMUMBLE_GAMES=/data/games.txt)
    echo "createchannel: game servers from data/games.txt"
fi

docker exec "${games[@]}" "$CONTAINER" python3 /opt/scripts/setup_channels.py "$@"
docker restart "$CONTAINER" >/dev/null
echo "createchannel: done, $CONTAINER restarted"
