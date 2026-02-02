from src.common.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    print("Agent initialized. Type 'exit' to quit.")

    # Initialize the agent
    agent = Agent(
        name="greeting_agent",
        model="gemini-2.5-flash",
        instruction="You are a helpful assistant. Provide a warm and friendly greeting to the user based on their input.",
    )

    # Initialize the runner
    runner = Runner(
        agent=agent,
        app_name="greeting_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    user_id = "user_default"
    session_id = "session_default"

    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            print("Agent: ", end="", flush=True)

            # Run the agent with the user input
            for event in runner.run(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text=user_input)]
                ),
            ):
                # Process and print the agent's response
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            print(part.text, end="", flush=True)
            print()  # Newline after response

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break


if __name__ == "__main__":
    main()
