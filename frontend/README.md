# AgentForAll Frontend

React + Vite + TypeScript frontend for the formal AgentForAll Web layer.

## Development

```bash
npm install
npm run dev
```

Set the API base URL in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

The frontend only talks to `backend` APIs. It must not import or call `codeagent`.
