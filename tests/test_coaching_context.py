import pytest
from pydantic import ValidationError

from bank_simulator.models import CoachFeedback, ProductRecommendation
from bank_simulator.services.coaching_context import build_coaching_context


@pytest.mark.parametrize("client_id, other_client_id", [("maryam", "mohamed"), ("mohamed", "maryam")])
def test_context_includes_full_transcript_catalogue_and_submissions(
    client_id, other_client_id, content, interviews, recommendations
):
    session = interviews.create_session(client_id)
    session = interviews.record_student_message(session, "What brings you in today?")
    session = interviews.record_client_response(session, "I'd like to review my options.")
    session = interviews.record_student_message(session, "Which concern is most urgent?")
    session = interviews.end_interview(session)
    summary = "  I would follow up about access to funds.\n"
    choice = ProductRecommendation(product_id="everyday-access-account", justification="Access to funds.")
    session = recommendations.submit_summary(session, summary)
    session = recommendations.submit_recommendations(session, [choice])

    context = build_coaching_context(session, content)
    _, expected_needs = content.get_private_client(client_id)
    _, other_needs = content.get_private_client(other_client_id)
    assert context.client_profile == content.get_client(client_id)
    assert context.hidden_needs == expected_needs
    assert set(context.hidden_needs.private_financial_facts).isdisjoint(other_needs.private_financial_facts)
    assert context.transcript == session.transcript
    assert len(context.transcript) == 3
    assert context.products == content.list_products()
    assert context.student_summary == summary
    assert context.recommendations == (choice,)


def test_context_requires_a_finished_interview_and_recommendations(
    content, interviews, recommendations, completed_interview
):
    with pytest.raises(ValueError, match="End the interview"):
        build_coaching_context(interviews.create_session("mohamed"), content)
    with pytest.raises(ValueError, match="Submit a needs summary and product recommendations"):
        build_coaching_context(completed_interview, content)

    session = recommendations.submit_summary(completed_interview, "Mohamed wants to save.")
    with pytest.raises(ValueError, match="Submit a needs summary and product recommendations"):
        build_coaching_context(session, content)


def test_context_rejects_an_unknown_product_from_a_restored_session(content, recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "Mohamed wants to save.")
    outdated = ProductRecommendation(product_id="removed-product", justification="It fits.")
    session = session.validated_update(selected_recommendations=(outdated,))
    with pytest.raises(ValidationError, match="unknown product ID 'removed-product'"):
        build_coaching_context(session, content)


def test_feedback_requires_all_three_sections():
    with pytest.raises(ValidationError, match="what_was_missed"):
        CoachFeedback.model_validate({"what_went_well": ["Asked about timing."], "how_to_improve": []})

    feedback = CoachFeedback(
        what_went_well=("Asked about timing.",),
        what_was_missed=(),
        how_to_improve=("Ask a follow-up question about access to funds.",),
    )
    assert CoachFeedback.model_validate_json(feedback.model_dump_json()) == feedback
