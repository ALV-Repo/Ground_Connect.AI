# GroundConnect AI — Frontend v4

## Quick Start

```bash
npm install
npm run dev     # → http://localhost:5173
npm run build   # → /dist (production bundle)
```

## Demo credentials

| Role | Mobile | Password | OTP / MFA |
|---|---|---|---|
| Leader | +91 98765 00005 | demo1234 | any 6 digits |
| Coordinator | +91 98765 00006 | demo1234 | any 6 digits |
| Field Worker | +91 98765 00007 | demo1234 | any 6 digits |
| Citizen | +91 98765 00008 | demo1234 | any 6 digits |
| Org Admin | +91 98765 00002 | demo1234 | any 6 digits |
| Compliance | +91 98765 00003 | demo1234 | any 6 digits |
| Security Admin | +91 98765 00004 | demo1234 | any 6 digits |
| Platform Operator | +91 98765 00001 | demo1234 | any 6 digits |
| Integration Client | +91 98765 00009 | demo1234 | any 6 digits |

OTP and MFA: enter any 6-digit code except 000000.

## AI features setup

AI features work in two modes:

**Demo mode (no key needed):** All AI screens are fully visible and show
realistic deterministic responses labelled AID-05 FALLBACK. The full UI
is demonstrable without any API key.

**Live mode (real AI responses):**
1. Get an API key from https://console.anthropic.com
2. Open the `.env` file in the project root
3. Set `VITE_ANTHROPIC_API_KEY=sk-ant-your-actual-key`
4. Save and restart `npm run dev`

Never commit your `.env` file — it is in `.gitignore`.

## Tech stack

- React 18 · Vite 5 · Tailwind CSS 3
- Recharts (charts) · Lucide React (icons)
- Anthropic claude-sonnet-4-6 (AI features)

## Project structure

```
src/
  App.jsx                    Main shell, routing, sidebar
  index.css                  Design system (Tailwind + components)
  data/index.js              All mock data (replace with API calls)
  components/
    UI.jsx                   Shared UI primitives
    Charts.jsx               Chart components
    OrgTree.jsx              Recursive org tree
    AIModule.jsx             Full AI module (AI-01→09, AIB/AIC/AID)
  pages/
    Auth.jsx                 4-step MFA auth flow
    Supplements.jsx          SDI, geo view, messages, notifications,
                             language, TPI, offline, evidence screens
    roles/
      Leader.jsx             Leader role (10 screens)
      AllRoles.jsx           All other 8 roles
```

## Connecting to backend

Every page imports mock data from `src/data/index.js`.
Replace each import with a fetch() call to your FastAPI backend.
The mock data shape is your API contract.

Example:
```js
// Before (mock)
import { TASKS } from '../../data'

// After (live backend)
const [tasks, setTasks] = useState([])
useEffect(() => {
  fetch('/api/v1/tasks', { headers: { Authorization: `Bearer ${token}` } })
    .then(r => r.json()).then(setTasks)
}, [])
```
