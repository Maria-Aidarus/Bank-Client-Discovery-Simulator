import json

import pytest

from bank_simulator.agents.client_agent import CLIENT_SYSTEM_PROMPT, OllamaClientAgent
from bank_simulator.agents.coach_agent import COACH_SYSTEM_PROMPT
from bank_simulator.agents.disclosure import DisclosureController
from bank_simulator.data_loader import ContentLoadError
from bank_simulator.services.content_service import ContentService


def _state(interviews, client_id, question, previous=()):
    session = interviews.create_session(client_id)
    for student, client in previous:
        session = interviews.record_student_message(session, student)
        session = interviews.record_client_response(session, client)
    session = interviews.record_student_message(session, question)
    return DisclosureController().available_information(interviews.build_client_context(session))


def _payload(interviews, scripted_adapter, client_id, question, previous=()):
    session = interviews.create_session(client_id)
    for student, client in previous:
        session = interviews.record_student_message(session, student)
        session = interviews.record_client_response(session, client)
    session = interviews.record_student_message(session, question)
    adapter = scripted_adapter(["A supplied customer reply."])
    OllamaClientAgent(adapter).respond(interviews.build_client_context(session))
    return json.loads(adapter.calls[0][0]["content"].split("Customer context\n")[1]), adapter


def test_client_style_is_guidance_and_client_budget_remains_separate(interviews, scripted_adapter):
    _, adapter = _payload(interviews, scripted_adapter, "maryam", "Tell me about your business.")
    assert "1–3" in CLIENT_SYSTEM_PROMPT
    assert "not a rigid limit" in CLIENT_SYSTEM_PROMPT
    assert "every part of a clear multipart" in CLIENT_SYSTEM_PROMPT
    assert "do not repeat their figures" in CLIENT_SYSTEM_PROMPT
    assert adapter.options[0]["max_tokens"] == 2048
    assert adapter.options[0]["temperature"] > 0.1


def test_impact_question_keeps_unrequested_figures_out_of_the_roleplay(interviews, scripted_adapter):
    payload, _ = _payload(interviews, scripted_adapter, "maryam", "How do late payments affect your business?")
    facts = " ".join(payload["available_facts"])
    assert "payroll" in facts and "supplier" in facts
    assert "QAR" not in facts
    assert "Sharia" not in json.dumps(payload)
    assert "fact_references" not in json.dumps(payload)
    assert "question_patterns" not in json.dumps(payload)


@pytest.mark.parametrize("question, expected, excluded", [
    ("How much cash is available?", "25,000", ("40,000", "60,000", "15,000")),
    ("What payments are due?", "40,000", ("25,000", "60,000", "15,000")),
    ("What payments are you expecting from customers?", "60,000", ("25,000", "40,000", "15,000")),
    ("What financing do you prefer?", "Sharia", ("25,000", "40,000", "60,000")),
])
def test_current_question_receives_only_requested_financial_details(interviews, question, expected, excluded):
    state = _state(interviews, "maryam", question)
    facts = " ".join(state.relevant_facts)
    assert expected in facts
    assert all(value not in facts for value in excluded)


def test_multipart_question_includes_all_requested_amounts(interviews):
    state = _state(interviews, "maryam", "How much cash is available, what payments are due, and what receipts are expected?")
    facts = " ".join(state.relevant_facts)
    assert all(amount in facts for amount in ("25,000", "40,000", "60,000"))
    assert "15,000" not in facts
    assert "Sharia" not in facts


def test_contextual_obligations_and_receipts_follow_up(interviews):
    previous = [("How much cash is available?", "The business has QAR 25,000 available.")]
    state = _state(interviews, "maryam", "And how much do you need to pay? What about the payments coming in?", previous)
    facts = " ".join(state.relevant_facts)
    assert "40,000" in facts and "60,000" in facts
    assert "25,000" not in facts
    assert "25,000" in " ".join(state.disclosed_facts)


def test_due_date_reference_requires_relevant_preceding_context(interviews):
    assert not _state(interviews, "maryam", "And when is it due?").relevant_facts
    previous = [("What payments are due?", "We need to pay QAR 40,000.")]
    assert "three weeks" in " ".join(_state(interviews, "maryam", "And when is it due?", previous).relevant_facts)


@pytest.mark.parametrize("question", ["What about that?", "Can you explain?", "How much is it?", "Why is that important?"])
def test_generic_follow_up_keeps_the_recent_goal_topic(interviews, question):
    previous = [("What are you saving for?", "I want QAR 9,000 for certification in 18 months.")]
    state = _state(interviews, "mohamed", question, previous)
    assert "9,000" in " ".join(state.relevant_facts)
    assert "1,200" not in " ".join(state.relevant_facts)


def test_unspoken_available_facts_are_not_marked_disclosed(interviews):
    previous = [("How do customer payment delays affect your ability to pay suppliers?", "It makes paying suppliers difficult.")]
    state = _state(interviews, "maryam", "What do you do for work?", previous)
    assert "15,000" in " ".join(state.facts)
    assert "15,000" not in " ".join(state.disclosed_facts)
    assert "supplier" in " ".join(state.disclosed_facts)
    assert state.relevant_facts == ()


def test_product_discussion_uses_only_mentioned_catalogue_product(interviews, scripted_adapter, content):
    payload, _ = _payload(interviews, scripted_adapter, "mohamed", "Would Goal Saver Account work for you?")
    assert payload["discussed_products"] == [content.get_product("goal-saver-account").model_dump(mode="json")]
    assert "same day" in " ".join(payload["available_facts"])
    assert "1,200" not in json.dumps(payload)
    assert "business-flex-credit" not in json.dumps(payload)
    assert "select an optimal" in CLIENT_SYSTEM_PROMPT


def test_product_reference_and_constraint_continue_across_turns(interviews, scripted_adapter):
    previous = [("Business Flex Credit is an interest-bearing line. Would that work?", "I prefer Sharia-compliant banking.")]
    payload, _ = _payload(interviews, scripted_adapter, "maryam", "Why is that important?", previous)
    assert payload["discussed_products"][0]["id"] == "business-flex-credit"
    assert "Sharia" in " ".join(payload["available_facts"])


def test_personality_is_editable_and_distinct_without_public_leakage(interviews, scripted_adapter, editable_data):
    maryam, _ = _payload(interviews, scripted_adapter, "maryam", "Hello")
    mohamed, _ = _payload(interviews, scripted_adapter, "mohamed", "Hello")
    assert maryam["personality_guidance"] != mohamed["personality_guidance"]
    assert "personality_guidance" not in maryam["public_profile"]
    path = editable_data / "hidden_needs" / "maryam.json"
    record = json.loads(path.read_text())
    record["personality_guidance"] = ["Use measured everyday language."]
    path.write_text(json.dumps(record))
    _, needs = ContentService(editable_data).get_private_client("maryam")
    assert needs.personality_guidance == ("Use measured everyday language.",)


@pytest.mark.parametrize("field, value, error", [
    ("follow_up_after", ["Unknown topic"], "nonexistent predecessor"),
    ("product_ids", ["unknown-product"], "unknown product ID"),
])
def test_new_rule_references_are_validated(editable_data, field, value, error):
    path = editable_data / "hidden_needs" / "maryam.json"
    data = json.loads(path.read_text())
    target = next(rule for rule in data["disclosure_topics"] if rule["topic"] == "Upcoming business payments")
    target[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ContentLoadError, match=error):
        ContentService(editable_data)


def test_coach_distinguishes_errors_from_optional_product_opportunities():
    assert "products actually submitted" in COACH_SYSTEM_PROMPT
    assert "Unselected alternatives are optional" in COACH_SYSTEM_PROMPT
    assert "Do not introduce unrelated products" in COACH_SYSTEM_PROMPT
    assert "suitable product with limitations" in COACH_SYSTEM_PROMPT
    assert "use fewer when appropriate" in COACH_SYSTEM_PROMPT
    assert "do not claim the student omitted" in COACH_SYSTEM_PROMPT
    assert "Do not claim a figure was overlooked when it was discussed" in COACH_SYSTEM_PROMPT
    assert "Put any unselected alternative only in" in COACH_SYSTEM_PROMPT
    assert "merge any overlapping product-trade-off" in COACH_SYSTEM_PROMPT
    assert "If a precise term is absent from the catalogue" in COACH_SYSTEM_PROMPT
