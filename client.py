"""
Test client — exercises every endpoint in the Task Management API.
Run with the server already up:  python client.py
"""

import random
import string
import requests

BASE = "http://127.0.0.1:8000"

# Helpers ----------------------------------------------------------------

def rand_str(n=6):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def header(token):
    return {"Authorization": f"Bearer {token}"}


def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


def show(label, resp):
    status = resp.status_code
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    print(f"  [{status}] {label}")
    if isinstance(body, dict):
        for k, v in body.items():
            print(f"         {k}: {v}")
    elif isinstance(body, list):
        print(f"         ({len(body)} items)")
        for item in body[:3]:
            print(f"         - {item}")
    else:
        print(f"         {body}")
    print()
    return body


# ========================================================================
#  1. AUTH
# ========================================================================
section("AUTH — Signup, Login, Verify")

username = f"testuser_{rand_str()}"
email = f"{username}@example.com"
password = "SecurePass123!"

# Signup
r = requests.post(f"{BASE}/auth/signup", json={
    "username": username,
    "email": email,
    "password": password,
})
user = show("POST /auth/signup", r)

# Signup duplicate (expect 400)
r = requests.post(f"{BASE}/auth/signup", json={
    "username": username,
    "email": email,
    "password": password,
})
show("POST /auth/signup (duplicate — expect 400)", r)

# Login
r = requests.post(f"{BASE}/auth/login", json={
    "username": username,
    "password": password,
})
tokens = show("POST /auth/login", r)
TOKEN = tokens["access_token"]

# Login bad password (expect 401)
r = requests.post(f"{BASE}/auth/login", json={
    "username": username,
    "password": "wrong",
})
show("POST /auth/login (bad password — expect 401)", r)

# Verify token
r = requests.post(f"{BASE}/auth/verify", json={"token": TOKEN})
show("POST /auth/verify (valid token)", r)

r = requests.post(f"{BASE}/auth/verify", json={"token": "invalid.jwt.token"})
show("POST /auth/verify (invalid token)", r)

# ========================================================================
#  2. USERS
# ========================================================================
section("USERS — Profile, Leaderboard")

# Get me
r = requests.get(f"{BASE}/users/me", headers=header(TOKEN))
show("GET /users/me", r)

# Update profile
r = requests.post(f"{BASE}/users/profile", headers=header(TOKEN), json={
    "skills": ["python", "fastapi", "postgresql"],
    "interests": ["backend", "devops"],
    "bio": "Full-stack engineer who loves building APIs.",
})
show("POST /users/profile", r)

# Get me again (should reflect updates)
r = requests.get(f"{BASE}/users/me", headers=header(TOKEN))
show("GET /users/me (after update)", r)

# Leaderboard (public)
r = requests.get(f"{BASE}/users/leaderboard")
show("GET /users/leaderboard", r)

# ========================================================================
#  3. TASKS
# ========================================================================
section("TASKS — CRUD")

# Create task
r = requests.post(f"{BASE}/tasks", headers=header(TOKEN), json={
    "title": "Build REST API",
    "description": "Implement all CRUD endpoints for the project.",
    "required_skills": ["python", "fastapi"],
    "max_assignees": 2,
    "point_value": 50,
})
task = show("POST /tasks (create)", r)
TASK_ID = task["id"]

# Create a second task
r = requests.post(f"{BASE}/tasks", headers=header(TOKEN), json={
    "title": "Write unit tests",
    "description": "Achieve 90% coverage.",
    "required_skills": ["pytest"],
    "max_assignees": 1,
    "point_value": 30,
})
show("POST /tasks (create #2)", r)

# List tasks
r = requests.get(f"{BASE}/tasks", headers=header(TOKEN))
show("GET /tasks (list all open)", r)

# Get single task
r = requests.get(f"{BASE}/tasks/{TASK_ID}", headers=header(TOKEN))
show(f"GET /tasks/{TASK_ID} (detail)", r)

# Get non-existent task (expect 404)
r = requests.get(f"{BASE}/tasks/99999", headers=header(TOKEN))
show("GET /tasks/99999 (expect 404)", r)

# ========================================================================
#  4. TASK WORKFLOW — Claim → Start → Complete → Award Points
# ========================================================================
section("TASK WORKFLOW — Claim, Start, Complete, Award Points")

# Claim
r = requests.post(f"{BASE}/tasks/{TASK_ID}/claim", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/claim", r)

# Claim again (expect 400 — already claimed)
r = requests.post(f"{BASE}/tasks/{TASK_ID}/claim", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/claim (duplicate — expect 400)", r)

# Start
r = requests.post(f"{BASE}/tasks/{TASK_ID}/start", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/start", r)

# Start again (expect 400 — already started)
r = requests.post(f"{BASE}/tasks/{TASK_ID}/start", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/start (duplicate — expect 400)", r)

# Complete
r = requests.post(f"{BASE}/tasks/{TASK_ID}/complete", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/complete", r)

# Award points
r = requests.post(f"{BASE}/tasks/{TASK_ID}/award-points", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/award-points", r)

# Award points again (expect 400 — idempotency guard)
r = requests.post(f"{BASE}/tasks/{TASK_ID}/award-points", headers=header(TOKEN))
show(f"POST /tasks/{TASK_ID}/award-points (duplicate — expect 400)", r)

# ========================================================================
#  5. VERIFY POINTS CREDITED
# ========================================================================
section("VERIFY — Points credited to user")

r = requests.get(f"{BASE}/users/me", headers=header(TOKEN))
me = show("GET /users/me (after award)", r)
print(f"  >>> Points balance: {me['points']}  (expected: 50)")

r = requests.get(f"{BASE}/users/leaderboard")
show("GET /users/leaderboard (final)", r)

print("\n" + "="*60)
print("  ALL TESTS COMPLETE")
print("="*60 + "\n")
