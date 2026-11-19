import pytest
from pydantic import ValidationError

from bank_simulator.models import ProductRecommendation


def test_multiple_products_preserve_original_student_work(recommendations, completed_interview):
    summary = "  Mohamed needs separate goal savings and same-day emergency access.\n"
    submitted_summary = recommendations.submit_summary(completed_interview, summary)
    selections = [
        ProductRecommendation(product_id="goal-saver-account", justification="  A 12-month goal.\n"),
        ProductRecommendation(product_id="everyday-access-account", justification="For emergencies."),
    ]
    submitted = recommendations.submit_recommendations(submitted_summary, selections)

    assert submitted.session_id == completed_interview.session_id
    assert submitted.student_summary == summary
    assert submitted.selected_recommendations == tuple(selections)
    assert submitted.selected_recommendations[0].justification == "  A 12-month goal.\n"
    assert submitted.transcript == completed_interview.transcript
    assert completed_interview.student_summary is None
    assert submitted_summary.selected_recommendations == ()


def test_accepts_unsuitable_but_existing_products(recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "Mohamed needs a personal emergency fund.")
    choice = ProductRecommendation(product_id="business-flex-credit", justification="It sounds flexible.")
    submitted = recommendations.submit_recommendations(session, [choice])
    assert submitted.selected_recommendations == (choice,)


def test_rejects_nonexistent_product_without_changing_previous_submission(recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "Mohamed wants to start saving.")
    original = ProductRecommendation(product_id="goal-saver-account", justification="Dated goal.")
    session = recommendations.submit_recommendations(session, [original])
    unknown = ProductRecommendation(product_id="unknown-product", justification="It fits.")
    with pytest.raises(ValueError, match="Unknown product ID 'unknown-product'"):
        recommendations.submit_recommendations(session, [unknown])
    assert session.selected_recommendations == (original,)


def test_cannot_submit_student_work_before_end(interviews, recommendations):
    choice = ProductRecommendation(product_id="goal-saver-account", justification="Dated goal.")
    for session in (interviews.create_session(), interviews.create_session("mohamed")):
        with pytest.raises(ValueError, match="End the interview"):
            recommendations.submit_summary(session, "Mohamed wants to save.")
        with pytest.raises(ValueError, match="End the interview"):
            recommendations.submit_recommendations(session, [choice])


def test_recommendations_require_an_existing_summary(recommendations, completed_interview):
    choice = ProductRecommendation(product_id="goal-saver-account", justification="Dated goal.")
    with pytest.raises(ValueError, match="Submit a needs summary"):
        recommendations.submit_recommendations(completed_interview, [choice])


@pytest.mark.parametrize("summary", [None, "", " \n\t"])
def test_missing_or_blank_summary_is_rejected(recommendations, completed_interview, summary):
    with pytest.raises(ValueError, match="summary"):
        recommendations.submit_summary(completed_interview, summary)


def test_missing_or_duplicate_product_selection_is_rejected(recommendations, completed_interview):
    session = recommendations.submit_summary(completed_interview, "Mohamed is saving for a goal.")
    choice = ProductRecommendation(product_id="goal-saver-account", justification="Dated goal.")
    with pytest.raises(ValueError, match="at least one product"):
        recommendations.submit_recommendations(session, [])
    with pytest.raises(ValidationError, match="only once"):
        recommendations.submit_recommendations(session, [choice, choice])


def test_recommendation_requires_nonblank_justification():
    with pytest.raises(ValidationError, match="justification"):
        ProductRecommendation.model_validate({"product_id": "goal-saver-account"})
    with pytest.raises(ValidationError, match="justification"):
        ProductRecommendation(product_id="goal-saver-account", justification=" \n")
