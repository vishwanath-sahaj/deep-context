from src.common.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    logger.info("Agent initialized.")
    # Entry point for your agent logic
    # import google.genai.agent_adk as adk
    # ...


if __name__ == "__main__":
    main()
