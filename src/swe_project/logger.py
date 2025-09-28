import logging
import os
import sys


def setup_logging() -> None:
    # read env vars
    log_file = os.getenv("LOG_FILE", "default.log")
    log_level_str = os.getenv("LOG_LEVEL", "0").strip()

    # each level mapped to the logging it does
    level_map = {
        "0": logging.CRITICAL + 1,  # silence
        "1": logging.INFO,
        "2": logging.DEBUG,
    }
    log_level = level_map.get(log_level_str, logging.CRITICAL + 1)

    # check if the directory exists
    log_dir = os.path.dirname(log_file) or "."
    if not os.path.exists(log_dir):
        # terminate with exit code 1 if directory doesn't exist
        print(f"Invalid LOG_FILE path: {log_file}", file=sys.stderr)
        sys.exit(1)

    # if directory exists, set up logging normally
    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format="%(asctime)s - [%(levelname)s] - %(message)s",
    )

    logging.info("Logging initialized with level %s", log_level_str)
