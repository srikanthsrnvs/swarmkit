"""Agents-as-tools, the SDK way — where in-process orchestration lives in swarmkit.

A coordinator Agent gets two member Agents as tools (`Agent.as_tool`) and answers a question by delegating; nothing
leaves the process. Compare with the network: agents that live in other sandboxes or on other machines are reached
with `send`, and the SDK knows nothing about them. Use this pattern for a lane that wants specialists of its own
(a reviewer, a summarizer) without putting more identities on the network.

    python -m swarmkit.orchestrate "Which quantization format should we try first and why?" \
        [--model deepseek-flash --base-url https://api.deepseek.com/v1 --api-key-env DEEPSEEK_API_KEY] [--post ROOM]

--post sends the coordinator's answer to a room through anet (AGENTNET_URL/AGENTNET_TOKEN or the local daemon).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys


def build(model_name: str, base_url: str, api_key_env: str):
    from agents import Agent, OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI

    api_key = os.environ.get(api_key_env) or sys.exit(f"{api_key_env} is not set")
    if not os.environ.get("OPENAI_API_KEY"):
        set_tracing_disabled(True)
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=AsyncOpenAI(base_url=base_url, api_key=api_key))

    researcher = Agent(name="researcher", model=model, instructions=(
        "You list the concrete options for the question, each with one line of evidence and one risk. Facts only; say "
        "'unknown' rather than invent a number. Under 200 words."))
    reviewer = Agent(name="reviewer", model=model, instructions=(
        "You are handed a list of options. Rank them, name the single acceptance test that would decide between the top two, "
        "and say what would make you change your mind. Under 150 words."))
    coordinator = Agent(name="coordinator", model=model, instructions=(
        "Answer the user's question by first calling research_options, then review_options on its output, then write a "
        "five-line answer: recommendation, why, the acceptance test, the main risk, what to do if it fails."),
        tools=[
            researcher.as_tool(tool_name="research_options", tool_description="List the concrete options with evidence and risks."),
            reviewer.as_tool(tool_name="review_options", tool_description="Rank a list of options and name the deciding test."),
        ])
    return coordinator


async def run(question: str, args: argparse.Namespace) -> str:
    from agents import Runner

    result = await Runner.run(build(args.model, args.base_url, args.api_key_env), question, max_turns=args.max_turns)
    return str(result.final_output)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m swarmkit.orchestrate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("question")
    p.add_argument("--model", default="deepseek-flash")
    p.add_argument("--base-url", default="https://api.deepseek.com/v1")
    p.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    p.add_argument("--max-turns", type=int, default=6)
    p.add_argument("--post", default=None, help="room (or agent) to send the answer to, through anet")
    args = p.parse_args(argv)
    answer = asyncio.run(run(args.question, args))
    print(answer)
    if args.post:
        try:
            import anet  # type: ignore
        except ImportError:
            from swarmkit import netshim as anet  # type: ignore
        net = anet.connect()
        print(net.send(args.post, f"coordinator → {args.post}: {answer}"[:4000]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
