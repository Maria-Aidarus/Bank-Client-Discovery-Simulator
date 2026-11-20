"""Streamlit presentation only. Student views use public content and observed results."""

import streamlit as st

from ..data_loader import ContentLoadError
from ..models import InterviewStatus, MessageRole, ProductRecommendation
from ..services.content_service import ContentService
from .controller import (
    MAX_JUSTIFICATION_CHARS, MAX_MESSAGE_CHARS, MAX_QUESTIONS, MAX_REQUESTS,
    MAX_SUMMARY_CHARS, WebController, Workspace,
)
from .export import student_report


STYLES = """<style>
.stApp {
    --academic-red: #C41230; --rose-tint: #F9E8EC;
    --academic-green: #2F5D50; --green-tint: #EAF4F0;
    --academic-text: #1F2D3D; --muted-text: #5B6777; --light-border: #D9E0E6;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: var(--academic-text); background: #FFFFFF;
}
.stApp button, .stApp input, .stApp textarea, .stApp p, .stApp li, .stApp label,
.stApp [data-testid="stText"], .stApp [data-testid="stMarkdownContainer"] {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}
.block-container {max-width: 1040px; padding-top: 3.75rem; padding-bottom: 3rem;}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    font-family: Georgia, "Times New Roman", serif;
    font-weight: 500; letter-spacing: 0; color: var(--academic-text);
}
.stApp h1 {font-size: clamp(1.7rem, 2.4vw, 2.1rem); line-height: 1.25; padding-bottom: .35rem;}
.stApp h2 {font-size: 1.6rem;}
.stApp h3 {font-size: 1.35rem; line-height: 1.35;}
.stApp p, .stApp [data-testid="stText"] {line-height: 1.65;}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p {
    color: var(--muted-text); opacity: 1;
}
.stApp hr {border-color: var(--light-border); margin: 1.1rem 0;}
[data-testid="stHeader"] {background: #FFFFFF;}
#MainMenu, footer {display: none;}
.stApp button {border-radius: 5px; box-shadow: none;}
.stApp button:focus-visible {outline: 2px solid var(--academic-red); outline-offset: 3px;}

.journey {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .5rem;
          padding: 0; margin: .8rem 0 1.8rem; list-style: none;}
.journey li {display: flex; align-items: center; gap: .5rem; padding: .6rem .8rem; margin: 0;
             background: #FFFFFF; border: 1px solid var(--light-border); border-radius: 24px;
             color: var(--muted-text); font-size: .8rem; line-height: 1.3;}
.journey span {font-size: .62rem; letter-spacing: .03em; white-space: nowrap;}
.journey .current {background: var(--rose-tint); border-color: #E8BFC8;
                   color: var(--academic-red); font-weight: 600;}
.journey .complete {background: var(--green-tint); border-color: #CEDFD7; color: var(--academic-green);}

[data-testid="stSidebar"] {background: #FFFFFF; border-right: 1px solid var(--light-border);}
[data-testid="stSidebarUserContent"] {padding: .75rem 0;}
[data-testid="stSidebar"] h3 {font-size: 1.2rem;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: .7rem;}
[data-testid="stSidebar"] button {min-height: 2.2rem; padding: .35rem .6rem; font-size: .82rem;}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    border: 1px solid var(--light-border); border-radius: 5px; background: #FFFFFF;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {padding: .4rem .55rem;}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {font-size: .81rem; line-height: 1.4;}
[data-testid="stSidebar"] [data-testid="stText"] {font-size: .85rem;}

[class*="st-key-client_card_"] {border: 1px solid var(--light-border); border-radius: 7px;
                               padding: 1.45rem; background: #FFFFFF;}
[class*="st-key-client_card_"] h3 {font-size: 1.5rem;}
[class*="st-key-client_card_"] [data-testid="stCaptionContainer"] {font-size: .82rem;}
.st-key-meeting_context {border-left: 2px solid var(--light-border); padding: .15rem 0 .15rem 1rem;}
[data-testid="stChatMessage"] {border: 0; border-radius: 4px; padding: 1rem 1.1rem;
                              box-shadow: none; background: #FFFFFF;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {background: #F7F8FA;}
[data-testid="stChatMessageAvatarUser"] {background: #EDF0F3; color: var(--muted-text);}
[data-testid="stChatInput"] {border-radius: 6px;}
[data-testid="stMain"] [data-testid="stExpander"] details {
    border: 0; border-bottom: 1px solid var(--light-border); border-radius: 0;
}
[data-testid="stMain"] [data-testid="stExpander"] summary {padding: .75rem .1rem;}
[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelectTagsContainer"] [data-tag] {background: var(--rose-tint); color: var(--academic-red);}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
[data-testid="stMultiSelectTagsContainer"] [data-tag] * {color: inherit;}

.st-key-feedback_strengths, .st-key-feedback_gaps, .st-key-feedback_improvements {
    border: 1px solid var(--light-border); border-radius: 6px; padding: 1.1rem 1.35rem; margin-bottom: .5rem;
}
.st-key-feedback_strengths {background: var(--green-tint); border-color: #D6E4DD;}
.st-key-feedback_gaps {background: var(--rose-tint); border-color: #EED5DC;}
.st-key-feedback_improvements {background: #F6F9F7;}
.st-key-feedback_strengths h3 {color: var(--academic-green);}
.st-key-feedback_gaps h3 {color: #9E1630;}
.st-key-feedback_strengths [data-testid="stVerticalBlock"],
.st-key-feedback_gaps [data-testid="stVerticalBlock"],
.st-key-feedback_improvements [data-testid="stVerticalBlock"] {gap: .65rem;}

@media (max-width: 640px) {
    /* Reserve a scrollable area above mobile hosting badges on client selection.
       This styles our app, without hiding or targeting the hosting controls. */
    .stApp:has([class*="st-key-client_card_"]) {
        bottom: calc(3.5rem + env(safe-area-inset-bottom, 0px));
    }
    .block-container {padding-top: 3.5rem;}
    .journey {grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .45rem;}
    .journey li {border-radius: 8px; padding: .55rem .65rem; font-size: .78rem;}
    .journey span {font-size: .57rem;}
    [class*="st-key-client_card_"] {padding: 1.2rem;}
    .st-key-feedback_strengths, .st-key-feedback_gaps, .st-key-feedback_improvements {padding: 1rem;}
    .stApp [data-testid="stButton"] button,
    .stApp [data-testid="stDownloadButton"] button,
    .stApp [data-testid="stFormSubmitButton"] button {min-height: 44px;}
}
</style>"""


def _progress(stage: int) -> None:
    labels = ("Select client", "Interview", "Recommend", "Coach feedback")
    items = []
    for index, label in enumerate(labels, 1):
        css = "current" if index == stage else "complete" if index < stage else ""
        aria = ' aria-current="step"' if index == stage else ""
        items.append(f'<li class="{css}"{aria}><span>STEP {index:02d}</span>{label}</li>')
    st.markdown('<ol class="journey" aria-label="Interview progress">' + "".join(items) + '</ol>', unsafe_allow_html=True)


def _catalogue(content: ContentService) -> None:
    st.subheader("Product catalogue")
    st.caption("Five fictional products for this exercise. Explore their terms before making your own recommendations.")
    for product in content.list_products():
        with st.expander(product.name):
            st.write(product.description)
            for label, values in (
                ("Features", product.key_features), ("Benefits", product.benefits),
                ("Eligibility", product.eligibility_requirements), ("Limitations", product.limitations),
                ("Intended uses", product.suitable_use_cases), ("Restrictions and unsuitable uses", product.unsuitable_use_cases),
            ):
                st.markdown(f"**{label}**")
                for value in values:
                    st.text("• " + value)


def _sidebar(controller: WebController) -> None:
    state = controller.state
    with st.sidebar:
        st.divider()
        if state.session:
            profile = controller.content.get_client(state.session.client_id)
            st.markdown(f"**{profile.name}**")
            st.caption(profile.occupation)
            st.caption(f"{state.question_count}/{MAX_QUESTIONS} questions · {state.requests}/{MAX_REQUESTS} AI requests")
            if st.button("Restart interview", key="restart", disabled=state.busy, width="stretch",
                         help="Discard this attempt and start fresh with the same client."):
                controller.start(profile.id)
                st.rerun()
            if st.button("Choose another client", key="choose_another", disabled=state.busy, width="stretch",
                         help="Discard this attempt and return to client selection."):
                controller.choose_another()
                st.rerun()
            st.download_button(
                "Download interview report", student_report(state.session, state.feedback, controller.content),
                file_name=f"bank-interview-{profile.id}-{str(state.session.session_id)[:8]}.json",
                mime="application/json", on_click="ignore", width="stretch", key="download_report",
                help="Includes this conversation, your submitted work, and any completed feedback.",
            )
            st.divider()
        _catalogue(controller.content)
        st.divider()
        st.caption("Training scenarios and products are fictional. AI feedback can make mistakes; compare it with the interview and catalogue.")


def _selection(controller: WebController) -> None:
    st.subheader("Select a client")
    st.write("Read the background, then begin your interview.")
    columns = st.columns(2)
    for index, client in enumerate(controller.content.list_clients()):
        column = columns[index % 2]
        with column, st.container(border=False, key=f"client_card_{client.id}"):
            st.caption(client.occupation)
            st.subheader(client.name)
            st.write(client.background)
            st.write(client.public_financial_situation)
            if st.button("Start interview", key=f"start_{client.id}", type="primary"):
                controller.start(client.id)
                st.rerun()
    st.caption("Your work stays in this browser session. Download your report before leaving or starting another interview.")


def _transcript(state: Workspace, name: str) -> None:
    for message in state.session.transcript:
        student = message.role is MessageRole.STUDENT
        with st.chat_message("user" if student else name):
            st.caption("You" if student else name)
            st.text(message.content)


def _interview(controller: WebController) -> None:
    state = controller.state
    profile = controller.content.get_client(state.session.client_id)
    st.subheader(f"Interview with {profile.name.split()[0]}")
    with st.container(border=False, key="meeting_context"):
        st.caption("Meeting context")
        st.write(profile.interview_opening_context)
    st.caption("Ask in your own words. The product catalogue is available in the sidebar.")
    _transcript(state, profile.name)
    if not state.session.transcript:
        st.info("Start by asking your client what brought them to the meeting.")
    if state.error:
        st.error(state.error)
    if state.failed_question:
        with st.container(border=True):
            st.caption("UNANSWERED QUESTION · not added to the saved transcript")
            st.text(state.failed_question)
            if st.button("Retry question", key="retry_question", disabled=not state.can_send):
                with st.spinner(f"{profile.name.split()[0]} is responding…"):
                    controller.send(state.failed_question)
                st.rerun()
    if not state.can_send:
        st.info("You have reached this interview's question or request limit. End the interview to submit your recommendations.")
    if st.button("End interview & make recommendations", key="end_interview", disabled=state.busy):
        controller.end()
        st.rerun()
    message = st.chat_input("Ask your client a question", key=f"question_{state.session.session_id}",
                            max_chars=MAX_MESSAGE_CHARS, disabled=not state.can_send)
    if message:
        with st.chat_message("user"):
            st.caption("You")
            st.text(message)
        with st.spinner(f"{profile.name.split()[0]} is responding…"):
            controller.send(message)
        st.rerun()


def _recommendations(controller: WebController) -> None:
    state = controller.state
    session = state.session
    products = controller.content.list_products()
    st.subheader("Make your recommendation")
    st.write("Summarize the needs you discovered, select products, and explain your reasoning.")
    with st.expander("Review interview transcript"):
        _transcript(state, controller.content.get_client(session.client_id).name)
    prefix = f"work_{session.session_id}"
    previous_choices = {choice.product_id: choice.justification for choice in session.selected_recommendations}
    # Capture the previous widget values before Streamlit removes deselected widgets.
    # Drafts live outside widget keys so reselecting a product restores its exact text.
    for product in products:
        widget_key = f"{prefix}_why_{product.id}"
        if widget_key in st.session_state:
            state.justification_drafts[product.id] = st.session_state[widget_key]
    for product_id, justification in previous_choices.items():
        state.justification_drafts.setdefault(product_id, justification)

    # Regular widgets rerun on edits; the explicit submit button is the only AI trigger.
    summary = st.text_area("Financial needs summary", value=session.student_summary or "",
                           key=f"{prefix}_summary", max_chars=MAX_SUMMARY_CHARS, height=150)
    summary_error = st.empty()
    selected = st.multiselect("Recommended products", [product.id for product in products],
                              default=list(previous_choices),
                              format_func=lambda product_id: controller.content.get_product(product_id).name,
                              key=f"{prefix}_products", placeholder="Select at least one fictional product")
    selection_error = st.empty()
    justifications = {}
    justification_errors = {}
    for product_id in selected:
        product = controller.content.get_product(product_id)
        with st.container(key=f"justification_{product_id}"):
            justifications[product_id] = st.text_area(
                f"Why {product.name}?", value=state.justification_drafts.get(product_id, ""),
                key=f"{prefix}_why_{product_id}", max_chars=MAX_JUSTIFICATION_CHARS, height=110,
            )
            state.justification_drafts[product_id] = justifications[product_id]
            st.caption("Briefly explain why this product fits the client's needs. Mention any important limitations.")
            justification_errors[product_id] = st.empty()
    submitted = st.button("Submit & get coaching", key=f"{prefix}_submit", type="primary", disabled=state.busy)
    if submitted:
        missing_justifications = [product_id for product_id in selected if not justifications[product_id].strip()]
        if not summary.strip():
            summary_error.error("Enter a financial needs summary.")
        if not selected:
            selection_error.error("Select at least one product.")
        for product_id in missing_justifications:
            product = controller.content.get_product(product_id)
            justification_errors[product_id].error(f"Add a brief justification for {product.name}.")
        if summary.strip() and selected and not missing_justifications:
            try:
                controller.submit(summary, [ProductRecommendation(product_id=product_id, justification=justifications[product_id])
                                            for product_id in selected])
            except ValueError:
                st.error("Check your summary and selected product justifications, then submit again.")
            else:
                with st.spinner("Your coach is reviewing the interview and recommendations…"):
                    controller.coach()
                st.rerun()


def _feedback(controller: WebController) -> None:
    state = controller.state
    st.subheader("Your coaching feedback")
    st.caption("Use this feedback to plan your next interview. Check it against the conversation and fictional product terms.")
    if state.feedback is None:
        st.error(state.error or "Feedback has not been generated. Your interview and submission are saved in this session.")
        if st.button("Retry coaching", key="retry_coaching", type="primary",
                     disabled=state.busy or state.requests >= MAX_REQUESTS):
            with st.spinner("Your coach is reviewing your submitted work…"):
                controller.coach()
            st.rerun()
    else:
        for title, points, section_key in (
            ("What went well", state.feedback.what_went_well, "feedback_strengths"),
            ("What was missed", state.feedback.what_was_missed, "feedback_gaps"),
            ("How to improve", state.feedback.how_to_improve, "feedback_improvements"),
        ):
            with st.container(border=False, key=section_key):
                st.subheader(title)
                for point in points:
                    st.text("• " + point)
                if not points:
                    st.caption("No observations returned in this section.")
    with st.expander("Your submitted work"):
        st.markdown("**Financial needs summary**")
        st.text(state.session.student_summary)
        for choice in state.session.selected_recommendations:
            st.markdown(f"**{controller.content.get_product(choice.product_id).name}**")
            st.text(choice.justification)
    with st.expander("Review interview transcript"):
        _transcript(state, controller.content.get_client(state.session.client_id).name)
    if st.button("Revise submission", key="revise_submission", disabled=state.busy,
                 help="Edit your work. Submitting again requests new feedback and uses the same request allowance."):
        controller.revise()
        st.rerun()
    st.info("Download your interview report from the sidebar before restarting or leaving this session.")


def main() -> None:
    """Render one rerun; model calls occur only inside explicit action handlers."""
    st.set_page_config(page_title="Bank Client Discovery Simulator", layout="wide")
    st.markdown(STYLES, unsafe_allow_html=True)
    if "workspace" not in st.session_state:
        st.session_state.workspace = Workspace()
    try:
        content = ContentService()
    except (ContentLoadError, OSError, ValueError):
        st.error("The simulator content could not be loaded. Ask the administrator to check the data files.")
        return
    controller = WebController(st.session_state.workspace, content)
    _sidebar(controller)
    st.title("Bank Client Discovery Simulator")
    st.caption("Client interviews, financial discovery, and product suitability.")
    _progress(controller.state.stage)
    if controller.state.stage == 1:
        _selection(controller)
    elif controller.state.stage == 2:
        _interview(controller)
    elif controller.state.stage == 3:
        _recommendations(controller)
    else:
        _feedback(controller)
