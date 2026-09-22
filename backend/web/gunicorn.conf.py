# Gunicorn configuration for the Bunch of AIgents web application.
#
# Gunicorn does not terminate TLS here and does not listen on a port. The
# application's own HAProxy does both, because the local HAProxy prefixes a
# PROXY header before the TLS handshake and gunicorn cannot read it there: it
# terminates TLS first, so those bytes break the handshake.
#
# So gunicorn speaks plain HTTP over a Unix socket that only the proxy can
# reach, which also means there is no way to reach the application without
# passing through it.

import os

cBaseDir = os.environ.get("BOA_BASE_DIR", "/opt/boa")

# Unix socket, created by systemd's RuntimeDirectory and owned by `boa`.
bind = "unix:/run/boa-web/web.sock"
backlog = 128

# Workers: a single-user LAN application does not need a worker farm, but two
# workers keep the UI responsive while an agent run is being launched.
workers = 2
threads = 4
worker_class = "gthread"
timeout = 120
graceful_timeout = 30
keepalive = 5

# The proxy in front sets X-Forwarded-For from the PROXY header, and it is the
# only thing that can reach the socket, so its headers are trustworthy.
forwarded_allow_ips = "*"

# Logging
accesslog = os.path.join(cBaseDir, "logs", "access.log")
errorlog = os.path.join(cBaseDir, "logs", "error.log")
loglevel = "info"

# Process naming
proc_name = "boa-web"
