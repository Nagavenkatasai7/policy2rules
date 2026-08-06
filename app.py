"""policy2rules - turn coverage policy text into executable rules."""

import json
import os
import pathlib

import streamlit as st
from openai import OpenAI

def load_env():
    # no python-dotenv dep, so read .env from here or one dir up; a real env var still wins
    here = pathlib.Path(__file__).resolve().parent
    for f in (here / ".env", here.parent / ".env"):
        lines = f.read_text().splitlines() if f.exists() else []
        for key, sep, val in (line.partition("=") for line in lines):
            if sep and not key.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), val.strip().strip("\"'"))
    try:
        # streamlit cloud passes secrets through st.secrets, and raises if there is no secrets file
        os.environ.setdefault("OPENAI_API_KEY", st.secrets["OPENAI_API_KEY"])
    except Exception:
        pass


load_env()

SAMPLES = pathlib.Path(__file__).parent / "samples"
DEMO = not os.getenv("OPENAI_API_KEY")

MOCK_CLAIMS = [
    {"claim_id": "CLM-1001", "age": 54, "diagnosis_code": "E11.9", "procedure_code": "K0554",
     "insulin_regimen": "pump", "daily_bg_tests": 5, "prior_therapy_failed": True, "visit_within_6mo": True},
    {"claim_id": "CLM-1002", "age": 15, "diagnosis_code": "E10.9", "procedure_code": "K0554",
     "insulin_regimen": "mdi", "daily_bg_tests": 6, "prior_therapy_failed": True, "visit_within_6mo": True},
    {"claim_id": "CLM-1003", "age": 47, "diagnosis_code": "E11.65", "procedure_code": "A4239",
     "insulin_regimen": "mdi", "daily_bg_tests": 6, "prior_therapy_failed": False, "visit_within_6mo": True},
    {"claim_id": "CLM-1004", "age": 18, "diagnosis_code": "E13.9", "procedure_code": "E2103",
     "insulin_regimen": "mdi", "daily_bg_tests": 3, "prior_therapy_failed": True, "visit_within_6mo": True},
]

SUMMARY_SYSTEM = (
    "You are a utilization management analyst. Summarize the coverage policy the user pastes "
    "as markdown with these sections, in this order: Covered population, Coverage criteria, "
    "Exclusions, Relevant codes. Use short bullets, quote code values exactly as written, and "
    "do not invent criteria that are not in the text."
)

DIFF_SYSTEM = (
    "You compare two versions of a coverage policy. Output ONLY a markdown table with the columns "
    "Change type | Criterion | v1 | v2 | So what. Change type is Added, Removed, or Modified. "
    "One row per change, and the So what cell is a single line on how the change affects who gets "
    "approved. Ignore pure wording changes that do not move a criterion."
)

RULES_SYSTEM = (
    "You convert a coverage policy into executable claim rules. Return JSON only, no prose, with a "
    'top-level key "rules" holding an ordered list. Each rule is '
    '{"id": "R1", "description": "short human label", "source": "the numbered section of the policy '
    'this rule comes from, exactly as numbered, e.g. 1.4", "conditions": [{"field": "...", '
    '"operator": "...", "value": ...}], "decision": "APPROVE" or "DENY", "denial_reason": "text '
    'shown when the rule fires, empty string for APPROVE rules"}. '
    "The source must be the number of the section whose text the conditions encode, taken from the "
    "policy and never renumbered to close a gap left by a section you skipped. The denial_reason "
    "states what the claim failed and names that same section, e.g. 'Beneficiary is under 18, "
    "criterion 1.2 requires 18 or older' - never phrase it as the criterion being met. "
    "Allowed operators: ==, !=, <, <=, >, >=, in, not_in. For in/not_in the value must be a list "
    "and the claim value is tested for membership. Allowed fields only: age (int), diagnosis_code (str), "
    "procedure_code (str), insulin_regimen (str), daily_bg_tests (int), prior_therapy_failed (bool), "
    "visit_within_6mo (bool). Claims are coded, not prose: diagnosis_code and procedure_code hold codes "
    'exactly as the policy writes them, and insulin_regimen is one of "pump", "mdi", "oral_only", '
    '"diet_only", "none" - never invent other values for these fields. '
    "A rule fires when all of its conditions are true and the first firing rule "
    "decides, so put DENY rules first and end with a catch-all APPROVE rule with an empty conditions list. "
    "Write one DENY rule for each numbered coverage criterion that the allowed fields can express, and "
    "no rules beyond those. If a criterion has no matching field, omit it entirely rather than testing "
    "some other field, and never write two rules on the same field for different criteria. "
    "The conditions in a rule are ANDed, there is no OR, so never repeat a field "
    "with == or != to mean "
    'any of several values - use one in/not_in condition instead. To deny a beneficiary who is not on '
    'insulin, the only correct form is {"field": "insulin_regimen", "operator": "in", "value": '
    '["oral_only", "diet_only", "none"]}.'
)

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def canned(name):
    return json.loads((SAMPLES / name).read_text())


def call_llm(system, user, json_mode=False):
    client = OpenAI()
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,  # demo needs the same rules every run, not creative ones
        **kwargs,
    )
    # chat.completions returns choices, grab [0]
    return r.choices[0].message.content


def get_summary(policy):
    if DEMO:
        return canned("canned_summary.json")["text"]
    return call_llm(SUMMARY_SYSTEM, policy)


def diff_policies(v1, v2):
    if DEMO:
        return canned("canned_diff.json")["text"]
    return call_llm(DIFF_SYSTEM, f"POLICY V1\n{v1}\n\nPOLICY V2\n{v2}")


def extract_rules(policy):
    if DEMO:
        return canned("canned_rules.json")
    raw = call_llm(RULES_SYSTEM, policy, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # json_mode usually prevents fences, strip them once before giving up
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return raw


def evaluate_claim(claim: dict, rules: list) -> tuple[str, str, str]:
    for rule in rules:
        fired = True
        for cond in rule.get("conditions", []):
            if cond.get("field") not in claim:
                fired = False
                break
            op = OPS.get(cond.get("operator"))
            try:
                ok = bool(op(claim[cond["field"]], cond.get("value")))
            except TypeError:
                # str vs int compares and unknown operators count as not matching
                ok = False
            if not ok:
                fired = False
                break
        if fired:
            cite = rule.get("source") or "not cited"
            if rule.get("decision") == "DENY":
                return "DENY", rule.get("denial_reason", ""), cite
            return "APPROVE", rule.get("description", ""), cite
    # plain "-" would render as a markdown bullet in st.table
    return "APPROVE", "no rule triggered", "none"


st.set_page_config(page_title="policy2rules", layout="wide")
st.title("policy2rules")
st.caption("Paste a coverage policy, get a readable summary, a version diff, and rules you can run claims through.")

if DEMO:
    st.warning("OPENAI_API_KEY not set. Running in demo mode with canned responses from samples/.")

for key in ("sum_text", "v1_text", "v2_text", "rules_text"):
    st.session_state.setdefault(key, "")

tabs = st.tabs(["Summarize", "Compare versions", "Policy to rules"])

with tabs[0]:
    if st.button("Load sample", key="sum_load"):
        # text_area with a key reads session_state, so write it before the widget renders
        st.session_state["sum_text"] = (SAMPLES / "sample_policy_v2.txt").read_text()
    st.text_area("Policy text", key="sum_text", height=280)
    if st.button("Summarize", key="sum_go"):
        with st.spinner("Summarizing"):
            # buttons are True for one run only, so stash the output to survive later reruns
            st.session_state["sum_out"] = get_summary(st.session_state["sum_text"])
    if st.session_state.get("sum_out"):
        st.markdown(st.session_state["sum_out"])

with tabs[1]:
    if st.button("Load sample", key="diff_load"):
        st.session_state["v1_text"] = (SAMPLES / "sample_policy_v1.txt").read_text()
        st.session_state["v2_text"] = (SAMPLES / "sample_policy_v2.txt").read_text()
    left, right = st.columns(2)
    with left:
        st.text_area("Policy v1", key="v1_text", height=280)
    with right:
        st.text_area("Policy v2", key="v2_text", height=280)
    if st.button("Compare", key="diff_go"):
        with st.spinner("Comparing"):
            st.session_state["diff_out"] = diff_policies(st.session_state["v1_text"], st.session_state["v2_text"])
    if st.session_state.get("diff_out"):
        st.markdown(st.session_state["diff_out"])

with tabs[2]:
    if st.button("Load sample", key="rules_load"):
        st.session_state["rules_text"] = (SAMPLES / "sample_policy_v2.txt").read_text()
    st.text_area("Policy text", key="rules_text", height=280)
    if st.button("Extract rules", key="rules_go"):
        with st.spinner("Extracting rules"):
            st.session_state["rules_out"] = extract_rules(st.session_state["rules_text"])
    result = st.session_state.get("rules_out")
    if result is not None:
        if isinstance(result, str):
            st.info("Model output was not valid JSON, showing it raw.")
            st.code(result)
        else:
            with st.expander("Rules JSON"):
                st.json(result)
            rows = []
            for claim in MOCK_CLAIMS:
                decision, reason, cite = evaluate_claim(claim, result.get("rules", []))
                rows.append({"Claim": claim["claim_id"], "Decision": decision,
                             "Policy section": cite, "Reason": reason})
            st.subheader("Mock claims")
            st.table(rows)
