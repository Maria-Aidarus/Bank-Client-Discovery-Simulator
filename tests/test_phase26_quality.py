import json
import runpy
from pathlib import Path

import pytest
from pydantic import ValidationError

from bank_simulator.agents.client_agent import OllamaClientAgent
from bank_simulator.agents.coach_agent import COACH_SYSTEM_PROMPT, COACH_COMPLETION_TOKENS, COACH_RECOVERY_TOKENS, OllamaCoachAgent
from bank_simulator.agents.disclosure import DisclosureController
from bank_simulator.evaluation import (
    REVIEW_DIMENSIONS, HumanRatings, apply_human_ratings, feedback_metrics,
    new_manual_review, render_review_packet, review_status,
)
from bank_simulator.models import CoachFeedback, ProductRecommendation
from bank_simulator.services.ai_workflow import AIWorkflow
from bank_simulator.services.coaching_context import build_coaching_context


SCENARIOS = json.loads((Path(__file__).resolve().parents[1] / "scripts/conversation_scenarios.json").read_text())
FEEDBACK = {"what_went_well": ["You established a goal."], "what_was_missed": ["Affordability needs follow-up."],
            "how_to_improve": ["Ask what remains after essential and irregular expenses."]}


@pytest.mark.parametrize("client, initial, reply, question, expected", [
    ("maryam", "What payments are you expecting from customers?", "We expect QAR 60,000.",
     "And when would that happen?", "four to six weeks"),
    ("mohamed", "What are you saving for?", "Certification in 18 months.",
     "Why does that concern you?", "QAR 9,000"),
    ("mohamed", "Would Goal Saver Account work?", "I need money available the same day.",
     "Would that account work for you?", "same day"),
    ("mohamed", "What are you saving for?", "Certification in 18 months.",
     "What happens if you need the money earlier?", "same day"),
    ("mohamed", "What are you saving for?", "Certification in 18 months.",
     "How much could you realistically put aside?", "QAR 500"),
    ("maryam", "How much cash is available?", "QAR 25,000.",
     "Which obligations cannot be postponed?", "Payroll has fixed dates"),
])
def test_targeted_follow_ups_preserve_topic_boundaries(interviews, client, initial, reply, question, expected):
    session = interviews.create_session(client)
    session = interviews.record_student_message(session, initial)
    session = interviews.record_client_response(session, reply)
    session = interviews.record_student_message(session, question)
    state = DisclosureController().available_information(interviews.build_client_context(session))
    assert expected in " ".join(state.relevant_facts)
    assert "QAR 1,200" not in " ".join(state.relevant_facts)


@pytest.mark.parametrize("question", ["And when would that happen?", "Why does that concern you?",
                                     "Would that account work for you?", "How much could you realistically put aside?"])
def test_vague_follow_up_alone_does_not_unlock_private_facts(interviews, question):
    session = interviews.record_student_message(interviews.create_session("mohamed"), question)
    state = DisclosureController().available_information(interviews.build_client_context(session))
    assert state.relevant_facts == ()


def test_soft_coaching_length_and_discovery_instructions_keep_reliability_limits():
    assert "180–260 words" in COACH_SYSTEM_PROMPT
    assert "2–3" in COACH_SYSTEM_PROMPT
    assert "soft target" in COACH_SYSTEM_PROMPT
    assert "200–350" not in COACH_SYSTEM_PROMPT
    assert "partial means only a clue" in COACH_SYSTEM_PROMPT
    assert "missed means the transcript did not explore" in COACH_SYSTEM_PROMPT
    assert "remove repeated calculations" in COACH_SYSTEM_PROMPT
    assert "Do not invent generic praise when evidence is scant" in COACH_SYSTEM_PROMPT
    assert COACH_COMPLETION_TOKENS == COACH_RECOVERY_TOKENS == 8192


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario["id"])
def test_each_scenario_keeps_its_own_transcript_products_and_private_benchmark(
    scenario, content, interviews, recommendations, scripted_adapter
):
    adapter = scripted_adapter([*(["A supplied interview response."] * len(scenario["questions"])), json.dumps(FEEDBACK)])
    workflow = AIWorkflow(content, OllamaClientAgent(adapter), OllamaCoachAgent(adapter))
    session = interviews.create_session(scenario["client_id"])
    for question in scenario["questions"]:
        session = workflow.send_student_message(session, question)
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, scenario["summary"])
    session = recommendations.submit_recommendations(
        session, [ProductRecommendation.model_validate(choice) for choice in scenario["recommendations"]],
    )
    result = workflow.generate_feedback(session)
    context = json.loads(adapter.calls[-1][1]["content"])
    assert context["client_profile"]["id"] == context["hidden_needs"]["client_id"] == scenario["client_id"]
    assert context["recommendations"] == scenario["recommendations"]
    assert context["student_summary"] == scenario["summary"]
    assert [message["content"] for message in context["transcript"] if message["role"] == "student"] == scenario["questions"]
    assert result.model_dump(mode="json") == FEEDBACK


def test_measurements_do_not_shorten_feedback_or_claim_quality_approval():
    text = " ".join(["evidence"] * 300)
    feedback = CoachFeedback(what_went_well=(text,), what_was_missed=(), how_to_improve=())
    measured = feedback_metrics(feedback)
    assert measured["word_count"] == 300
    assert measured["within_soft_word_target"] is False
    assert feedback.what_went_well == (text,)
    assert measured["human_accuracy_review_required"] is True
    assert review_status(new_manual_review()) == "unscored"
    assert len(new_manual_review()["scores"]) == 11


@pytest.mark.parametrize("score", [0, 6, True, "4"])
def test_human_ratings_validate_range_and_type(score):
    with pytest.raises(ValidationError):
        HumanRatings(scores={"coach_evidence": score})


def test_manual_scores_are_explicit_and_preserve_the_original_report():
    original = {"manual_review": new_manual_review(), "feedback": FEEDBACK}
    ratings = HumanRatings(reviewer="Human reviewer", scores={"coach_evidence": 4},
                           evidence={"coach_evidence": "Compared feedback with messages 1–4."})
    updated = apply_human_ratings(original, ratings)
    assert original["manual_review"]["scores"]["coach_evidence"] is None
    assert updated["manual_review"]["scores"]["coach_evidence"] == 4
    assert updated["manual_review_status"] == "incomplete"
    assert updated["feedback"] == original["feedback"]
    with pytest.raises(ValidationError):
        HumanRatings(scores={"coach_evidence": 4}, applicable={"coach_evidence": False})
    with pytest.raises(ValidationError):
        HumanRatings(scores={"unknown": 4})


def test_ratings_target_applies_only_to_human_supplied_applicable_scores():
    updated = apply_human_ratings({}, HumanRatings(scores=dict.fromkeys(REVIEW_DIMENSIONS, 4)))
    assert updated["manual_review_status"] == "meets_human_rating_target"
    updated = apply_human_ratings({}, HumanRatings(scores={"coach_evidence": 2}))
    assert updated["manual_review_status"] == "needs_human_attention"
    updated = apply_human_ratings({}, HumanRatings(applicable=dict.fromkeys(REVIEW_DIMENSIONS, False)))
    assert updated["manual_review_status"] == "no_applicable_scores"


def test_human_packet_includes_actual_evidence_and_private_benchmark(content, recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "A certification goal.")
    report = {"status": "completed", "session": session.model_dump(mode="json"), "feedback": FEEDBACK,
              "manual_review": new_manual_review()}
    packet = render_review_packet(report, content)
    assert "Message 1 — student" in packet
    assert "What are you saving for?" in packet
    assert "Private reviewer reference" in packet
    assert "QAR 1,200" in packet
    assert "Unscored" in packet
    assert "client_realism" in packet and "coach_conciseness" in packet
    assert "question_patterns" not in packet


def test_offline_review_mode_writes_template_without_api_calls(monkeypatch, tmp_path, completed_interview):
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_conversations.py"
    main = runpy.run_path(str(script))["main"]
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"session": completed_interview.model_dump(mode="json"), "feedback": FEEDBACK}))
    template = tmp_path / "ratings.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--review-report", str(report_path), "--ratings-template", str(template)])
    monkeypatch.setitem(main.__globals__, "OllamaCloudAdapter", lambda **kwargs: pytest.fail("API constructed"))
    assert main() == 0
    assert report_path.with_suffix(".review.md").exists()
    scores = json.loads(template.read_text())["scores"]
    assert len(scores) == 11 and all(score is None for score in scores.values())


def test_coverage_counts_only_matching_completed_scenarios(tmp_path, content, interviews, recommendations, capsys):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/evaluate_conversations.py"))
    scenarios = {record["id"]: module["EvaluationScenario"].model_validate(record) for record in SCENARIOS}
    session = interviews.create_session("mohamed")
    for question in scenarios["mohamed-weak"].questions:
        session = interviews.record_student_message(session, question)
        session = interviews.record_client_response(session, "A supplied response.")
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, "A certification goal.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification="For the dated goal.",
    )])
    base = {"status": "completed", "session": session.model_dump(mode="json"), "feedback": FEEDBACK}
    (tmp_path / "valid.json").write_text(json.dumps({**base, "scenario_id": "mohamed-weak"}))
    (tmp_path / "wrong-client.json").write_text(json.dumps({**base, "scenario_id": "maryam-weak"}))
    (tmp_path / "failed.json").write_text(json.dumps({**base, "status": "failed", "scenario_id": "maryam-strong"}))
    (tmp_path / "unrelated.json").write_text('[]')
    module["_coverage"](scenarios, tmp_path, content)
    output = capsys.readouterr().out
    assert "mohamed-weak — recorded: valid.json" in output
    assert "maryam-weak — pending live execution" in output
    assert "maryam-strong — pending live execution" in output


def test_offline_ratings_are_recorded_in_a_copy_with_evidence_preserved(monkeypatch, tmp_path, completed_interview):
    main = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/evaluate_conversations.py"))["main"]
    original = {"session": completed_interview.model_dump(mode="json"), "feedback": FEEDBACK,
                "manual_review": new_manual_review()}
    source = tmp_path / "original.json"
    source.write_text(json.dumps(original))
    ratings = tmp_path / "human.json"
    ratings.write_text(json.dumps({"reviewer": "Human", "scores": {"coach_evidence": 4},
                                  "evidence": {"coach_evidence": "Checked messages 1–2."}}))
    output = tmp_path / "reviewed.json"
    monkeypatch.setattr("sys.argv", ["evaluate", "--review-report", str(source), "--ratings", str(ratings),
                                     "--output", str(output)])
    monkeypatch.setitem(main.__globals__, "OllamaCloudAdapter", lambda **kwargs: pytest.fail("API constructed"))
    assert main() == 0
    reviewed = json.loads(output.read_text())
    assert reviewed["manual_review"]["scores"]["coach_evidence"] == 4
    assert reviewed["manual_review_status"] == "incomplete"
    assert reviewed["session"] == original["session"]
    assert reviewed["feedback"] == original["feedback"]
    assert json.loads(source.read_text()) == original


def test_exact_duplicate_feedback_is_flagged_for_review_without_rewriting():
    repeated = "Ask about emergency access."
    feedback = CoachFeedback(what_went_well=(), what_was_missed=(repeated,), how_to_improve=(repeated,))
    assert feedback_metrics(feedback)["exact_duplicate_points"] == 1
    assert feedback.how_to_improve == (repeated,)


def test_unselected_undiscussed_product_critique_gets_one_model_repair(
    content, recommendations, completed_interview, scripted_adapter
):
    session = recommendations.submit_summary(completed_interview, "A dated savings goal.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification="For certification only.",
    )])
    incorrect = {**FEEDBACK, "what_was_missed": ["You failed to consider Business Cash Management."]}
    corrected = {**FEEDBACK, "how_to_improve": ["Optional: consider Everyday Access Account for emergency funds."]}
    adapter = scripted_adapter([json.dumps(incorrect), json.dumps(corrected)])
    events = []
    result = OllamaCoachAgent(adapter, diagnostics=events.append).evaluate(build_coaching_context(session, content))
    assert result.model_dump(mode="json") == corrected
    assert len(adapter.calls) == 2
    assert events[0]["validation_failure_category"] == "unselected_product_critique"
    assert "Move alternatives" in adapter.calls[1][-1]["content"]


def test_product_fairness_validation_exhaustion_never_silently_drops_a_point(
    content, recommendations, completed_interview, scripted_adapter
):
    from bank_simulator.agents.api_adapter import AIServiceError
    session = recommendations.submit_summary(completed_interview, "A savings goal.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="goal-saver-account", justification="For the goal.",
    )])
    incorrect = {**FEEDBACK, "what_was_missed": ["You failed to consider Business Flex Credit."]}
    adapter = scripted_adapter([json.dumps(incorrect)] * 2)
    with pytest.raises(AIServiceError) as error:
        OllamaCoachAgent(adapter).evaluate(build_coaching_context(session, content))
    assert error.value.category == "coach_grounding"
    assert len(adapter.calls) == 2


def test_actual_product_discussion_can_be_critiqued_even_when_not_selected(
    content, interviews, recommendations, scripted_adapter
):
    session = interviews.create_session("maryam")
    session = interviews.record_student_message(session, "Would Business Flex Credit work?")
    session = interviews.record_client_response(session, "I decline interest-bearing credit.")
    session = interviews.end_interview(session)
    session = recommendations.submit_summary(session, "Requires Sharia-compliant arrangements.")
    session = recommendations.submit_recommendations(session, [ProductRecommendation(
        product_id="business-cash-management", justification="Visibility only, no funding.",
    )])
    feedback = {**FEEDBACK, "what_was_missed": ["The Business Flex Credit discussion did not explain its interest charges."]}
    adapter = scripted_adapter([json.dumps(feedback)])
    assert OllamaCoachAgent(adapter).evaluate(build_coaching_context(session, content)).what_was_missed
    assert len(adapter.calls) == 1
