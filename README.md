# Bulletin

**An announcement is published only if its own cited source backs it.** A trust layer for on-chain announcements, judged from live evidence by GenLayer validators.

An announcement is only as trustworthy as the source behind it, and on chain there is usually no source at all: a string is posted, signed by an address, and a reader has to take it on faith. "The Foundation has announced X" travels faster than anyone can check it, screenshots are forged, and a fake token sale looks exactly like a real grant.

Bulletin makes the check the price of publication.

## How it works

1. **`post(headline, body, source_url)`** — anyone posts an announcement and must name the page it comes from. The poster is bound to `gl.message.sender_address`. Status: `PENDING` (not published).
2. **`verify(id)`** — open to anybody. The contract **fetches the cited page itself** inside a validator round and decides one thing: does the page back this announcement? `SUPPORTED` → `VERIFIED`; `NOT_SUPPORTED` (contradicts or does not support) → `REFUTED`; `UNREADABLE` (unreachable or off-topic) → stays `PENDING`.
3. **`is_verified(id)`** — the boolean a downstream contract or reader gates on. Only `VERIFIED` bulletins are meant to be trusted.

Reads for the board: `get(id)`, `size()`, `page(start, count)`.

## Why it needs GenLayer

Whether a page "backs a claim" is a judgement about real-world text that no ordinary contract can make and no single oracle should be trusted to make alone. GenLayer validators each fetch the page and reach consensus on one categorical field, so publication rests on evidence the contract read, not on the poster's word.

## What it refuses

- **Never publishes on silence.** An unreachable or unrelated page is `UNREADABLE`; the bulletin stays `PENDING`, never falsely `VERIFIED`.
- **Never publishes on the poster's word.** The poster is the caller; the deciding evidence is the page the contract fetched.
- **Separates contradiction from outage.** A source that denies the claim is `REFUTED` (a finding); one that could not be read stays `PENDING` (not a finding), so a server being down never condemns an honest announcement.

## Live

- **Contract (GenLayer Asimov):** `0x9CBD9AebeE96a4658Bc5fb2D57afA0659881E871`
- Explorer: https://explorer-asimov.genlayer.com/address/0x9CBD9AebeE96a4658Bc5fb2D57afA0659881E871
- **App:** https://jspiiv.github.io/bulletin/ — reads the board from chain without a wallet; posting and verifying are transactions on Asimov.

## Proven on Asimov

Two announcements against two source pages in `docs/press/` (`scripts/prove.mjs`, `results/proved.json`):
- A real grant announcement, whose source confirms it → `verify` returns **SUPPORTED** → **VERIFIED**.
- A fake "the Foundation launched token $FDN" announcement, whose cited source is a security notice denying any token → `verify` returns **NOT_SUPPORTED** → **REFUTED**, never published.

## Try it

Browse the live app, or from the CLI:

```
genlayer call 0x9CBD9AebeE96a4658Bc5fb2D57afA0659881E871 size
genlayer call 0x9CBD9AebeE96a4658Bc5fb2D57afA0659881E871 page --args '"0"' '"10"'
```

Reproduce the proof: `AT=0x9CBD9AebeE96a4658Bc5fb2D57afA0659881E871 PADV=<your padv password> node scripts/prove.mjs` (after `npm i`).

## Where it stops, plainly

It judges whether a page supports an announcement, not whether the page itself is honest. A source the poster chose can be captured or wrong, and a loosely worded claim can be read two ways. It reads what is public: a page behind a login or paywall is `UNREADABLE`. Point it at an authoritative third party rather than your own site, and say so to whoever relies on the verdict. It holds no native value on this network; the consequence it moves is the bulletin's status, which a settlement or display contract layers on top.

## Licence

AGPL-3.0-or-later.
