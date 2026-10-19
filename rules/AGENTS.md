# Replica Clean-Room and Safety Rules

These rules apply whenever the Replica skill pack is active.

## 1. Clean-Room Principles
- Rebuild functionality and UX patterns only. Never copy proprietary source code, private APIs, SVGs, images, sounds, or licensed copy.
- Write every screen, state, schema definition, and component fresh from recon specifications.
- Match what components do, not their exact proprietary implementation.

## 2. Authorized Research Only
- Work only from public sources (documentation, help centers, pricing pages, public walkthroughs, public review feeds) and the user's own authorized account.
- Never bypass a paywall, trick an authentication gate, or scrape behind unauthorized logins.
- Respect terms of service. If an account's terms forbid competitor research, rely strictly on public sources.

## 3. Grounded Entrepreneurship
- Never fabricate reviews, quotes, ratings, user counts, or customer feedback.
- Every quote in `replica/reviews.csv` and `replica/feedback.md` must be verbatim and accompanied by its public URL.
- Never create fake reviews for your app or against the target app.
- Do not use customer reviews as marketing testimonials on landing pages.

## 4. Rebranding and Intellectual Property
- Never ship under the target app's name, trademark, or trade dress.
- Always generate a fresh color palette verified for WCAG contrast.
- Run the sweep verification tool (`sweep.py`) before deployment to guarantee that all target brand names, domains, and signature colors have been purged.

## 5. Security and Keys
- Never request, store, or hardcode private API keys, user passwords, or live credit card credentials.
- Document required environment variables in `.env.example` and instruct the user to configure `.env.local`.
- Test payments using official provider sandbox/test keys only.
