# DeepContext Project

A Python agent project for creating documentation, built with `uv`.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (for dependency management)

## Installation

1.  **Sync dependencies:**
    This project uses `uv` to manage dependencies. Run the following command to create the virtual environment and install packages:
    ```bash
    uv sync
    ```

## Configuration

1.  **Environment Variables:**
    Copy the example environment file to create your local configuration:
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`:**
    Open the `.env` file and populate the required variables:
    -   `GOOGLE_API_KEY`: Your Google Cloud API key.
    -   `WEBSITE_URL`: The target website URL for the agent.
    -   `OPENAI_KEY`: Your OpenAI API key.

## Usage

To run the main agent:

```bash
uv run python src/agents/main.py
```

This command uses `uv` to run the script within the project's virtual environment.
