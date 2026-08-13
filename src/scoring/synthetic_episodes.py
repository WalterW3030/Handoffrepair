"""A5/A9 — Synthetic scenarios with scripted source/target policies.

Two scenario families; five smoke episodes total. Source policy completes
the task correctly; target policy is weaker in controlled ways (wrong
recipient content, skipped steps) so B0 vs B1 columns produce divergent,
predictable scores for harness validation.

DAG edge semantics: achieving M_alarm gives 0.5 partial credit for
M_alarm_exact if the alarm is set but to the wrong time, etc.
"""

MORNING_DAG = {
    "milestones": [
        {"id": "M_alarm",   "predicate": {"alarm": "07:00"}, "weight": 1.0},
        {"id": "M_msg_bob", "predicate": {"messages.any.to": "bob"}, "weight": 1.0},
        {"id": "M_msg_late", "predicate": {"messages.any.text": "I'll be late"}, "weight": 1.0},
    ],
    "edges": [
        {"src": "M_msg_bob", "dst": "M_msg_late", "kind": "similar", "credit": 0.5},
    ],
    "minefields": [
        {"id": "F_wrong_recipient", "predicate": {"messages.any.to": "alice"}},
    ],
}

EVENT_DAG = {
    "milestones": [
        {"id": "M_event_created", "predicate": {"events.any.title": "dentist"}, "weight": 1.0},
        {"id": "M_old_cancelled", "predicate": {"old_meeting_present": False}, "weight": 1.0},
        {"id": "M_contact", "predicate": {"contacts.dentist_office": "555-0100"}, "weight": 1.0},
    ],
    # old_meeting_present / double_booking are DERIVED flags the runner adds to
    # every trajectory snapshot (see runner._derive).
    "edges": [],
    "minefields": [
        {"id": "F_double_booking", "predicate": {"double_booking": True}},
    ],
}

SOURCE_MORNING = [
    {"type": "tool_call", "tool": "get_time", "args": {}},
    {"type": "tool_call", "tool": "set_alarm", "args": {"time": "07:00"}},
    {"type": "tool_call", "tool": "send_message", "args": {"to": "bob", "text": "I'll be late"}},
    {"type": "message", "content": "Alarm set for 7am and Bob notified."},
]

# weaker target: sets alarm correctly but texts the wrong content to bob
TARGET_MORNING = [
    {"type": "tool_call", "tool": "set_alarm", "args": {"time": "07:00"}},
    {"type": "tool_call", "tool": "send_message", "args": {"to": "bob", "text": "on my way"}},
    {"type": "message", "content": "Done."},
]

SOURCE_EVENT = [
    {"type": "tool_call", "tool": "check_calendar", "args": {}},
    {"type": "tool_call", "tool": "cancel_event", "args": {"title": "old_meeting"}},
    {"type": "tool_call", "tool": "create_event", "args": {"title": "dentist", "day": "2026-08-12"}},
    {"type": "tool_call", "tool": "add_contact", "args": {"name": "dentist_office", "phone": "555-0100"}},
    {"type": "message", "content": "Dentist appointment scheduled, old meeting cancelled, contact saved."},
]

# weaker target: forgets to cancel the old meeting (double booking) and skips the contact
TARGET_EVENT = [
    {"type": "tool_call", "tool": "check_calendar", "args": {}},
    {"type": "tool_call", "tool": "create_event", "args": {"title": "dentist", "day": "2026-08-12"}},
    {"type": "message", "content": "Created the dentist event."},
]


def make_smoke_episodes():
    eps = []
    for i in (1, 2):
        eps.append({
            "episode_id": f"smoke_morning_{i}",
            "family": "morning",
            "system": "You are a helpful assistant with tool access.",
            "user": "Set an alarm for 7am and text Bob that I'll be late.",
            "initial_state": {"alarm": None, "messages": [], "contacts": {}, "events": []},
            "dag": MORNING_DAG,
            "source_script": SOURCE_MORNING,
            "target_script": TARGET_MORNING,
            "max_turns": 8,
        })
    for i in (1, 2, 3):
        eps.append({
            "episode_id": f"smoke_event_{i}",
            "family": "event",
            "system": "You are a helpful assistant with tool access.",
            "user": "Cancel my old_meeting, create a dentist appointment for tomorrow, and save the dentist office contact 555-0100.",
            "initial_state": {"alarm": None, "messages": [], "contacts": {},
                              "events": [{"title": "old_meeting", "day": "2026-08-12"}]},
            "dag": EVENT_DAG,
            "source_script": SOURCE_EVENT,
            "target_script": TARGET_EVENT,
            "max_turns": 10,
        })
    return eps


# ---- A5 verification fixtures: hand-computed scorer cases --------------------

VERIFY_DAG = {
    "milestones": [
        {"id": "A", "predicate": {"x": 1}, "weight": 1.0},
        {"id": "B", "predicate": {"y": 2}, "weight": 1.0},
    ],
    "edges": [{"src": "A", "dst": "B", "kind": "similar", "credit": 0.5}],
    "minefields": [{"id": "F", "predicate": {"z": 9}}],
}

VERIFY_CASES = [
    # (name, trajectory, expected)
    ("full_success",
     [{"x": 0}, {"x": 1, "y": 2}],
     {"success": True, "raw": 1.0, "milestones_hit": ["A", "B"], "partial_credit": {}, "minefields_hit": []}),
    ("partial_via_similar_edge",
     [{"x": 1}],
     {"success": False, "raw": 0.75, "milestones_hit": ["A"], "partial_credit": {"B": 0.5}, "minefields_hit": []}),
    ("minefield_hit",
     [{"x": 1, "y": 2, "z": 9}],
     {"success": False, "raw": 1.0, "milestones_hit": ["A", "B"], "partial_credit": {}, "minefields_hit": ["F"]}),
    ("nothing_achieved",
     [{"x": 0, "y": 0}],
     {"success": False, "raw": 0.0, "milestones_hit": [], "partial_credit": {}, "minefields_hit": []}),
]
