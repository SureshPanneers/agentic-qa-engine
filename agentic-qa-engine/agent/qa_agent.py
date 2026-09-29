"""Builds the LangChain tool-calling agent that drives the QA engine."""
import os

from langchain.agents import create_agent

from agent.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are an autonomous QA test execution agent.
You receive a test scenario written in plain English and must execute it in a real browser
using only the tools provided. Always call open_browser first and close_browser last.
Break the scenario into small, ordered steps. After each action, verify the outcome before
proceeding. If a step fails, keep going with the remaining steps so the full evidence trail
is captured, and clearly state which steps failed in your final summary."""


def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
        return ChatOllama(model=model_name, temperature=0)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return ChatGoogleGenerativeAI(model=model_name, temperature=0)

    from langchain_anthropic import ChatAnthropic
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    return ChatAnthropic(model=model_name, temperature=0)


def build_agent():
    llm = _build_llm()
    return create_agent(model=llm, tools=ALL_TOOLS, system_prompt=SYSTEM_PROMPT)
