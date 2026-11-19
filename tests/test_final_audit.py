"""Focused checks for financial clarity and catalogue-grounded agent instructions."""

import json

from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import OllamaCoachAgent
from bank_simulator.models import ProductRecommendation
from bank_simulator.services.coaching_context import build_coaching_context


def test_goal_saver_client_context_keeps_unknown_terms_unconfirmed(content, interviews, scripted_adapter):
    question = (
        "Goal Saver Account lets me pause without affecting the bonus, and early "
        "withdrawals are instant and penalty-free. Is that right?"
    )
    session = interviews.record_student_message(interviews.create_session("mohamed"), question)
    adapter = scripted_adapter(["I would need to check those terms."])
    OllamaClientAgent(adapter).respond(interviews.build_client_context(session))
    messages, = adapter.calls
    prompt, payload_text = messages[0]["content"].split("\nCustomer context\n")
    prompt = " ".join(prompt.split())
    payload = json.loads(payload_text)
    product, = payload["discussed_products"]

    assert product == content.get_product("goal-saver-account").model_dump(mode="json")
    assert "Schedule transfers that can be adjusted or paused." in product["key_features"]
    assert "Early withdrawals take several business days and may forfeit a goal bonus." in product["limitations"]
    assert "penalty-free" not in json.dumps(product)
    assert "Preserve conditional wording" in prompt
    assert "do not assume either a charge or no charge" in prompt
    assert "undocumented procedures, bonus conditions, fees, or penalties" in prompt
    assert "student-supplied product claims as unverified" in prompt
    assert "unless the catalogue supports them" in prompt
    assert messages[-1] == {"role": "user", "content": question}


def test_coach_verifies_unknown_terms_without_requiring_an_invented_explanation(
    content, recommendations, completed_interview, scripted_adapter
):
    session = recommendations.submit_summary(completed_interview, "Assess affordability for the certification goal.")
    justification = (
        "Goal Saver permits adjusted or paused transfers and delayed early withdrawals "
        "with possible bonus loss. Verify pause procedures, bonus conditions, and any fees."
    )
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification=justification,
    )])
    feedback = {
        "what_went_well": ["You identified the certification goal and marked unspecified terms for verification."],
        "what_was_missed": ["Emergency liquidity and monthly affordability were not established."],
        "how_to_improve": ["Ask about existing emergency savings and irregular costs before setting contributions."],
    }
    adapter = scripted_adapter([json.dumps(feedback)])
    OllamaCoachAgent(adapter).evaluate(build_coaching_context(session, content))
    messages, = adapter.calls
    prompt = " ".join(messages[0]["content"].split())
    evidence = json.loads(messages[1]["content"])
    product = next(item for item in evidence["products"] if item["id"] == "goal-saver-account")

    assert product == content.get_product("goal-saver-account").model_dump(mode="json")
    assert evidence["recommendations"] == [{"product_id": "goal-saver-account", "justification": justification}]
    assert "Do not turn possible bonus forfeiture into a guaranteed loss or an additional fee" in prompt
    assert "Adjustable or pausable transfers do not establish procedures or effects on bonuses and charges" in prompt
    assert "Do not fault students for failing to explain undocumented terms; recommend verification instead" in prompt
    assert "unknown, not confirmed charges or a guarantee of no charges" in prompt


def test_mohamed_context_separates_existing_savings_goal_and_uncertain_affordability(interviews, scripted_adapter):
    # These replies are test inputs, not claims about generated model behavior.
    turns = [
        ("How much emergency savings do you have?", "I have QAR 1,200 in emergency savings."),
        ("What are you saving for and by when?", "I want QAR 9,000 for certification in 18 months."),
        ("How much could you realistically put aside?", "I need to check affordability first."),
    ]
    session = interviews.create_session("mohamed")
    adapter = scripted_adapter([reply for _, reply in turns])
    agent = OllamaClientAgent(adapter)
    payloads = []
    for question, _ in turns:
        session = interviews.record_student_message(session, question)
        response = agent.respond(interviews.build_client_context(session))
        payloads.append(json.loads(adapter.calls[-1][0]["content"].split("\nCustomer context\n")[1]))
        session = interviews.record_client_response(session, response)

    emergency, goal, contribution = (" ".join(payload["available_facts"]) for payload in payloads)
    assert "has QAR 1,200 in emergency savings" in emergency
    assert "9,000" not in emergency
    assert "wants to save QAR 9,000 in 18 months" in goal
    assert "separately from his emergency fund" in goal
    assert "1,200" not in goal
    assert "average of QAR 500 per month is feasible" in contribution
    assert "after accounting for irregular expenses and emergency savings" in contribution
    assert "QAR 1,200" in " ".join(payloads[-1]["previously_disclosed_facts"])
    assert "QAR 9,000" in " ".join(payloads[-1]["previously_disclosed_facts"])
