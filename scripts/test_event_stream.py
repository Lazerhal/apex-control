"""Check that a note created through the API reaches the event stream within 2 seconds.

    .venv/bin/python scripts/test_event_stream.py
    .venv/bin/python scripts/test_event_stream.py --base-url http://127.0.0.1:3000/api/proxy

Uses the token in APEX_TOKEN, or asks for the dashboard login.
Without --project-id it creates a temporary project and deletes it afterwards.
"""
import argparse
import asyncio
import getpass
import json
import os
import sys
import time
import uuid

import httpx

LIMIT_SECONDS = 2.0


async def get_token(client: httpx.AsyncClient) -> str:
    if os.getenv("APEX_TOKEN"):
        return os.environ["APEX_TOKEN"]
    username = input("Dashboard username: ")
    password = getpass.getpass("Dashboard password: ")
    res = await client.post("/auth/login", json={"username": username, "password": password})
    res.raise_for_status()
    return res.json()["access_token"]


async def run(base_url: str, project_id: str | None) -> float:
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        client.headers["Authorization"] = f"Bearer {await get_token(client)}"
        temporary = project_id is None
        if temporary:
            res = await client.post("/api/projects", json={
                "name": f"stream-test-{uuid.uuid4().hex[:8]}", "type": "infrastructure"})
            res.raise_for_status()
            project_id = res.json()["id"]
        try:
            async with client.stream("GET", "/api/events/stream") as stream:
                stream.raise_for_status()
                content_type = stream.headers.get("content-type", "")
                if not content_type.startswith("text/event-stream"):
                    raise RuntimeError(f"Not an event stream: {content_type}")
                lines = stream.aiter_lines()
                # The first comment means the server is listening
                await asyncio.wait_for(anext(lines), 10)

                async def create_note_and_wait() -> None:
                    res = await client.post(f"/api/projects/{project_id}/notes", json={
                        "content": "event stream test", "source": "stream-test"})
                    res.raise_for_status()
                    note_id = res.json()["id"]
                    async for line in lines:
                        if line.startswith("data:"):
                            event = json.loads(line[5:])
                            if event["kind"] == "note.created" and event["payload"].get("note_id") == note_id:
                                return
                    raise RuntimeError("Stream closed before the event arrived")

                start = time.monotonic()
                await asyncio.wait_for(create_note_and_wait(), LIMIT_SECONDS)
                return time.monotonic() - start
        finally:
            if temporary:
                res = await client.delete(f"/api/projects/{project_id}")
                if res.is_error:
                    print(f"Could not delete temporary project {project_id}: {res.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--project-id", help="add the note to this project (the note stays there)")
    args = parser.parse_args()
    try:
        elapsed = asyncio.run(run(args.base_url, args.project_id))
    except asyncio.TimeoutError:
        print(f"FAIL: no event within {LIMIT_SECONDS:.0f}s")
        return 1
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    print(f"PASS: note.created arrived in {elapsed:.3f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
