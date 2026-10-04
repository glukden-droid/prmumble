#!/bin/bash
# First start on a clean data directory: builds the image, starts the
# container (ports from config/mumble-server.ini: 64740, Ice 6504) and creates
# the channels from data/games.txt (copied from config/games.txt if missing -
# edit it before running this script, or the example servers are created).
#
#   cd <project dir> && sudo bash scripts/initialsetup.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$HERE/data"
cd "$HERE"

if [[ -f "$DATA/murmur.sqlite" ]]; then
    echo "initialsetup: $DATA/murmur.sqlite already exists; this is not a fresh setup." >&2
    echo "initialsetup: to start over: docker compose down && mv data data.old" >&2
    exit 1
fi

mkdir -p "$DATA/mumo/modules-enabled" "$DATA/logs"
[[ -f "$DATA/mumble-server.ini" ]] || cp config/mumble-server.ini "$DATA/mumble-server.ini"
[[ -f "$DATA/mumo/mumo.ini" ]] || cp config/mumo.ini "$DATA/mumo/mumo.ini"
if [[ ! -f "$DATA/games.txt" && -f config/games.txt ]]; then
    cp config/games.txt "$DATA/games.txt"
    echo "initialsetup: data/games.txt created from config/games.txt"
fi

docker compose build
docker compose up -d

"$HERE/scripts/createchannel.sh"
