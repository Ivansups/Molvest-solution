## 1. Guest feedback and reset

- [x] 1.1 Render a pending in-transcript indicator for text generation and Vision analysis.
- [x] 1.2 Render sources as expandable controls that reveal `chunk_text`.
- [x] 1.3 Add a guest-only New conversation CTA and a `useConversation` reset method.
- [x] 1.4 Guard the reset flow against late responses from the previous request.
- [x] 1.5 Mark guest composer controls as `type="button"` to avoid native form submission.

## 2. Runtime and motion

- [x] 2.1 Allow `127.0.0.1` through Next.js `allowedDevOrigins` for local Docker development.
- [x] 2.2 Add shared entrance motion and reduced-motion support.
- [x] 2.3 Apply shared motion to cards, headers, navigation, tables, dialogs, source bubbles and guest CTA.

## 3. Verification

- [x] 3.1 Run frontend ESLint, TypeScript and Vitest.
- [x] 3.2 Run the frontend production build.
- [x] 3.3 Run Docker Compose and manually verify interactive guest chat request reaches `POST /chat`.
