"""Mini world simulator: stateful tools with side-effect flags.

Mirrors ToolSandbox's stateful-tool interface (name, args -> state mutation
+ result). On the real pilot these are replaced by ToolSandbox's own tools
(A6 selection); the runner/scorer stack is unchanged.
"""

def _set_alarm(state, args):
    state["alarm"] = args["time"]
    return {"ok": True, "alarm": args["time"]}

def _send_message(state, args):
    state.setdefault("messages", []).append({"to": args["to"], "text": args["text"]})
    return {"ok": True, "sent_to": args["to"]}

def _add_contact(state, args):
    state.setdefault("contacts", {})[args["name"]] = args["phone"]
    return {"ok": True}

def _create_event(state, args):
    state.setdefault("events", []).append({"title": args["title"], "day": args["day"]})
    return {"ok": True, "title": args["title"]}

def _cancel_event(state, args):
    state["events"] = [e for e in state.get("events", []) if e["title"] != args["title"]]
    return {"ok": True}

def _check_calendar(state, args):
    return {"events": list(state.get("events", []))}

def _get_time(state, args):
    return {"time": "2026-08-11T06:30:00"}


TOOLS = {
    "set_alarm":      {"side_effect": True,  "fn": _set_alarm},
    "send_message":   {"side_effect": True,  "fn": _send_message},
    "add_contact":    {"side_effect": True,  "fn": _add_contact},
    "create_event":   {"side_effect": True,  "fn": _create_event},
    "cancel_event":   {"side_effect": True,  "fn": _cancel_event},
    "check_calendar": {"side_effect": False, "fn": _check_calendar},
    "get_time":       {"side_effect": False, "fn": _get_time},
}
