"""Tests for SSE graph event formatting."""

import json

from src.api.sse_streamer import SSEStreamer


def test_assistant_chain_start_emits_agent_and_status_events():
    streamer = SSEStreamer()

    events = streamer.handle_chain_start("assistant")

    assert [event["event"] for event in events] == ["agent", "status"]
    assert json.loads(events[0]["data"]) == {
        "agent": "assistant",
        "all_agents": ["assistant"],
    }
    assert json.loads(events[1]["data"]) == {"message": "답변 준비 중..."}


def test_assistant_chain_end_emits_tool_results_and_final_content_once():
    streamer = SSEStreamer()
    output = {
        "tool_results": [{"tool": "retriever", "confidence": "high"}],
        "messages": [{"role": "assistant", "content": "최종 답변"}],
    }

    first_events = streamer.handle_chain_end("assistant", output)
    second_events = streamer.handle_chain_end("assistant", output)

    assert [event["event"] for event in first_events] == ["tool", "token"]
    assert json.loads(first_events[0]["data"]) == {"tool": "retriever", "confidence": "high"}
    assert first_events[1] == {"event": "token", "data": "최종 답변"}
    assert [event["event"] for event in second_events] == ["tool"]
