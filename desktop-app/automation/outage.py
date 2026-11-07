"""
Telling a plan's network being down apart from a claim being refused.

Both arrive as "the claim was rejected", and the right answer is opposite:

  - the SWITCH is down   -> exclude the plan from this Rx, carry on, rebill
                            later when it is back up
  - the claim is REFUSED -> that is the plan's real answer; excluding it would
                            quietly bill the patient differently

So this matches the INFRASTRUCTURE wording, not the plan and not the token.
Arman saw `[E1] Host processing error` on CS and is not sure every plan words
it the same, which is the reason not to key off `CS:` or off a token name: the
phrase is the part that means "nobody answered", and it is not language a
coverage or refill-too-soon refusal uses.
"""

# Seen live on CS, 2026-11-07:
#   [E1] Host processing error.
#   REQUETE REJETEE PAR L'AIGUILLEUR
#   REQUEST REJECTED BY THE SWITCH
# The French line is the same sentence as the English one; both are kept
# because the window shows both and either may be what gets read.
OUTAGE_MARKS = (
    "host processing error",
    "rejected by the switch",
    "rejetee par l aiguilleur",
    "rejetee par l'aiguilleur",
)

# Wording that means the plan ANSWERED and said no. If any of this is present
# the claim is not an outage, whatever else the window says -- a refusal that
# happens to mention a host is still a refusal.
REFUSAL_MARKS = (
    "refill too soon",
    "too soon",
    "not covered",
    "coverage",
    "identical claim",
    "drug interaction",
    "patient not eligible",
    "not eligible",
    "invalid",
    "expired",
)


def _flat(text) -> str:
    return " ".join(str(text or "").split()).lower()


def is_switch_outage(text) -> bool:
    """
    Does this window say the plan's network did not answer? (bool).

    Read conservatively: a single refusal word anywhere wins, because getting
    this wrong in that direction bills a patient against a plan that genuinely
    said no.
    """
    flat = _flat(text)
    if not flat:
        return False
    if any(mark in flat for mark in REFUSAL_MARKS):
        return False
    return any(mark in flat for mark in OUTAGE_MARKS)


def describe(plan: str, text) -> str:
    """One line for the status stream and the log."""
    flat = _flat(text)
    which = next((m for m in OUTAGE_MARKS if m in flat), "a switch error")
    return (f"PLAN OUTAGE: {plan or 'the plan'} did not answer ({which}) -- "
            "excluding it from this Rx so the rest can bill. REBILL this one "
            "when the plan is back up.")
