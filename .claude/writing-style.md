# NeoJelly — Agent Writing Style

> How to write PR titles, descriptions, commit messages, and code
> comments. The goal is output that reads like a senior engineer
> wrote it, not an AI assistant.

## The Core Rule

**Scale effort to change size.** A one-line fix gets a one-line
PR body. A multi-day feature gets bullets. Never produce the same
structured format regardless of what changed.

The most structured writer on the team sets the ceiling. Going
further than that trips every detector.

---

## PR Titles

### Rules
- 5-12 words. No period at the end
- Lowercase after the type prefix: `feat:`, `fix:`, `chore:`
- Drop articles: "add filter" not "add a filter"
- Abbreviations are natural: `deps`, `env`, `config`, `auth`, `db`
- Conventional commit prefix is optional for small changes

### Good
```
feat: add coupon validation endpoint
fix: stripe webhook not processing refunds
chore: bump neojelly sdk to 1.0.18
add redirect click tracking
fix: creator slug check returns wrong status
```

### Never write
```
feat: Implement Comprehensive Coupon Validation System with Stripe Integration
chore: Enhance the existing webhook handler for improved reliability
fix: Resolve the issue causing stripe webhooks to not process refunds correctly
```

---

## PR Descriptions

### The effort spectrum

```
null body --- ticket/link --- 1 sentence --- bullets --- structured
   25%            15%             25%           25%          10%
```

Never land at "structured" for a small change. Match the size.

### Small fix (1-3 files changed)
```
webhook was returning 200 before verifying signature
```
One sentence. Done.

### Medium change (new endpoint, refactor)
```
- adds POST /coupons/validate endpoint
- checks against stripe before saving to db
- returns 400 if expired or already used
```
Bullets. No headers. No preamble.

### Large feature
```
adds stripe coupon flow end to end

- new endpoint: POST /coupons/validate
- sdk method: api.Coupons.validate(token, code)
- ui: coupon input on checkout with inline error state
- webhook handles coupon.deleted to sync db

tested against stripe test mode, 3 coupon states covered
```
Still no bold headers. Still no "This PR introduces...".

### Never write
- "This PR introduces..." or "This change implements..."
- Bold category headers: `**Database Changes:**`
- Sections nobody asked for: `## Rollback Plan`, `## Accessibility`
- "Comprehensive test coverage" — write actual numbers: "14 tests"
- "The most important changes are grouped below"
- A perfectly filled template every single time

---

## Commit Messages

### Individual commits (feature branch work)
```
add coupon validate endpoint
fix auth check on webhook
update sdk method signature
remove unused import
wip: testing stripe coupon states
fix response format
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
Implement coupon validation to improve checkout UX and ensure
robust handling of expired and already-used codes. This commit
adds the POST /coupons/validate endpoint and updates the SDK
to expose this functionality to frontend consumers.
```

---

## Code Comments

The fastest way to make code look AI-generated is over-commenting.

### The rule
Comments explain **why**, never **what**. If the code reads
clearly, no comment is needed.

### Acceptable
```csharp
// Stripe requires raw body for webhook signature verification
// must read before model binding touches the stream
Request.EnableBuffering();
```

```js
// FormData not JSON — matches [FromForm] on the backend
const formData = new FormData();
```

```jsx
// step stored as string so we can add more steps without
// renumbering enum values
const [step, setStep] = useState('info');
```

### Instant AI flag
```csharp
// Get the creator from the database
var creator = await context.Creators.FirstOrDefaultAsync(...);

// Check if stripe ID exists
if (string.IsNullOrEmpty(stripeId))

// Return the products
return stripeProducts;
```

```js
// Create a new FormData object
const formData = new FormData();

// Append the account stripe ID
formData.append('accountStripeId', accountStripeId);
```

If you're about to write a comment that describes what the next
line does, delete the comment.

---

## Forbidden Words

Never use these — they are reliable AI tells:

| Avoid | Use instead |
|---|---|
| "comprehensive" | actual scope: "covers 3 coupon states" |
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

Never start a PR body or commit with:
- "This pull request..."
- "This change..."
- "This commit..."
- "The main changes..."
- "Key changes include:"

---

## Checklist Before Submitting

- [ ] PR description length matches the size of the change
- [ ] No em dashes anywhere
- [ ] No forbidden words (comprehensive, robust, ensures, leverages)
- [ ] No "This PR introduces..." or "This change implements..."
- [ ] No bold section headers in PR body
- [ ] Code comments explain why, not what
- [ ] No comments on code that reads obviously
- [ ] No co-authored-by lines in commits
- [ ] Commit messages are short and lowercase

---

## The Contrast Test

**Wrong:**
> This PR introduces a comprehensive refactoring of the coupon
> system, enhancing reliability and ensuring robust validation
> against the Stripe API. Additionally, this change implements
> proper error handling for expired codes.

**Right:**
> - validate coupons against stripe before saving
> - 400 on expired or already-used codes
> - webhook syncs deletions to db
