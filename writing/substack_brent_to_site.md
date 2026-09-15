# Brent to Site: What a Barrel of Oil Actually Does to a Ugandan Building Site

*Or: why the formula in your construction contract might be pricing the wrong thing.*

Somewhere in a filing system in Kampala sits a spreadsheet — an Interim Payment Certificate, or IPC, the monthly document that tells a contractor how much they're owed for a month's work on a road. It has 200-odd tabs. Most of them are quantity take-offs: how many cubic metres of murram were laid, how many linear metres of pipe went in. But two tabs are different. They're called "Adjust Local" and "Adjust Foreign," and they do something quietly remarkable: every month, for nearly five years, they've been running a live experiment in what happens when the price of oil moves and a construction contract has to decide who pays for it.

I got to look at one of these recently, and it ended up confirming — almost line for line — something I'd already found by a completely different route: a nine-year statistical model of Uganda's construction sector. This is the story of both.

## The question nobody quite answers

Construction contracts in oil-importing countries carry a risk nobody chose: the international price of crude. Diesel moves the trucks. Bitumen — the black, sticky binder in asphalt — is itself refined from crude. Cement and steel are cooked and shaped using enormous amounts of energy. None of that is under a contractor's control, and none of it is under an employer's control either. So contracts build in a formula: as published price indices move, the contract price moves with them. FIDIC, the most widely used family of international construction contracts, calls this Sub-Clause 13.8. It's a weighted sum: a fixed, non-adjustable slice of the price, plus a set of categories — labour, fuel, materials — each tracked against a published index, each carrying a weight fixed on day one.

It sounds simple. Whether it actually works — whether the indices chosen track the real cost driver, with the right timing, at the right weight — is almost never tested. Not because nobody cares, but because testing it means doing two hard things at once: building a real transmission model of how a global oil shock moves through a specific economy, and then checking that model against a real contract's real numbers. Most work does one or the other. I wanted to do both.

## Chasing the wrong channel first

The obvious hypothesis is the exchange-rate story: oil goes up, the import bill grows, the currency weakens, general prices rise, and construction costs follow along with everything else. I built exactly that model for Uganda — Brent crude, to the exchange rate, to the consumer price index, to construction cost inflation — using nine years of monthly data.

It found nothing. Every link in that chain came back statistically empty. Not "small effect" — genuinely undetectable, at every single lag tested.

That's not usually where an analysis ends up in public, because a null result isn't satisfying. But it was the right prompt to ask a sharper question: what if oil isn't reaching construction costs through the *economy*, but through a much more direct, much more boring pipe — diesel?

## The pivot, and the thing that actually worked

Diesel fuels the trucks that move materials to site. It fuels a lot of the equipment on site. If Brent crude is going to touch a construction project at all, diesel is the most literal way it could do it — no exchange rate, no general inflation, just: oil price up, pump price up, haulage cost up, invoice up.

Rebuilding the model around Uganda's own construction-sector diesel index (rather than the roundabout exchange-rate route) changed everything. Brent moves diesel within about a month, with real statistical confidence. Diesel moves construction cost inflation almost immediately. And — this is the part that mattered most — when you control for diesel, Brent's own apparent effect on construction costs nearly disappears. That's the signature of a *mediator*: diesel isn't just correlated with the oil shock, it's the channel the oil shock actually travels through.

I ran it through a battery of stress tests after that, because a clean result on nine years of monthly data can still be a fluke: regularized forecasting models (to make sure the finding wasn't just overfitting), a structural break test (to check the relationship was stable over time — it wasn't: it got roughly five times stronger after the 2022 commodity shock), and a bootstrap (to put honest error bars on the claim). It held up. Not perfectly — the exact size of the effect is uncertain — but the direction and the mechanism survived every check I threw at it.

One twist: when I extended the same logic to every individual construction material — not just the overall cost index — diesel's biggest downstream fingerprint wasn't on diesel-adjacent things. It was on **cement**. Cement, it turns out, is also the single most connected material in an entirely separate, previously-built analysis of how Uganda's construction materials move together domestically — a ranking that had nothing to do with oil at all. Two unrelated methods, pointing at the same material. Diesel is the gateway the shock comes in through; cement is the room it ends up flooding.

## Then the spreadsheet showed up

All of that was internal — a model built entirely from published statistics, with no outside check. Then someone handed me a real IPC.

I anonymized it and pulled out the numbers only — no client, no contractor, no project name, just dates, published index values, and the formula's own arithmetic. It turned out to be a genuine gift: 37 monthly-to-bimonthly valuation periods, April 2019 to February 2024, on a real price-adjustment formula that nobody built to prove anyone's point, because it was signed years before this analysis existed.

Three things fell out of it that I didn't expect:

**First**, the real contract already does something more sophisticated than the "generic index" strawman I'd been arguing against. It has its own dedicated fuel index — and a *separate* bitumen index, weighted even higher (0.20 against fuel's 0.10). Since bitumen is itself a petroleum product, that means well over a third of this formula's adjustable weight is, one way or another, tracking the price of oil. Nobody in this contract used the word "diesel-mediated transmission channel." They just built a formula that happens to reflect it.

**Second**, the real fuel index this contract uses — sourced independently, in a different currency, from a different statistical agency than anything in my model — tracks Brent crude at a correlation of 0.96. Its bitumen index, a channel I'd never even tested because it doesn't exist in the standard construction-cost data, tracks Brent at 0.50. Both are real, both are strong, and neither one owes me anything: I had no hand in building either series.

**Third**, and the one that actually gave me a small jolt: split that real contract's own fuel index at February 2022 — the same date my statistical model flagged, independently, months earlier — and its monthly growth rate accelerates 2.6 times. Two completely different datasets, built for completely different purposes, agreeing on the same turning point.

## So what does this mean for the contract itself?

Not that FIDIC's formula is broken. The architecture — a weighted sum of category indices — is the right shape, and this real example shows it can already be specified with real granularity. What the evidence argues for is narrower and, I think, more useful:

- If a contract's fuel or energy exposure is buried inside a general materials index rather than given its own line, that's a real, measurable gap — not a theoretical one.
- Weights should reflect what a project is actually built from. A road project weighted 20% to bitumen looks very different, oil-wise, from a building project where bitumen doesn't feature at all.
- The lag is short — about a month — and this real contract's own convention (a 49-day reference lag, chosen by the people who drafted it, with no reference to any of this analysis) already gets close to that number. What doesn't happen automatically is revisiting the *weights* once the world changes underneath them — and the world changed, measurably, in February 2022.

What none of this can yet say is whether any real contractor was actually short-changed by a specific amount. That needs bills of quantities and claims records I don't have. It's the obvious next step.

## The honest version

This started as a nine-year statistical model with a genuinely uncomfortable early finding (the obvious channel doesn't exist) and ended up, almost by luck, getting checked against a piece of paper nobody built for this purpose. That's about as good a day as this kind of work gets. It's not proof. It's one real contract, anonymized, alongside one internal model — a strong first data point, not a verdict. But when a spreadsheet built in 2019, by people who'd never heard of this analysis, and a model built in 2026, entirely from public statistics, land on the same date and the same mechanism independently — that's the kind of coincidence worth paying attention to.

*This is a working paper in progress — a fuller academic version, with the full methodology, is available on request. If you've worked with IPCs, escalation claims, or FIDIC contracts in East Africa and think this rings true (or doesn't), I'd like to hear about it.*
