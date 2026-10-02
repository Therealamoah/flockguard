from app.agent.agent_state import AgentAssessment, AgentState
from app.api.routes import ask as ask_module
from app.services.grok_service import grok_service


def _create_farm(client):
    return client.post("/farms", json={"name": "Test Farm"}).json()


def _completed_agent(monkeypatch):
    async def fake_run_agent(db, *, org_id, trigger, skill, farm_id, house_id, question):
        state = AgentState(trigger=trigger, org_id=org_id, farm_id=farm_id, skill=skill, question=question)
        state.assessment = AgentAssessment(
            priority="low",
            summary="Your birds look fine.",
            recommended_actions=["Keep the drinkers clean", "Watch feed every morning"],
            confidence="moderate",
        )
        state.status = "completed"
        return state

    monkeypatch.setattr(ask_module, "run_agent", fake_run_agent)


def test_stream_sends_the_written_answer_piece_by_piece(authed_client, monkeypatch):
    _completed_agent(monkeypatch)
    sent = {}

    async def fake_stream(messages, **kwargs):
        sent["messages"] = messages
        for piece in ["**Sell early** ", "so you ", "get better prices."]:
            yield piece

    monkeypatch.setattr(grok_service, "stream_chat", fake_stream)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask/stream", json={"question": "How do I earn more at Christmas?", "farm_id": farm["id"]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "**Sell early** so you get better prices."
    assert "Your birds look fine." in sent["messages"][1]["content"]  # grounded in the agent's findings
    assert sent["messages"][-1] == {"role": "user", "content": "How do I earn more at Christmas?"}


def test_stream_falls_back_to_agent_findings_when_writer_fails(authed_client, monkeypatch):
    _completed_agent(monkeypatch)

    async def broken_stream(messages, **kwargs):
        raise RuntimeError("provider down")
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(grok_service, "stream_chat", broken_stream)
    farm = _create_farm(authed_client)

    response = authed_client.post("/ask/stream", json={"question": "Anything wrong?", "farm_id": farm["id"]})

    assert response.status_code == 200
    assert "Your birds look fine." in response.text
    assert "1. **Keep the drinkers clean**" in response.text


def test_stream_greeting_needs_no_ai(authed_client):
    response = authed_client.post("/ask/stream", json={"question": "hi"})
    assert response.status_code == 200
    assert response.text.startswith("Hi!")


def test_plain_ask_now_includes_the_steps_not_just_the_summary(authed_client, monkeypatch):
    _completed_agent(monkeypatch)
    farm = _create_farm(authed_client)

    answer = authed_client.post("/ask", json={"question": "Anything wrong?", "farm_id": farm["id"]}).json()["answer"]

    assert "**What to do:**" in answer and "2. **Watch feed every morning**" in answer
