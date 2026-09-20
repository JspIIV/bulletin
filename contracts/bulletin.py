# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Bulletin: an announcement is published only if its own cited source backs it.

An announcement is only as trustworthy as the source behind it, and on chain
there is usually no source at all: a string is posted, signed by an address, and
a reader has to take it on faith that the address is who it claims and that what
it says is real. Screenshots are forged, quotes are invented, and "the foundation
has announced X" travels faster than anyone can check it.

Bulletin makes the check the price of publication. Whoever posts an announcement
must name the page it comes from. Anyone can then ask the contract to verify it:
the contract fetches that page itself and a round of validators decides one thing,
does the page actually back this announcement? Only if they agree it does is the
bulletin marked VERIFIED, and only VERIFIED bulletins are what another contract or
reader is meant to trust. A page that contradicts the announcement marks it
REFUTED; a page that cannot be read leaves it PENDING, never falsely published.

## What it answers

    is_verified(id) -> bool

for another contract to gate on: release a payout, show a banner, trigger an
action, but only behind an announcement whose own cited source was read and found
to support it.

## What it refuses

It never publishes on silence: an unreachable or unrelated page is UNREADABLE and
the bulletin stays PENDING, not VERIFIED. It never publishes on the poster's word
alone: the poster is bound to the caller, and the deciding evidence is the page
the contract fetched, not anything the poster passed in. And it separates a source
that contradicts the claim (REFUTED, a finding) from one that could not be read
(PENDING, not a finding), because treating an outage as a refutation would punish
an honest announcement for a server being down.

## Where it stops, plainly

It judges whether a page supports an announcement, not whether the page itself is
honest. A source the poster chose can be captured or wrong, and a claim worded
loosely can be read two ways. It reads what is public: a page behind a login or a
paywall is UNREADABLE here. Point it at an authoritative third party rather than
your own site, and say so to whoever relies on the verdict.
"""

from genlayer import *
import json

SUPPORTED = "SUPPORTED"
NOT_SUPPORTED = "NOT_SUPPORTED"
UNREADABLE = "UNREADABLE"
DECISIONS = (SUPPORTED, NOT_SUPPORTED, UNREADABLE)

PENDING = "PENDING"
VERIFIED = "VERIFIED"
REFUTED = "REFUTED"

MAX_HEADLINE = 200
MAX_BODY = 600
MAX_URL = 300
MAX_PAGE = 6000
MAX_REASON = 300
MAX_QUOTE = 300

FETCH_FAILED = "__FETCH_FAILED__"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _url_ok(url: str) -> bool:
    text = str(url).strip()
    if len(text) < 8 or len(text) > MAX_URL or " " in text:
        return False
    return text.startswith("https://") or text.startswith("http://")


def _field(raw: str, name: str, allowed, fallback: str) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            said = str(obj.get(name, "")).strip().upper()
            return said if said in allowed else fallback
    except Exception:
        pass
    return fallback


def _text_field(raw: str, name: str, limit: int) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return _clip(str(obj.get(name, "")), limit)
    except Exception:
        pass
    return ""


def _task(headline: str, body: str, page: str) -> str:
    return f"""An announcement has been posted on chain, and it names one page as its source.
Decide whether that page actually backs the announcement.

THE ANNOUNCEMENT:
{headline}

{body}

THE PAGE IT NAMED AS ITS SOURCE:
{page}

Decide one of:
  {SUPPORTED} the page clearly states or confirms what the announcement claims
  {NOT_SUPPORTED} the page addresses the claim and does not support it, or contradicts it
  {UNREADABLE} the page could not be read, or says nothing about the claim either way

Judge only the substance of the claim against what the page actually says. Small
differences of wording are fine if the page confirms the same fact. Do not treat
an unreachable page, or a page about something else, as either support or denial:
that is {UNREADABLE}. A bulletin becomes public only on {SUPPORTED}, so give it
only when the page genuinely backs the announcement.

Reply with bare JSON and nothing else:
{{"decision": "{SUPPORTED}" or "{NOT_SUPPORTED}" or "{UNREADABLE}",
  "quote": "the sentence on the page that decided it, or empty",
  "reason": "one sentence naming what decided it"}}"""


class Bulletin(gl.Contract):
    """Announcements, each publishable only once its own cited source is read and found to back it."""

    # str(id) -> the bulletin as JSON. Flat, because a storage collection cannot
    # be created in user code, so nothing nested is kept.
    items: TreeMap[str, str]
    # Append only, so the board can be listed in the order things were posted.
    ids: DynArray[str]

    def __init__(self) -> None:
        pass

    @gl.public.write
    def post(self, headline: str, body: str, source_url: str) -> str:
        """Post an announcement with the page it comes from. It starts PENDING, unpublished.

        The poster is bound to the caller. Nothing here is trusted yet: an
        announcement is only a claim until its source is fetched and found to back
        it by verify.
        """
        poster = gl.message.sender_address.as_hex.lower()
        head = _clip(headline, MAX_HEADLINE)
        text = _clip(body, MAX_BODY)
        link = str(source_url).strip()
        if not head:
            return json.dumps({"ok": False, "error": "give the announcement a headline"})
        if not _url_ok(link):
            return json.dumps({"ok": False,
                               "error": "give an http(s) source URL the announcement can be checked against"})

        bid = str(len(self.ids))
        record = {
            "id": bid,
            "poster": poster,
            "posted_at": _now_iso(),
            "headline": head,
            "body": text,
            "source_url": link,
            "status": PENDING,
            "checks": 0,
            "decision": "",
            "reason": "",
            "quote": "",
            "verified_at": "",
        }
        self.items[bid] = json.dumps(record)
        self.ids.append(bid)
        return json.dumps({"ok": True, "id": bid, "status": PENDING})

    @gl.public.write
    def verify(self, bulletin_id: str) -> str:
        """Fetch the cited source and mark the bulletin VERIFIED, REFUTED, or leave it PENDING.

        Open to anybody: a bulletin only its poster could verify would prove
        nothing. The page is fetched by the contract itself inside the round, so no
        caller can pass in the answer.
        """
        bid = str(bulletin_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"ok": False, "error": "no bulletin with that id"})
        record = json.loads(stored)
        if record["status"] == VERIFIED:
            return json.dumps({"ok": False, "error": "already verified", "status": VERIFIED})

        # Everything the round needs is copied into locals first. Nothing inside
        # the block reads self and nothing inside it raises: either would end the
        # whole transaction rather than the round.
        headline = record["headline"]
        body = record["body"]
        url = record["source_url"]

        def look() -> str:
            page = ""
            try:
                got = gl.nondet.web.render(url)
                page = got if isinstance(got, str) else getattr(got, "body", "")
                if isinstance(page, (bytes, bytearray)):
                    page = page.decode("utf-8", "replace")
                page = _clip(str(page), MAX_PAGE)
            except Exception:
                page = FETCH_FAILED
            if not page or page == FETCH_FAILED:
                return json.dumps({"decision": UNREADABLE, "quote": "",
                                   "reason": "the source page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(headline, body, page)))
            except Exception as error:
                return json.dumps({"decision": UNREADABLE, "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named decision, one of "
                f"{SUPPORTED}, {NOT_SUPPORTED} or {UNREADABLE}. That single field decides whether "
                "an announcement is published as verified, so two readers differing on it are not "
                "wording a judgement differently, they disagree about whether the source backs the "
                "claim. The quote and the reason are not compared, and the two readers will not "
                "have fetched byte-identical copies of the page."
            ),
        )

        decision = _field(raw, "decision", DECISIONS, "")
        if not decision:
            return json.dumps({"ok": False,
                               "error": "the round produced no decision this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        record["checks"] = int(record.get("checks", 0)) + 1
        record["decision"] = decision
        record["reason"] = _text_field(raw, "reason", MAX_REASON)
        record["quote"] = _text_field(raw, "quote", MAX_QUOTE)
        if decision == SUPPORTED:
            record["status"] = VERIFIED
            record["verified_at"] = _now_iso()
        elif decision == NOT_SUPPORTED:
            record["status"] = REFUTED
        # UNREADABLE leaves the status untouched, so an outage never publishes or
        # condemns a bulletin; it can simply be verified again later.
        self.items[bid] = json.dumps(record)
        return json.dumps({"ok": True, "id": bid, "decision": decision,
                           "status": record["status"], "reason": record["reason"]})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def is_verified(self, bulletin_id: str) -> str:
        """The one field a downstream contract gates on: is this announcement backed by its source."""
        bid = str(bulletin_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"exists": False, "verified": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": bid,
                           "verified": record["status"] == VERIFIED,
                           "status": record["status"]})

    @gl.public.view
    def get(self, bulletin_id: str) -> str:
        """The whole bulletin, including the deciding quote and reason once verified."""
        bid = str(bulletin_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def size(self) -> str:
        """How many bulletins are pending, verified and refuted."""
        pending = 0
        verified = 0
        refuted = 0
        for position in range(len(self.ids)):
            record = json.loads(self.items[self.ids[position]])
            state = record["status"]
            if state == PENDING:
                pending += 1
            elif state == VERIFIED:
                verified += 1
            elif state == REFUTED:
                refuted += 1
        return json.dumps({"total": len(self.ids), "pending": pending,
                           "verified": verified, "refuted": refuted})

    @gl.public.view
    def page(self, start: str, count: str) -> str:
        """A slice of the board, newest first, for a frontend to render without reading every id."""
        total = len(self.ids)
        try:
            begin = int(str(start).strip())
        except Exception:
            begin = 0
        try:
            want = int(str(count).strip())
        except Exception:
            want = 20
        if begin < 0:
            begin = 0
        if want < 1:
            want = 1
        if want > 50:
            want = 50
        out = []
        seen = 0
        position = total - 1 - begin
        while position >= 0 and seen < want:
            out.append(json.loads(self.items[self.ids[position]]))
            position -= 1
            seen += 1
        return json.dumps({"total": total, "start": begin, "count": len(out), "items": out})
