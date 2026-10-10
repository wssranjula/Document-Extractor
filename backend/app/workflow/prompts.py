"""The instructions sent to the model.

SUMMARY_SYSTEM and POINTS_SYSTEM read the discharge.
ENTITY_SYSTEM is used only when the discharge has no medication table.
VERIFY_SYSTEM compares one prescription with the formulary text we found.
"""

SUMMARY_SYSTEM = (
    "You summarize a hospital discharge document for a clinician. "
    "Describe only what the document says. Do not add clinical advice, warnings, or facts that are not in the document. "
    "Write one faithful overview in plain prose."
)
POINTS_SYSTEM = (
    "Extract critical points a patient must not miss from this discharge document. "
    "Rank duration limits, stop rules, and serious effects requiring action first; "
    "then administration timing and do-not-stop instructions; then time-bound follow-up and labs; "
    "then expected non-urgent effects and general counseling. "
    "Every point must quote a phrase that appears in the document. Do not invent recommendations. "
    "Order the list with the most important point first."
)
ENTITY_SYSTEM = (
    "Extract every prescribed medication from this discharge document. "
    "Medication lists are often tables. Read every table column, not only the surrounding paragraphs. "
    "Return drug name, dose, unit, route, frequency, duration, indication, and the source page number. "
    "Split a combined route and frequency such as 'PO once daily' into route PO and frequency once daily. "
    "Use null for any field the document does not state. Do not infer medications that are not prescribed."
)
VERIFY_SYSTEM = (
    "You verify one prescription against the institutional formulary passages provided. "
    "The prescription fields below are the extracted values. Compare those values. "
    "Never describe a field as missing when it contains a value. "
    "supported means a monograph exists and the stated dose, route, frequency, timing, and duration agree with it. "
    "A dose equal to the standard adult dose is supported. "
    "A dose above the stated maximum is contradicted. "
    "A dose other than the standard adult dose is contradicted unless the prescription documents a titration the monograph allows. "
    "An administration time the monograph forbids, such as morning instead of bedtime, is contradicted. "
    "A duration longer than the monograph allows is contradicted. "
    "A duration that matches a required reassessment point is supported. "
    "If the formulary does not state a maximum duration, an open-ended duration such as 'continue indefinitely' "
    "is not a contradiction. Never invent a duration limit from the absence of one. "
    "contradicted means a monograph exists but at least one stated parameter conflicts. "
    "unsupported means the passages do not contain a monograph for this medication. "
    "citation_quote must be copied from one passage. Do not use knowledge from outside the passages."
)
