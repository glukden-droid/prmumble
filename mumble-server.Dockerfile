# Mumble server 1.5 with the PR:BF2 channel bot (mumo), on Ubuntu 24.04.
#
# Replaces the 2013 stack (PRMurmur 1.2 + Qt4 + Ice 3.4 + Python 2.6, kept
# alive by bundled libraries and a Debian snapshot of libssl 1.0.0):
#
#   mumble-server     1.5.857   built from the upstream release with the PR
#                               patch (docs/patch_identity.py); Ubuntu only
#                               has the 1.5.517 release candidate
#   python3-zeroc-ice 3.7.10    Ice bindings for Python 3
#   mumo              upstream  the moderator framework (Python 3)
#
# The image holds only programs. State lives in the /data volume:
# mumble-server.ini, murmur.sqlite, mumo's config and the logs.

# --- Stage 1: mumble-server from the upstream source, with the PR patch
# (players' plugin identity goes to the other clients, like PRMurmur did;
# the PR client takes in-game names for its HUD from there).
FROM ubuntu:24.04 AS build

ENV DEBIAN_FRONTEND=noninteractive

# Build dependencies of the Ubuntu mumble package cover the server.
RUN sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake curl ca-certificates python3 \
    && apt-get build-dep -y mumble \
    && rm -rf /var/lib/apt/lists/*

ARG MUMBLE_VERSION=1.5.857
WORKDIR /src
RUN curl -fsSL "https://github.com/mumble-voip/mumble/releases/download/v${MUMBLE_VERSION}/mumble-${MUMBLE_VERSION}.tar.gz" \
        | tar -xz \
    && mv "mumble-${MUMBLE_VERSION}" mumble
COPY docs/patch_identity.py /src/patch_identity.py
RUN python3 /src/patch_identity.py /src/mumble \
    && cmake -S /src/mumble -B /src/build -DCMAKE_BUILD_TYPE=Release \
        -Dclient=OFF -Dserver=ON -Dice=ON -Dzeroconf=OFF -Dtests=OFF \
        -Dwarnings-as-errors=OFF -DBUILD_NUMBER="${MUMBLE_VERSION##*.}" \
    && cmake --build /src/build -j"$(nproc)" \
    && /src/build/mumble-server --version 2>&1 | head -1

# --- Stage 2: runtime
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# The Ubuntu package brings the runtime libraries, the mumble-server user and
# its directories; its binary is replaced by the one built above.
RUN apt-get update && apt-get install -y --no-install-recommends \
        mumble-server \
        python3 \
        python3-zeroc-ice \
        zeroc-ice-slice \
        ca-certificates \
        curl \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/mumble-server /usr/bin/mumble-server
# Ice interface of exactly this server version
COPY --from=build /src/mumble/src/murmur/MumbleServer.ice /usr/share/MumbleServer.ice
RUN mumble-server --version 2>&1 | head -1 \
    && grep -q '^module ' /usr/share/MumbleServer.ice

# mumo: the moderator framework that drives the channels over Ice.
ARG MUMO_REF=master
RUN curl -fsSL "https://github.com/mumble-voip/mumo/archive/${MUMO_REF}.tar.gz" \
        | tar -xz -C /opt \
    && mv "/opt/mumo-${MUMO_REF}" /opt/mumo

# The PR:BF2 module: the only part of the old setup that carries real logic
# (team and squad channels from the game state the Mumble plugin reports).
COPY mumo/modules/prbf2.py /opt/mumo/modules/prbf2.py

# Upstream mumo.py builds its module manager without the config it read, so
# the module directories are always the relative defaults (modules/ and
# modules-enabled/ under /opt/mumo), whatever mumo.ini says. The module
# configs live in the volume, so point the default there.
RUN rm -rf /opt/mumo/modules-enabled \
    && ln -s /data/mumo/modules-enabled /opt/mumo/modules-enabled

COPY scripts/setup_channels.py scripts/check_acl.py scripts/grant_bot.py scripts/link_teams.py scripts/voice_probe.py /opt/scripts/
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

VOLUME /data
EXPOSE 64740/tcp 64740/udp

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
