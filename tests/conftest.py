"""Settings shared by every test suite in the workspace."""

import os

from hypothesis import settings

# No deadline in any profile: a per-example deadline times the machine as well as the code, and
# a busy laptop turned it into a red the next run could not reproduce (#30).
settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile("ci", max_examples=500, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
