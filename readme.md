# TestPilot – Setup Guide

Instructions for cloning, installing dependencies and running TestPilot locally.

## Prerequisites

Install:

- [Git](https://git-scm.com/downloads)
- [Python 3.12+](https://www.python.org/downloads/)
- [Node.js LTS](https://nodejs.org/)
- [VS Code](https://code.visualstudio.com/) (recommended)

Check installations:

```powershell
git --version
py --version
node --version
npm --version
```

---

## 1. Clone the Repository

```powershell
git clone YOUR_PUBLIC_REPOSITORY_URL
cd ManchesterGreatUniHack2026
```

## 2. Backend Setup

Run from the repository root:

```powershell
cd backend

py -m venv .venv

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

python -m pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then retry:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Start Backend

From the `backend` directory:

```powershell
python -m uvicorn app.main:app --reload
```

Backend URLs:

- API: http://localhost:8000
- Health: http://localhost:8000/health
- API documentation: http://localhost:8000/docs

Keep this terminal open.

---

## 3. Frontend Setup

Open a **second terminal**.

From the repository root:

```powershell
cd frontend

npm install

npm run dev
```

Frontend URL:

http://localhost:5173

Keep this terminal open.

---

## 4. Running the Application

You need both terminals running simultaneously.

| Service | Command | URL |
|---|---|---|
| Backend | `python -m uvicorn app.main:app --reload` | http://localhost:8000 |
| Frontend | `npm run dev` | http://localhost:5173 |

The backend terminal must have `.venv` activated.

The frontend terminal must be inside the `frontend` directory.

---

## 5. Testing the Application

1. Open http://localhost:5173.
2. Check that the backend status displays `healthy`.
3. Enter the example PR URL:

```text
https://github.com/example/demo-project/pull/12
```

4. Click **Analyse PR**.

The current endpoint returns mock analysis data.

---

## 6. Useful Commands

### Backend

Activate the virtual environment (from `backend`):

```powershell
.\.venv\Scripts\Activate.ps1
```

Install a new Python dependency:

```powershell
python -m pip install PACKAGE_NAME
```

Update requirements after installing dependencies:

```powershell
python -m pip freeze > requirements.txt
```

Run backend tests:

```powershell
python -m pytest
```

Deactivate virtual environment:

```powershell
deactivate
```

### Frontend

Install dependencies:

```powershell
npm install
```

Install a new package:

```powershell
npm install PACKAGE_NAME
```

Run development server:

```powershell
npm run dev
```

Build frontend:

```powershell
npm run build
```

---

## 7. Troubleshooting

**PowerShell won't activate `.venv`:**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Backend says a Python module is missing:**

Make sure `.venv` is activated, then run:

```powershell
python -m pip install -r requirements.txt
```

**Frontend says a package is missing:**

From `frontend`:

```powershell
npm install
```

**Port 8000 or 5173 is already in use:**

Close the other development server using that port before restarting.

**Frontend cannot connect to backend:**

Check that the backend is running at http://localhost:8000 and that `/health` returns a healthy status.

---

## Project Structure

```text
ManchesterGreatUniHack2026/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── requirements.txt
│   └── .venv/
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
├── .gitignore
└── README.md
```