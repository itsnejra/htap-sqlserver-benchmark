FROM ubuntu:22.04

# Instalacija mssql-tools18 (sqlcmd) i curl
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] \
       https://packages.microsoft.com/ubuntu/22.04/prod jammy main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends mssql-tools18 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="$PATH:/opt/mssql-tools18/bin"

COPY run_setup.sh /init/run_setup.sh
COPY 00_DatabaseSetup_docker.sql /init/00_DatabaseSetup_docker.sql
COPY 01_restore_stackoverflow.sql /init/01_restore_stackoverflow.sql
RUN chmod +x /init/run_setup.sh

ENTRYPOINT ["/bin/bash", "/init/run_setup.sh"]
