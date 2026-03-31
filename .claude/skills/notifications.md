---
description: Review and triage Icarus notifications by severity, type, and ticker.
user_invocable: true
---

# /notifications

1. Fetch unread overview: GET /notifications/unread
   - Count by severity (critical, warning, info)

2. List critical alerts first: GET /notifications/?severity=critical&unread_only=true
   - Present each in full immediately

3. List warnings: GET /notifications/?severity=warning&unread_only=true&limit=20
   - Group by type, one-line summary each

4. Filter options (apply if user specifies):
   - By type: GET /notifications/?type={type}
   - By ticker: GET /notifications/?ticker={ticker}

5. Ask user which to mark read:
   - Single: PUT /notifications/{id}/read
   - All: PUT /notifications/read-all (only after explicit confirmation)

Format as triage table: severity, type, ticker, timestamp, message.
