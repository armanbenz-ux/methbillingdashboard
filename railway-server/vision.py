import os
import anthropic

MAIN_PROMPT_TEMPLATE = """\
You are reading a screenshot of a Kroll pharmacy software adjudication window.
These windows have a consistent layout: a green leaf icon and title bar at the top,
a bold centred header stating the claim result, an errors/warnings section below that,
and a pricing table with Submitted/Accepted/Difference/Discount rows showing
Cost, Markup, Fee, Mix Fee, SSC Fee, and Total columns. On the right side are
Total, Prev Paid, Plan Pays, Discount, and Pat Pays fields.

STEP 1 — IDENTIFY THE PLAN
The dashboard has selected plan: {plan}

To confirm the exact plan for THIS window, look at these two spots IN THE BODY OF THE WINDOW:
  1. PRIMARY: The line "Errors, Warnings and Messages for [PLAN]" — this always shows the plan.
  2. SECONDARY: The bold centred header "The [PLAN] claim was accepted/rejected..." — also shows the plan.

Use the plan name you read from the image. These two spots are the most reliable.
The window title bar is unreliable — do not use it to determine the plan.
If you cannot read the plan from the image at all, use {plan} as a fallback.
The plan name (ODB/BC/CS/GS/AHE) will be used as the prefix in your token.

STEP 2 — READ THE BOLD CENTRED HEADER
This is the most important line in the window. It will say one of:
  "The [PLAN] claim was accepted"
  "The [PLAN] claim was accepted with price adjustments"
    Go to STEP 3
  "The [PLAN] claim was rejected because:"
    Go to STEP 4

STEP 3 — ACCEPTED FLOW
IMPORTANT: When the claim is accepted, ALL error codes shown in the
"Errors, Warnings and Messages" section ([ME], [CK], [DD], [LG], [DH],
[DJ], [D7], [KU], [DB] etc.) are purely informational warnings.
Ignore them completely — they do not affect your token.

Look for these visual cues in order from top to bottom of the window:

  A) COST DIFFERENCE
     Visual: The pricing table shows the Submitted Cost row and Accepted Cost row
     with DIFFERENT values. The Difference row has a non-zero value highlighted
     in YELLOW. Below the pricing table is the question:
     "Do you want to charge the Cost difference of $X.XX to the patient?"
     with a field showing the amount, and Yes / No buttons.
     Return: <PLAN>:COST_DIFF

  B) FEE DIFFERENCE (never appears on ODB — only BC, CS, GS, AHE)
     Visual: Same pricing table layout but the Fee column shows different
     Submitted/Accepted values highlighted in YELLOW. The question reads:
     "Do you want to charge the Fee difference of $X.XX to the patient?"
     with Yes / No buttons.
     Return: <PLAN>:FEE_DIFF

  C) COPAY TO WAIVE
     Visual: Below the pricing table, the text reads:
     "There was a copay amount of X.XX"
     followed by: "Adjust it, if desired, and press Enter."
     with an editable blue input field showing the copay amount, and an OK button.
     The Pat Pays field on the right will show the copay amount.
     Return: <PLAN>:COPAY:<amount>   e.g. ODB:COPAY:2.00 or BC:COPAY:3.99

  D) COPAY AUTO-WAIVED BY KROLL
     Visual: Below the pricing table, the text reads:
     "The patient's copay of X.XX was discounted to 0.00"
     The Discount field on the right shows the waived amount. Pat Pays shows 0.00.
     No input field visible. Kroll has already applied the discount.
     Return: <PLAN>:COPAY_AUTO_WAIVED

  E) CLEAN ACCEPT — none of the above present
     Visual: Pricing table Submitted and Accepted rows show identical values.
     Difference row is empty. No question text below the table.
     No copay text visible anywhere in the window.
     Return: <PLAN>:ACCEPTED

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

Reply with ONLY the single token — nothing else, no punctuation, no explanation.
Example valid responses: ODB:ACCEPTED  BC:COST_DIFF  GS:REJECTED_DRUG_INTERACTION
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


def analyse(image_b64: str, plan: str, context: str) -> str:
    if context == "bc_intervention":
        prompt = BC_INTERVENTION_PROMPT
    else:
        prompt = MAIN_PROMPT_TEMPLATE.format(plan=plan)

    message = _get_client().messages.create(
        model="claude-haiku-4-5",
        max_tokens=64,
        timeout=15,
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

    token = message.content[0].text.strip()
    return token
