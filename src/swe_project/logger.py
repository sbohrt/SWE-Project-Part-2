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

    # Validate log file path
    # If path contains directory components, check if directory exists and is writable
    log_dir = os.path.dirname(log_file)

    if log_dir:  # If there's a directory component in the path
        if not os.path.exists(log_dir):
            print(
                f"Error: Directory '{log_dir}' does not exist for LOG_FILE '{log_file}'",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.access(log_dir, os.W_OK):
            print(
                f"Error: Directory '{log_dir}' is not writable for LOG_FILE '{log_file}'",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        # If no directory specified (just a filename), check current directory
        if not os.access(".", os.W_OK):
            print(
                f"Error: Current directory is not writable for LOG_FILE '{log_file}'",
                file=sys.stderr,
            )
            sys.exit(1)

    # if directory exists and is writable, set up logging normally
    logging.basicConfig(
        filename=log_file,
        level=log_level,
        format="%(asctime)s - [%(levelname)s] - %(message)s",
    )

    logging.info("Logging initialized with level %s", log_level_str)
