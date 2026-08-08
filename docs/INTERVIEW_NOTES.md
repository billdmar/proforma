# INTERVIEW_NOTES.md — defend this model

Answers grounded in **this** merger model: the real **Synopsys (SNPS) /
ANSYS (ANSS)** deal, announced 2024-01-16, closed 2025-07-17, reconstructed
from SEC filings. Every number below comes from the engine; the assumptions
(and which figures are disclosed vs. ours) live in `docs/ASSUMPTIONS.md`.
Practice saying each of these aloud — the project only converts in a room if
you own the finance, not just the code. This is an educational reconstruction
from public filings, **not investment advice**, and it passes no verdict on
whether the deal should have happened.

---

## The 90-second "tell me about a recent deal"
"Synopsys — the EDA leader — is buying ANSYS, the engineering-simulation
leader, in a cash-and-stock deal announced in January 2024 and closed in mid-
2025. The strategic logic is a full 'silicon-to-systems' design stack: chip
design plus physics simulation under one roof. Each ANSYS share got $197 in
cash plus 0.345 of a Synopsys share — about $390 implied at announcement, a
roughly 29% premium, so around $34 billion of equity value for ~87 million
target shares. Synopsys funded the ~$17B cash leg with about $14.3 billion of
new debt — $10B senior notes and a $4.3B term loan — plus roughly $3B of cash
on hand, and issued about 30 million new shares. Here's the insight I'd lead
with: on my model it's deeply GAAP-**dilutive** — down roughly 38% to EPS in
Year 1 and still down about 21% by Year 5 — and the breakeven synergy level
that would make Year 1 neutral is about $1.25 billion a year, which is far
above any plausible cost-synergy number for a target with only a ~$1.5B cost
base. My standalone DCF of ANSYS lands well below the $390 offer. So this isn't
an EPS deal at all — it's a strategic, capability deal, and the accretion math
proves it: they paid up for the combined platform, not for near-term earnings."

---

## 1. Walk me through a merger model.
You start with two standalone companies — here I built each off its last
**pre-close** fiscal year so I don't double-count: Synopsys FY2024 (revenue
$6,127M, ~22% operating margin, ~156M shares) and ANSYS FY2024 (revenue
$2,545M, ~28% margin, ~87.9M shares). Then you set the deal terms — the offer
price and the cash/stock mix — which gives the equity purchase price. Next is
sources and uses: how the cash portion is funded (new debt, cash on hand, new
equity). Then purchase price accounting: allocate the price over the target's
net assets, step up intangibles, and plug the rest to goodwill. Then you
combine the income statements and layer the deal adjustments — new interest
expense on the debt, foregone interest income on the cash you spent, the extra
D&A from the intangible step-up, and synergies — all after-tax. Divide the
combined pro forma net income by the new pro forma share count and compare that
EPS to the acquirer's standalone EPS. That delta is accretion/dilution, and
the whole point of the model is to tell you whether the deal adds to or
subtracts from the buyer's earnings per share, and by how much, over time.

## 2. Walk me through THIS accretion/dilution.
Start with combined net income: Synopsys standalone plus ANSYS standalone. Then
four after-tax adjustments. First, subtract new interest on ~$14.3B of debt at
a ~5% blended rate — that's a big drag, roughly $700M pre-tax a year. Second,
subtract foregone interest income on the ~$3B of cash they deployed at ~4%.
Third, subtract the incremental step-up amortization — about $0.8B a year from
the $8B intangible step-up over a 10-year life. Fourth, add synergies. That
gives pro forma net income. The share count rises by only ~30 million new
Synopsys shares (0.345 × 87.3M) on a ~156M base, so the denominator only grows
~19% while the numerator gets hit hard by interest and amortization. Result:
pro forma EPS is well below standalone. In my base case (with our $300M synergy
assumption) it's **−38.5% in Year 1 improving to −20.6% by Year 5**; the
conservative $150M case runs **−42.1% to −24.0%**. It de-dilutes over time as
revenue grows and the fixed deal costs shrink relative to earnings, but it
never flips accretive in the horizon.

## 3. Why is Year-1 dilution not automatically bad?
Because a big chunk of the dilution is **non-cash and structural, not
economic**. The single largest recurring drag after interest is the ~$0.8B/yr
of intangible step-up amortization — that's purchase-accounting D&A, a
bookkeeping artifact of writing ANSYS's assets up to fair value. It reduces
GAAP EPS but it's not a cash outflow and it doesn't reflect any deterioration
in the business. On a **cash-EPS basis (excluding step-up amortization)** the
picture is materially less dilutive — roughly −10% in Year 1 on cash EPS versus
−38% on GAAP (adding back the ~$0.8B after-tax step-up amortization). Acquirers
routinely guide to cash EPS or non-GAAP EPS for exactly this reason. So a
GAAP-dilutive deal can still be value-creating, and it's far less dilutive than
the GAAP headline suggests. I'm careful not to overclaim: it's less
cash-dilutive, not cash-accretive. The real question isn't "is Year-1 EPS down"
— it's whether the strategic value and eventual synergies justify the premium.
Here the honest answer is that the case is strategic, not EPS-driven, and I say
that plainly rather than dressing it up.

## 4. How did you compute goodwill / the PPA walk?
Goodwill is the plug in purchase price accounting. I start with the equity
purchase price — about $34.1B from the disclosed $390.19/share consideration
times ~87.3M shares. Then I build up the identifiable net assets acquired: take
ANSYS's book equity (~$6.1B), **write off its existing $3,778M of pre-deal
goodwill** (you don't carry the target's old goodwill forward — you re-measure
from scratch), **step up identifiable intangibles by $8.0B** (our assumption),
and record a **deferred tax liability** on that step-up. Goodwill = equity
purchase price − fair value of identifiable net assets. That walk produces
**~$25.4B of goodwill**. As a sanity check, the actual post-close Synopsys
balance sheet shows ~$26.9B — our number is a touch lower precisely because we
assumed a more conservative $8B step-up while they booked ~$12.5B; more step-up
means less goodwill, so the gap ties out directionally.

## 5. What are the step-up and the DTL, and why?
The step-up is writing the target's identifiable intangibles — developed
technology, customer relationships, trade names — up from book value to fair
value at acquisition. I assumed **$8.0B over a 10-year life** (ours), which
throws off the ~$0.8B/yr of incremental amortization that hits pro forma EPS.
The **deferred tax liability** exists because that step-up is a *book* increase
with no corresponding *tax* basis increase — in a stock deal the tax basis
carries over. So book D&A will exceed tax D&A, meaning higher book taxes
relative to cash taxes in the future; you record a DTL today for that difference
and it unwinds as the intangibles amortize. I set the DTL at the **21% US
statutory rate** — deliberately different from the 16% normalized rate I use on
the P&L adjustments, because a DTL is a book-vs-tax basis difference and gets
the statutory rate, not an effective operating rate.

## 6. Cash vs. stock — how does each affect accretion?
It's an earnings-yield versus P/E comparison. **Cash** financed with debt is
accretive when the target's after-tax earnings yield exceeds the after-tax cost
of the debt — you're buying earnings with ~5% money. **Stock** is accretive
when the acquirer's earnings yield (1/PE) is higher than the target's — i.e.
when you're issuing expensive shares to buy cheaper earnings. Here Synopsys
trades at a very high P/E (low earnings yield), so issuing stock to buy ANSYS
is dilutive on that leg, and the debt leg carries real interest cost. The mix
is ~half cash / half stock by value, so you get both drags at once. That's a
big part of why this deal is so dilutive — a high-multiple acquirer using its
own richly-valued stock plus levered cash to buy a lower-growth, high-margin
target where the purchase-accounting amortization then piles on top.

## 7. How is the cash funded, and how does the debt affect A/D?
The disclosed structure is **$10.0B of senior notes plus a $4.3B term loan**,
so ~$14.3B of new debt, plus roughly $3B of cash on hand — that debt split is
disclosed in the filings; the ~**5% blended rate is my assumption** (the exact
tranche coupons aren't in the cached filings, so I use a defensible blended
investment-grade-tech cost). New debt hurts A/D through after-tax interest
expense — roughly $700M pre-tax a year, and after the 16% deal-tax rate it's
still one of the two biggest drags in the bridge. Using cash instead of debt
avoids the interest but costs the foregone interest income on that cash (~4%),
which is a smaller drag because deposit yields are below borrowing rates. The
trade-off is real: more debt means more interest drag but no share issuance;
more stock means dilution of ownership but no interest. This deal took on
substantial debt *and* issued stock, which is why it's dilutive on both fronts.

## 8. Sources = uses — walk it.
It's the balance check on how the deal is paid for. **Uses**: the cash portion
of the consideration (~$197 × 87.3M shares of cash), refinancing where needed,
and transaction fees (I assume $150M, ~0.4% of deal value — the proxy doesn't
itemize one figure). **Sources**: the new debt ($14.3B disclosed), cash on hand
(~$3.05B, ours), and the new equity issued to target holders (the stock leg,
~30.1M shares). The engine sizes the cash-on-hand as the exact remainder so
**sources equal uses with no residual plug** — that's an invariant the build
enforces, and it's what lets the pro forma balance sheet tie out every period.
If sources didn't equal uses, the combined balance sheet wouldn't balance, and
the build would fail.

## 9. What are breakeven synergies, and what does ~$1.25B tell you?
Breakeven synergies are the annual run-rate that makes **Year-1 A/D exactly
zero** — the amount of cost or revenue synergy you'd need to fully offset all
the dilution from interest, foregone income, and step-up amortization. For this
deal that's **~$1.25 billion a year**. That number is the punchline of the whole
model: ANSYS's entire operating-cost base is only about $1.5B, so you'd need to
synergize almost the target's whole cost structure just to break even on GAAP
EPS in Year 1. That's not plausible from cost synergies alone. Both of my
synergy cases — $150M conservative and $300M base — are **my own assumptions**
(the proxy quantifies none), and both sit far below breakeven. So the honest
read is: this deal cannot be justified on near-term EPS accretion. It has to be
a strategic bet on the combined platform, and the breakeven math is exactly how
I'd demonstrate that in a room.

## 10. Contribution vs. ownership — why do they differ?
Contribution analysis asks: what share of the combined company's fundamentals
does each side bring? On revenue, Synopsys contributes ~$6.8B and ANSYS ~$2.8B,
so ANSYS contributes roughly **29%** of combined revenue. But post-deal, ANSYS
shareholders own only about **16.2%** of the combined company (~30.1M new shares
on a ~186M combined base), with Synopsys holders at ~83.8%. They diverge because
this is a **cash-and-stock** deal, not all-stock: ANSYS holders got more than
half their consideration in cash, so they don't receive equity proportional to
what they contribute — they were partly cashed out. In a pure all-stock deal,
contribution and ownership converge toward each other (adjusted for relative
valuation); the gap here quantifies how much of the target was bought with cash
versus paper. It's also a premium tell: ANSYS holders own only ~16% of the
combined company yet were paid a 28.7% premium and over half their consideration
in cash — so they realized value up front rather than riding the combined
equity.

## 11. How did you value ANSYS standalone, and why is it below the offer?
I ran an independent DCF on ANSYS on a standalone basis — this is **my own**
intrinsic view, separate from the fairness-opinion work. I discount the
target's driver-based unlevered free cash flow at a **~9.4% WACC**: risk-free
4.3%, beta 1.05, 5% equity risk premium, and since ANSYS is essentially net-
cash the weight is almost entirely cost of equity. Two terminal methods: Gordon
growth at 3% gives about **$140/share**, and an exit EV/EBITDA of 22× gives
about **$264/share**. Both are **below the $390.19 offered**. That's the
expected and correct result: a standalone intrinsic value should sit below a
control offer, because the acquirer is paying a **premium for control,
synergies, and strategic fit** that a standalone DCF doesn't capture. If my
standalone value had come out *above* the offer, I'd worry I'd made an error or
the buyer overpaid egregiously. The gap between ~$140–264 standalone and $390
offered *is* the premium for control and strategy — which is exactly the story.

## 12. What does a fairness opinion tell you — and what doesn't it?
A fairness opinion — here Qatalyst Partners advising ANSYS's board — is a
banker's judgment that the consideration is "fair, from a financial point of
view" to the target's shareholders. It discloses the analyses behind that:
a DCF range, selected-companies comps, and selected-transactions precedents,
each with the key assumptions (discount rates, multiples). What it tells you is
whether the price sits within defensible valuation ranges. What it does **not**
tell you: it's not a conclusion that the deal is a *good* deal, or the *best*
price, or that the strategy will work. "Fair" just means "within a reasonable
range" — it's a legal and governance box, largely to protect the board against
shareholder suits. It says nothing about whether shareholders should have held
out for more, whether the strategic thesis pays off, or whether the buyer is
overpaying. I treat it as a disclosed, provenance-stamped input to check my own
work against — not as a verdict.

## 13. How did you reproduce Qatalyst's ranges, and why does the DCF overlap less?
I fed Qatalyst's **own disclosed assumptions** — their discount-rate band, their
multiple ranges, the management-case UFCF — through my engine and checked
whether I reproduce the implied per-share ranges they published. This is a
differential test, measured and never tuned. Mean overlap is **67.3%**:
Selected Companies **79%**, Selected Transactions **77%**, but DCF only **46%**.
The DCF gap has a specific, documented cause: Qatalyst's disclosed DCF range is
the **union of management Cases 1–3** ($160–$496), whereas the proxy only
tabulates the Case-1 projection in detail, so my reproduction uses Case 1 only
and lands in a narrower band ($342–$555) sitting in the upper portion of their
wider range. It's not a modeling error — it's a disclosure-granularity
difference, and I investigated and wrote it up rather than tuning my inputs to
force a higher overlap. That discipline — explain the deviation, don't tune it
away — is the point.

## 14. What are the key risks?
Four buckets. **Regulatory/antitrust**: EDA plus simulation is a big combination
scrutinized in multiple jurisdictions, with divestiture and timing risk (this
deal did face extended review). **Integration**: merging two large software
organizations, product roadmaps, and go-to-market motions — synergies are never
guaranteed, and mine are assumptions, not disclosed figures. **Financing**: they
took on ~$14.3B of new debt; my ~5% blended rate is an assumption, and higher
rates or refinancing risk would worsen the interest drag. **Market/valuation**:
the deal is dilutive for years, so it depends on the combined platform
delivering growth — if the strategic thesis underperforms, you've paid a 29%
premium and levered up for earnings dilution. And more narrowly, my model's
biggest judgment levers are the intangible step-up, the blended debt rate, and
the synergy cases — I flag those as the assumptions to stress.

## 15. How do you know your model is right — not just plausible?
Every number is machine-verified, not asserted. First, **dual XBRL tie-out**:
both companies' historical statement lines reconcile to SEC-reported facts to
the dollar. Second, the **Excel↔Python cell differential** — the workbook is
built with live formulas, and a verifier recalculates every computed cell and
matches it to the independent Python engine **to the cent**; nothing is hand-
typed into the workbook or the memo. Third, **accounting invariants** run at
build time: sources = uses, goodwill ties to the PPA walk, the pro forma
balance sheet balances every period, the EPS bridge recomputes independently,
contribution ties to ownership, and synergies phase in correctly. Fourth,
**sensitivity sanity**: A/D is monotone in the right directions — more premium
is more dilutive, more synergies more accretive — and breakeven is consistent
with the grids. Fifth, the **fairness differential** above. And it's all
**deterministic** — a full rebuild from cached SEC data reproduces identical
numbers — with **~97% test coverage green in CI**, where CI never touches live
EDGAR. The finance judgment is mine to defend; the arithmetic is proven.

---

## Stack
A Python engine is the single source of truth: it pulls both companies' SEC
XBRL facts and the merger proxy, builds the two standalone models, runs the
full deal engine (sources & uses, purchase price accounting, financing,
synergies, accretion/dilution), and emits everything two ways — a live-formula
Excel merger model and an M&A committee memo PDF — with every figure verified
in CI against the engine to the cent, plus a differential against Qatalyst's
disclosed fairness-opinion ranges.
