"""Audio processing and speaker diarization pipeline."""

import logging


# Library imports must not configure global logging or emit through Python's
# last-resort handler. Executable entry points configure the root handlers.
logging.getLogger(__name__).addHandler(logging.NullHandler())
