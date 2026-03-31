# Icarus — Agent Writing Style

> How to write commit messages, code comments, and documentation.
> The goal is output that reads like a senior engineer wrote it,
> not an AI assistant.

## The Core Rule

**Scale effort to change size.** A one-line fix gets a one-line
commit message. A multi-file feature gets bullets. Never produce
the same structured format regardless of what changed.

---

## Commit Messages

### Individual commits
```
add backtest walk-forward validation
fix signal confidence clamping
update risk limits config
remove unused data requirement
wip: testing IB order routing
fix regime detection window
```

### Rules
- No periods at the end
- Lowercase is fine
- Past tense and imperative can mix freely: "added X" and "add X"
- WIP commits are normal and fine
- Short is always better: "fix lint" is a complete message
- No multi-paragraph commit bodies
- No co-authored-by lines

### Never write
```
Implement walk-forward backtesting validation to ensure robust
out-of-sample testing and improve strategy evaluation reliability.
This commit adds validation checks and updates the backtest engine
to expose this functionality to the research pipeline.
```

---

## Code Comments

The fastest way to make code look AI-generated is over-commenting.

### The rule
Comments explain **why**, never **what**. If the code reads
clearly, no comment is needed.

### Acceptable
```python
# IB API returns prices as floats with variable precision
# round to 2 decimals to match our position tracking
price = round(raw_price, 2)
```

```python
# walk-forward: train on history, test on unseen window
# prevents lookahead bias in backtest results
for train_end in walk_forward_dates:
```

```python
# kill switch stays latched until CIO explicitly clears it
# auto-deactivation would defeat the purpose
if self.kill_switch_active:
    return SignalRejection("kill switch active")
```

### Instant AI flag
```python
# Get the strategy from the engine
strategy = engine.get_strategy(name)

# Check if the strategy exists
if strategy is None:

# Return the signals
return signals
```

If you're about to write a comment that describes what the next
line does, delete the comment.

---

## Forbidden Words

Never use these, they are reliable AI tells:

| Avoid | Use instead |
|---|---|
| "comprehensive" | actual scope: "covers 3 signal types" |
| "robust" | just skip it |
| "ensures" / "ensuring" | "so that" or restructure |
| "leverages" / "leverage" | "uses" |
| "utilizes" | "uses" |
| "streamlined" | "simplified" or skip |
| "enhanced" | "updated" or "improved" |
| "Additionally" | just start the next sentence |
| "Furthermore" | just start the next sentence |
| "In order to" | "to" |
| "aligns with" | "matches" or "follows" |
| "facilitates" | "lets" or "allows" |
| Em dashes | commas, colons, parens, or restructure |

---

## Checklist Before Submitting

- [ ] No em dashes anywhere
- [ ] No forbidden words (comprehensive, robust, ensures, leverages)
- [ ] Code comments explain why, not what
- [ ] No comments on code that reads obviously
- [ ] Commit messages are short and lowercase

---

## The Contrast Test

**Wrong:**
> This commit introduces a comprehensive refactoring of the risk
> engine, enhancing reliability and ensuring robust validation
> of position limits. Additionally, this change implements
> proper kill switch handling for edge cases.

**Right:**
> - validate position limits before signal approval
> - kill switch rejects all signals when latched
> - warn at 80% of each limit threshold
