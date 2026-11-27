async def test_empty(client):
    body = (await client.get("/api/dashboard/summary")).json()
    assert body == {
        "projects": {"total": 0, "by_stage": {}},
        "tasks": {"open": 0, "critical": 0},
        "ideas": {"new": 0},
        "recommendations": {"new": 0},
        "financials": {"monthly_cost_usd": 0, "monthly_revenue_usd": 0, "monthly_profit_usd": 0},
    }


async def test_counts_and_money(client, project):
    live = (await client.post("/api/projects", json={
        "name": "b", "type": "saas", "stage": "live",
        "monthly_cost_usd": 10, "monthly_revenue_usd": 25})).json()
    tasks = f"/api/projects/{live['id']}/tasks"
    await client.post(tasks, json={"title": "x", "priority": "critical"})
    done = (await client.post(tasks, json={"title": "y"})).json()
    await client.patch(f"{tasks}/{done['id']}", json={"status": "done"})
    await client.post(f"/api/projects/{project['id']}/tasks", json={"title": "z"})
    await client.post("/api/ideas", json={"title": "i", "raw_description": "d"})
    body = (await client.get("/api/dashboard/summary")).json()
    assert body["projects"] == {"total": 2, "by_stage": {"planning": 1, "live": 1}}
    assert body["tasks"] == {"open": 2, "critical": 1}
    assert body["ideas"] == {"new": 1}
    assert body["financials"] == {
        "monthly_cost_usd": 10, "monthly_revenue_usd": 25, "monthly_profit_usd": 15}


async def test_deleted_projects_leave_project_counts_and_money(client):
    gone = (await client.post("/api/projects", json={
        "name": "g", "type": "saas", "monthly_cost_usd": 99})).json()
    await client.delete(f"/api/projects/{gone['id']}")
    body = (await client.get("/api/dashboard/summary")).json()
    assert body["projects"]["total"] == 0 and body["financials"]["monthly_cost_usd"] == 0
