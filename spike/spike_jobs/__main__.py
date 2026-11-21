"""`python -m spike_jobs`: run one tick and exit. For a platform cron or a manual run;
it calls the same function as the in-process loop."""
import os

from .clock import SystemClock
from .jobs import tick

tick(os.environ["DATABASE_URL"], SystemClock())
