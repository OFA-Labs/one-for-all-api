# C6 — Identity, Sign-In, Credentials
**Purpose:** §5 C6, §8 · **Depends on:** 05, 04 · **Files likely touched:** `api/ofa/signin.py`, `api/ofa/vault/*` · **Done when:** M08 rows I1–I7 pass.

- Order: existing session → password-manager handle → vault handle → SSO button when that identity's session exists.
- Explicit "sign in to X" = Tier 1 for that verified origin only; unrequested sign-in → ask first.
- Multiple accounts → spoken choice (labels only).
- Handoffs: CAPTCHA, passkey, Windows Hello, biometric, device approval → orb "your turn" + speech; resume when page state changes (success marker) or the user says "done / ho gaya".
- OTP from the user's email/SMS only with per-instance Tier 2 approval; TOTP seed (D3) Tier 2 per use.
- Account creation, password change, new permission grants = Tier 2. Never evade bot detection.
