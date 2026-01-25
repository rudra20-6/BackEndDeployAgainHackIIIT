# Backend — KMS

This folder contains backend services for the KMS project. There are two server entry points in this repo: a Node/Express service (`server.js`) and a Flask service (`flask_server.py`). The Node/Express server is the primary API used by the mobile app; the Flask server exists for legacy/testing purposes.

Quick links
- Server entry (Node): [backend/server.js](backend/server.js)
- Flask entry (optional): [backend/flask_server.py](backend/flask_server.py)
- DB config: [backend/config/db.js](backend/config/db.js)

Folder layout
- `config/` — database and environment configuration.
- `middleware/` — Express middleware (auth, logging, validation).
- `models/` — Mongoose models for `User`, `Canteen`, `MenuItem`, `Order`, `Payment`.
- `routes/` — Express route handlers grouped by resource (auth, canteens, menu, orders, payments).
- `utils/` — helper utilities (e.g., `logger.js`).
- tests / scripts — small test files such as `test-auth.js`.

How to run (Node/Express)

1. Install dependencies

```powershell
cd backend
npm install
```

2. Configure environment

- Create a `.env` in `backend/` or set environment variables. Typical variables:

```
PORT=5000
MONGODB_URI=mongodb://localhost:27017/kms
JWT_SECRET=your_secret
```

3. Start the server

```powershell
node server.js
# or use a process manager / nodemon for development
npx nodemon server.js
```

4. Health check

- Visit `http://localhost:5000/` (or the configured port) to see the API.

How to run (Flask)

The Flask service is optional. To run:

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements_flask.txt
python flask_server.py
```

Notes on development
- Add new routes under `routes/` and export them from the primary server entry.
- Models are defined in `models/` as Mongoose schemas — use consistent naming and include validation there.
- Authentication middleware is in `middleware/auth.js` and uses JWT.

Testing
- There are small test files such as `test-auth.js`. Run them with `node` or your test runner of choice.

Useful files
- [backend/config/db.js](backend/config/db.js) — DB connection logic
- [backend/middleware/auth.js](backend/middleware/auth.js) — authentication middleware
- [backend/routes/auth.js](backend/routes/auth.js) — auth endpoints

If you want, I can add example `.env.example` and a script to launch the complete dev environment.
