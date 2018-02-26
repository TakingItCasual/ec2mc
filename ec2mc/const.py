import os

# Location where the script finds/creates its configuration file(s).
CONFIG_FOLDER = os.path.join(os.path.expanduser("~"), ".ec2mc", "")
# Limit configuration RW access to owner of file(s).
CONFIG_PERMS = 0o600
# Private key files must be read-only, and only readable by the user.
PK_PERMS = 0o400
