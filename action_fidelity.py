"""Conservative user-owned action-role constraints for explicit hand-pin events.

This module deliberately does not reinterpret free-form physical choreography.
It recognizes only unambiguous named A-pins-B's-hands commands, and matches
explicit H3 <Subject> statements. Unrecognized verbs remain under creative
freedom and are not assigned guessed roles.
"""
import re

_PIN = r"(?:pin(?:s|ned|ning)?|hold(?:s|ing)?\s+down|secur(?:e|es|ed|ing))"
_HAND = r"(?:hands?|wrists?|arms?)"


def explicit_pin_roles(direction, speaker_subject_map):
    """Extract known, explicit actor/target hand-pin relationships from Direction."""
    names = [(name, int(sid)) for name, sid in (speaker_subject_map or {}).items()
             if name and str(sid).isdigit() and name.casefold() != 'viewer']
    names.sort(key=lambda item: -len(item[0]))
    requirements = []
    for actor, actor_id in names:
        for target, target_id in names:
            if actor_id == target_id:
                continue
            # Never cross sentence/clause boundaries: actor must own the pin verb.
            pattern = (rf"(?<!\w){re.escape(actor)}(?!\w)"
                       rf"[^.!?,;]{{0,85}}?\b{_PIN}\b"
                       rf"[^.!?,;]{{0,75}}?\b{re.escape(target)}[\u2019']s\s+{_HAND}\b")
            if re.search(pattern, direction or '', re.I):
                item = {'action': 'pin_hands', 'actor_subject': actor_id,
                        'target_subject': target_id, 'source': 'user_direction'}
                if item not in requirements:
                    requirements.append(item)
    return requirements


def _h3_pin_relations(detail):
    """Find explicit H3 actor->target pin clauses; ignore unattributed passives."""
    found = set()
    for clause in re.split(r'[.;\n]', detail or ''):
        for verb in re.finditer(rf'\b{_PIN}\b', clause, re.I):
            # Pinned hands must appear after the active pin verb.
            after = clause[verb.end():]
            target = re.search(
                rf'(?:both\s+of\s+|one\s+of\s+|(?:her|his|their)\s+)?'
                rf'<Subject\s+(\d+)>[\u2019\']s\s+{_HAND}\b', after, re.I)
            if not target:
                continue
            before = clause[:verb.start()]
            actors = list(re.finditer(r'<Subject\s+(\d+)>', before))
            if not actors:
                continue
            # A referenced object mentioned just before the pin verb is not
            # necessarily the actor. E.g.:
            #   <Subject 2> leans forward to hold <Subject 1> down, and firmly
            #   pins both of <Subject 1>'s hands ...
            # The last mention before "pins" is <Subject 1>, the *object* of
            # "hold". Work backwards to the nearest grammatical actor, while
            # remaining conservative for more ambiguous phrasing.
            object_preceders = re.compile(
                r'\b(?:of|over|toward|towards|against|with|beside|behind|'
                r'under|onto|to|past|at|'
                r'hold|holds|holding|held|push|pushes|pushed|pushing|'
                r'press|presses|pressed|pressing|grab|grabs|grabbed|grabbing|'
                r'flip|flips|flipped|flipping|pull|pulls|pulled|pulling|'
                r'yank|yanks|yanked|yanking|turn|turns|turned|turning|'
                r'pin|pins|pinned|pinning)\s*$', re.I,
            )
            actor = next((mention for mention in reversed(actors)
                          if not object_preceders.search(before[:mention.start()])), None)
            if actor is None:
                continue
            actor_id = int(actor.group(1))
            target_id = int(target.group(1))
            if actor_id != target_id:
                found.add((actor_id, target_id))
    return found


def action_role_checks(detail, required_actions):
    """Reject an explicit reversed pin and missing explicit required pin.

    No automatic rewriting: generating a correct action is the composer's job.
    """
    problems = []
    seen = _h3_pin_relations(detail)
    for item in required_actions or []:
        if not isinstance(item, dict) or item.get('action') != 'pin_hands':
            continue
        try:
            actor, target = int(item['actor_subject']), int(item['target_subject'])
        except (ValueError, TypeError, KeyError):
            continue
        if (target, actor) in seen:
            problems.append(
                f"unrequested hand-pin role reversal: <Subject {target}> pins "
                f"<Subject {actor}>'s hands; user directs <Subject {actor}> pinning "
                f"<Subject {target}>'s hands"
            )
        if (actor, target) not in seen:
            problems.append(
                f"required hand-pin action not explicitly grounded: "
                f"<Subject {actor}> must pin <Subject {target}>'s hands"
            )
    return problems
