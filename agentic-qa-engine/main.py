"""Entry point: run a natural-language QA scenario end to end.

Usage:
    python main.py "Login to the application, verify the homepage loaded, and logout."
"""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from agent.qa_agent import build_agent
from agent.tools import session
from reporting.report_generator import generate_report

DEFAULT_SCENARIO = (
    "Login to the application, verify the homepage loaded successfully, and logout."
)


async def run(scenario: str):
    agent = build_agent()
    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": scenario}]},
            config={"recursion_limit": 50},
        )
        final_message = result["messages"][-1]
        print("\nAgent summary:\n", final_message.content)
    finally:
        if session.page is not None:
            await session.stop()
        report_path = generate_report(scenario, session.execution_log)
        print(f"\nEvidence report generated: {report_path}")


def main():
    scenario = " ".join(sys.argv[1:]) or DEFAULT_SCENARIO
    print(f"Running scenario: {scenario}\n")
    asyncio.run(run(scenario))


if __name__ == "__main__":
    main()
