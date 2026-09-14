"""Organization roles.

Kept intentionally small - OWNER/MANAGER/WORKER are the only roles the
product needs today. VET/CONSULTANT can be added to this enum later
without touching anything else, since every permission check below goes
through `ROLE_RANK`/`require_role`, not hard-coded role names.
"""

from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    WORKER = "worker"


# Higher rank = more privilege. Used for simple "at least this role" checks;
# exact-role checks (e.g. "owner only") should list roles explicitly instead.
ROLE_RANK = {Role.WORKER: 0, Role.MANAGER: 1, Role.OWNER: 2}
