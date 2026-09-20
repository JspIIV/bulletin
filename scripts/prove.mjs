// Prove Bulletin end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv keystore password> node scripts/prove.mjs
//
// Two announcements against two real source pages in this repo:
//   - a real grant announcement, whose source confirms it -> verify SUPPORTED -> VERIFIED
//   - a fake "$FDN token launched" announcement, whose source is a scam warning
//     that denies any token -> verify NOT_SUPPORTED -> REFUTED
//
// It polls the record rather than waiting for FINALIZED, because the state is the
// real proof and Asimov can take a while to finalize a round.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs';
import os from 'os';
import path from 'path';
import url from 'url';

const AT = process.env.AT;
const PASS = process.env.PADV || '';
if (!AT || !PASS) { console.error('set AT and PADV'); process.exit(1); }

const ROOT = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const caller = await Wallet.fromEncryptedJson(
  fs.readFileSync(path.join(os.homedir(), '.genlayer', 'keystores', 'padv.json'), 'utf8'), PASS);
const as = createClient({ chain: testnetAsimov, account: createAccount(caller.privateKey) });
const anybody = createClient({ chain: testnetAsimov });

const RAW = 'https://raw.githubusercontent.com/JspIIV/bulletin/master/docs/press/';
const REAL = {
  headline: 'Foundation awards 50,000 GEN grant to Project Orbit',
  body: 'The grants committee approved a 50,000 GEN grant to Project Orbit, paid across three milestones.',
  url: RAW + 'grant-awarded.txt',
};
const FAKE = {
  headline: 'The Foundation has launched token $FDN, public sale live now',
  body: 'Buy $FDN before the price rises. Sale ends soon.',
  url: RAW + 'scam-warning.txt',
};

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const transient = e => /-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET/i
  .test(String(e?.details || e?.shortMessage || e?.message || e));

const read = async (fn, args = []) => JSON.parse(await anybody.readContract({ address: AT, functionName: fn, args }));
async function write(fn, args) {
  for (let a = 1; ; a++) {
    try { return await as.writeContract({ address: AT, functionName: fn, args, value: 0n }); }
    catch (e) { if (!transient(e) || a >= 8) throw e; say(`  (${fn} transient, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function poll(id, done, label) {
  for (let i = 0; i < 40; i++) {
    await sleep(12000);
    let r; try { r = await read('get', [id]); } catch { continue; }
    if (done(r)) { say(`  ${label} (${(i + 1) * 12}s)`); return r; }
  }
  throw new Error('timed out polling ' + label);
}

say('Bulletin, proven on GenLayer Asimov');
say('  contract ' + AT);
say('');

const before = (await read('size')).total;
await write('post', [REAL.headline, REAL.body, REAL.url]);
await poll('0', r => r.exists !== false && r.status, 'posted #0 (real grant announcement)');
await write('post', [FAKE.headline, FAKE.body, FAKE.url]);
await poll('1', r => r.exists !== false && r.status, 'posted #1 (fake $FDN token announcement)');
say('');

say('verifying #0 against its cited source...');
await write('verify', ['0']);
const v0 = await poll('0', r => Number(r.checks) >= 1, 'verified #0');
say('  decision ' + v0.decision + ', status ' + v0.status);
say('  reason: ' + (v0.reason || '(none)'));
say('');

say('verifying #1 against its cited source (a scam warning that denies any token)...');
await write('verify', ['1']);
const v1 = await poll('1', r => Number(r.checks) >= 1, 'verified #1');
say('  decision ' + v1.decision + ', status ' + v1.status);
say('  reason: ' + (v1.reason || '(none)'));
say('');

const iv0 = await read('is_verified', ['0']);
const iv1 = await read('is_verified', ['1']);
const size = await read('size');
say('is_verified(#0) = ' + iv0.verified + ' ; is_verified(#1) = ' + iv1.verified);
say('register: ' + JSON.stringify(size));

const checks = [
  ['two announcements were posted', before === 0 && size.total === 2],
  ['the real announcement is SUPPORTED by its source', v0.decision === 'SUPPORTED'],
  ['and it becomes VERIFIED', v0.status === 'VERIFIED'],
  ['the fake announcement is NOT_SUPPORTED by its source', v1.decision === 'NOT_SUPPORTED'],
  ['and it becomes REFUTED, never published', v1.status === 'REFUTED'],
  ['is_verified gates true only for the real one', iv0.verified === true && iv1.verified === false],
  ['the register counts one verified and one refuted', size.verified === 1 && size.refuted === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. It published only the announcement its own source backed.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  real: v0, fake: v1, is_verified: { real: iv0, fake: iv1 }, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
