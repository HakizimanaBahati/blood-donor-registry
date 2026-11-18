# Bug report template

Copy this block into a new issue. Redact tokens and personal donor data.

````markdown
## Summary
<!-- One sentence: what went wrong? -->

## Environment
- Date/time:
- Browser + version:
- OS:
- Frontend URL: http://127.0.0.1:3000/...
- Backend URL: http://127.0.0.1:8000
- Signed-in role: admin / hospital
- Demo account (if used): admin / hospital1 / hospital2

## Steps to reproduce
1.
2.
3.

## Expected result
<!-- What should have happened? -->

## Actual result
<!-- What happened instead? Include error text. -->

## Network evidence
- Method + path:
- HTTP status:
- Request payload (redacted):
- Response body (redacted):
- Authorization header present? yes / no   <-- do NOT paste the token

## Screenshots
<!-- Attach screenshots with personal data blurred. -->

## Console output
```text
<paste console errors here>
```

## Suspected layer
- [ ] Frontend rendering / state
- [ ] API validation / permissions
- [ ] Database / RLS / seed data
- [ ] Authentication / JWT
- [ ] Unknown

## Impact
<!-- Who is blocked and how severely? -->
````

## Useful details to include

- The exact donor/request UUID (these are fictional seed IDs).
- Whether the same action works with the other role.
- A link to [NETWORK_TAB_GUIDE.md](NETWORK_TAB_GUIDE.md) if the reporter needs help
  collecting evidence.
- The verification command that failed, if the bug is in the backend or database.
