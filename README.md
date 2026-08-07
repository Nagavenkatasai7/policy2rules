# policy2rules

Hackathon proof of concept: turn a health insurance coverage policy into machine-executable rules
with an LLM, then run claims against those rules in plain Python.

**Live demo:** https://policy2rules.streamlit.app (runs in demo mode against built-in samples when
no API key is configured, so every tab works)

## Deliverables

All files are in the [`deliverables/`](deliverables) folder. GitHub does not preview Word,
PowerPoint, or video files in the browser - use the direct links below (or the Raw / download
button on any file page) to download and open them.

| Deliverable | Direct download |
|---|---|
| Written report | [Chennu_Content_Management_Health_Care.docx](https://raw.githubusercontent.com/Nagavenkatasai7/policy2rules/main/deliverables/Chennu_Content_Management_Health_Care.docx) |
| Slide deck | [policy2rules_overview.pptx](https://raw.githubusercontent.com/Nagavenkatasai7/policy2rules/main/deliverables/policy2rules_overview.pptx) |
| Video presentation (4:59, MP4) | [policy2rules_presentation.mp4](https://raw.githubusercontent.com/Nagavenkatasai7/policy2rules/main/deliverables/policy2rules_presentation.mp4) |
| Resume (PDF, one page) | [NAGA VENKATA SAI CHENNU_Intern - Generative AI_Agentic AI_Research.pdf](https://raw.githubusercontent.com/Nagavenkatasai7/policy2rules/main/deliverables/NAGA%20VENKATA%20SAI%20CHENNU_Intern%20-%20Generative%20AI_Agentic%20AI_Research_20260807.pdf) |
| Proof of concept | `app.py` in this repo, deployed at the live demo link above |

Prepared by Naga Venkata Sai Chennu, George Mason University.

Three tabs:

1. **Summarize** - structured summary of a pasted policy: covered population, criteria, exclusions, codes.
2. **Compare versions** - change report between two policy revisions, with a one-line "so what" per change.
3. **Policy to rules** - the LLM emits a JSON rules object; `evaluate_claim()` runs four mock claims
   against it with no LLM involved. Each decision cites the policy section it came from.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

The API key is read from `OPENAI_API_KEY`, via a real environment variable, a `.env` file in this
folder or its parent, or Streamlit secrets. With no key set the app runs in demo mode against the
canned responses in `samples/`, so every tab still works offline.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. At share.streamlit.io, create an app pointing at that repo, branch `main`, file `app.py`.
3. Optional, in Advanced settings > Secrets, add:

   ```
   OPENAI_API_KEY = "sk-..."
   ```

   Leave Secrets empty to deploy in demo mode. Anyone with the app URL can spend against a key
   placed here, since the app has no authentication.

## Samples

`sample_policy_v1.txt` and `sample_policy_v2.txt` are a simplified Medicare-style LCD for continuous
glucose monitors. v2 tightens one criterion (fingerstick tests 3/day to 4/day, section 1.4) and adds
one (documented failure of prior therapy, section 1.7). The mock claims are built to trip both.
