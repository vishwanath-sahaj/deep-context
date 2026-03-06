import asyncio
import os
from dotenv import load_dotenv
from agents.action.agent import ActionAgent


async def main():
    load_dotenv()
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[RunActionAgent] ERROR: Required: Add ANTHROPIC_API_KEY='your-claude-api-key' to your .env file")
        return
        
    print("[RunActionAgent] Initializing Action Agent...")
    agent = ActionAgent()
    
    flow_path = os.path.join(os.path.dirname(__file__), "flow.md")
    with open(flow_path, "r", encoding="utf-8") as f:
        instruction = f.read()

    target_url = "https://dev.np-sadhak.sahaj.ai"
    
    print(f"[RunActionAgent] Starting Action Agent execution | instruction={instruction} | target_url={target_url}")
    
    result = await agent.run(instruction=instruction, url=target_url)
    
    print(f"[RunActionAgent] Agent execution completed | result={result}")

if __name__ == "__main__":
    asyncio.run(main())
