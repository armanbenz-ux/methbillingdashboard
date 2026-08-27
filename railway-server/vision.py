import json
import os
import anthropic

MAIN_PROMPT = """\
You are reading a screenshot of a Kroll pharmacy software adjudication window.
These windows have a consistent layout: a green leaf icon and title bar at the top,
a bold centred header stating the claim result, an errors/warnings section below that,
and a pricing table with Submitted/Accepted/Difference/Discount rows showing
Cost, Markup, Fee, Mix Fee, SSC Fee, and Total columns. On the right side are
Total, Prev Paid, Plan Pays, Discount, and Pat Pays fields.

STEP 1 — IDENTIFY THE PLAN
Read the plan name ONLY from the body of the window — never from the title bar.
Look at these two spots:
  1. PRIMARY: The line "Errors, Warnings and Messages for [PLAN]" — this always shows the plan.
  2. SECONDARY: The bold centred header "The [PLAN] claim was accepted/rejected..." — also shows the plan.

The plan will be one of: ODB, BC, CS, GS, AHE.
If you genuinely cannot read the plan from the image, use ODB as a fallback.
The plan name will be used as the prefix in your token.

STEP 2 — READ THE BOLD CENTRED HEADER
This is the most important line in the window. It will say one of:
  "The [PLAN] claim was accepted"
  "The [PLAN] claim was accepted with price adjustments"
    Go to STEP 3
  "The [PLAN] claim was rejected because:"
    Go to STEP 4

STEP 3 — ACCEPTED FLOW
IMPORTANT: When the claim is accepted, ALL error codes ([ME], [CK], [DD], [LG], [DH],
[DJ], [D7], [KU], [DB] etc.) are purely informational warnings. Ignore them.

Decide the token from the PROMPT AND BUTTONS BELOW THE PRICING TABLE — NOT from the table
cells. The pricing table can show non-zero Cost/Markup/Fee differences even on a copay
window: Kroll sometimes rolls the whole difference into a single copay. Non-zero difference
cells do NOT by themselves mean a difference token. Read the bottom of the window:

  1) COPAY TO WAIVE
     Bottom text: "There was a copay amount of X.XX" and "Adjust it, if desired, and press
     Enter.", with an editable field showing the amount and an OK button (NO Yes/No buttons).
     Return: <PLAN>:COPAY:<amount>
     Return this WHENEVER this copay prompt is present, EVEN IF the pricing table shows
     non-zero Cost/Markup/Fee differences. There is no "Do you want to charge" question here.

  2) COPAY AUTO-WAIVED
     Bottom text: "The patient's copay of X.XX was discounted to 0.00". Pat Pays shows 0.00,
     no input field.
     Return: <PLAN>:COPAY_AUTO_WAIVED

  3) CHARGE-DIFFERENCE QUESTION
     Bottom shows the question "Do you want to charge the [Cost|Markup|Fee] difference of
     $X.XX to the patient?" with Yes / No buttons, and the named difference cell highlighted
     in YELLOW. ONLY in this case return a difference token, named by the question:
       Cost   -> <PLAN>:COST_DIFF
       Markup -> <PLAN>:MARKUP_DIFF
       Fee    -> <PLAN>:FEE_DIFF
     If several differences exist, the question names one at a time; return the one shown.

  4) CLEAN ACCEPT
     None of the above prompts present (no copay text, no Yes/No question); Submitted and
     Accepted rows match, Difference row empty.
     Return: <PLAN>:ACCEPTED

DECISION RULE (do not deviate):
  OK button + "copay amount" text           => COPAY (case 1)
  Yes/No buttons + "Do you want to charge"  => difference token (case 3)
  If you see an OK button and a copay amount, it is NEVER a difference token, no matter
  what the pricing table shows.

STEP 4 — REJECTED FLOW
The header says "The [PLAN] claim was rejected because:"
Below it: "Errors, Warnings and Messages for [PLAN]"
Error codes appear as bold text like [ME], [A3], [CJ], [C3], [D7] etc.
At the bottom: "The claim was rejected. Do you want to:"
with buttons: Back to the Rx / Skip this Plan / Bill Manually / Trouble / Cancel Rx
An "Interventions" button appears top-right when intervention is possible.

Read the error codes and apply this priority order:

  [ME] — "Possible drug/drug interaction. Please verify the drug interaction
     and use appropriate intervention code."
     Return: <PLAN>:REJECTED_DRUG_INTERACTION
     (Return this regardless of any other codes also present)

  [A3] — "Identical claim processed. A previous claim submitted by the provider
     for the same person, same DIN, and the same dispense date has already been paid."
     Also shown as: "IDENTICAL CLAIM HAS BEEN PROCESSED" in bold.
     Return: <PLAN>:REJECTED_IDENTICAL_CLAIM
     (Only if [ME] is not present)

  [D7] — "Refill too soon. Prescription is refilled too soon."
     Also shown as: "EARLY REFILL" in bold.
     Return: <PLAN>:REJECTED_REFILL_TOO_SOON
     (Only if [ME] and [A3] are not present)

  [CJ] — "Patient not covered by this plan."
     Return: <PLAN>:REJECTED_COVERAGE_ERROR
     (Only if [ME], [A3], [D7] are not present)

  [C3] — "Coverage expired before service."
     Return: <PLAN>:REJECTED_COVERAGE_ERROR
     (Only if [ME], [A3], [D7] are not present)

  None of the above — any other rejection reason
     Return: <PLAN>:REJECTED_OTHER

  Always ignore these codes — they never determine the token:
    [CK] Health card version code error
    [DD] Insufficient space to send all DUR warnings
    [LG] Lowest cost equivalent pricing
    [DH] Professional fee adjusted
    [MH] May be double doctoring

  Priority: [ME] > [A3] > [D7] > [CJ]/[C3] > OTHER

STEP 5 — PRICING NUMBERS  (only when your token ends in COST_DIFF, MARKUP_DIFF, or FEE_DIFF)
Read these five numbers directly off the window. Do NOT calculate anything — just read.
  cost_diff:   Difference row, Cost column     (blank cell = 0.00)
  markup_diff: Difference row, Markup column   (blank cell = 0.00)
  fee_diff:    Difference row, Fee column      (blank cell = 0.00)
  total_diff:  Difference row, Total column
  pat_pays:    right-hand "Pat Pays" field
The full Difference row is visible even though the question at the bottom names only one of
them — read every column, not just the one named in the question.

OUTPUT FORMAT
Reply with ONLY a JSON object. No markdown, no code fences, no prose. Numbers are JSON floats.
For a difference token (COST_DIFF/MARKUP_DIFF/FEE_DIFF), the pricing object MUST include
"charge_prompt": true, asserting the "Do you want to charge ... difference?" Yes/No question
is actually visible on screen. If that Yes/No question is NOT visible, do NOT return a
difference token — it is a COPAY (case 1) or ACCEPTED (case 4) window.
{"token":"AHE:COST_DIFF","pricing":{"cost_diff":0.05,"markup_diff":0.00,"fee_diff":6.99,"total_diff":7.04,"pat_pays":7.10,"charge_prompt":true}}
For every other token (ACCEPTED, COPAY, COPAY_AUTO_WAIVED, all REJECTED_*), pricing is null:
{"token":"ODB:ACCEPTED","pricing":null}
{"token":"GS:REJECTED_DRUG_INTERACTION","pricing":null}
"""

BC_INTERVENTION_PROMPT = """\
This is a Kroll intervention code selection window titled "Select an item from the list".
It shows a list of intervention codes with a Code column and Description column.
Find the item in the Description column that reads "Enter custom Free Form code"
(exact capitalisation: capital F on Free, capital F on Form).
Return ONLY that exact text so pywinauto can locate and double-click it.
If you cannot find it, return NOT_FOUND.
"""

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def analyse(image_b64: str, plan: str, context: str) -> dict:
    if context == "bc_intervention":
        prompt = BC_INTERVENTION_PROMPT
    else:
        prompt = MAIN_PROMPT

    message = _get_client().messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        timeout=30,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()

    if context == "bc_intervention":
        return {"token": raw, "pricing": None}

    # main context: expect JSON; be defensive about fences / bare tokens
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
        token = str(data.get("token", "")).strip()
        if not token:
            raise ValueError("empty token")
        return {"token": token, "pricing": data.get("pricing")}
    except Exception:
        # Model returned a bare token (old behavior) — safe: no pricing => per-key path.
        return {"token": cleaned, "pricing": None}
