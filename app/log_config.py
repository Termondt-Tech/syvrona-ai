import logging
import os


def configure_logging():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Optionally add a file handler (uncomment to use file logs)
    # file_handler = logging.FileHandler("app.log")
    # file_handler.setLevel(getattr(logging, log_level))
    # formatter = logging.Formatter(
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # )
    # file_handler.setFormatter(formatter)
    # logging.getLogger().addHandler(file_handler)

    logging.getLogger().info("Logging configured at level: %s", log_level)
