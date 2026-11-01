import json
import os
import time
import logging
from threading import RLock
from typing import Any, Dict, List, Optional

GOALS_FILE = "core/goals.json"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoalManager:
    """
    Manages project goals, including persistence, status, and atomic state.
    """
    def __init__(self) -> None:
        self.lock = RLock()
        self.goals: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        with self.lock:
            if not os.path.exists(GOALS_FILE):
                self.goals = []
                return
            try:
                with open(GOALS_FILE, "r", encoding="utf-8") as f:
                    self.goals = json.load(f) or []
            except Exception as e:
                logger.error(f"Couldn't load goals: {e}")
                self.goals = []

    def save(self) -> None:
        with self.lock:
            os.makedirs(os.path.dirname(GOALS_FILE), exist_ok=True)
            with open(GOALS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.goals, f, indent=2, ensure_ascii=False)

    def add_goal(self, task: str, metadata: Optional[dict]=None) -> Dict[str, Any]:
        with self.lock:
            goal = {
                "id": int(time.time() * 1000),
                "task": task,
                "status": "active",
                "steps": [],
                "completed_steps": [],
                "created": time.time(),
                "updated": time.time(),
                "meta": metadata or {},
            }
            self.goals.append(goal)
            self.save()
            logger.info("Added new goal: %s", task)
            return goal

    def list_goals(self) -> List[Dict[str, Any]]:
        return self.goals

    def get_active(self) -> List[Dict[str, Any]]:
        return [g for g in self.goals if g.get("status") != "done"]

    def get_goal(self, goal_id: int) -> Optional[Dict[str, Any]]:
        for g in self.goals:
            if g.get("id") == goal_id:
                return g
        return None

    def update_goal(self, goal_id: int, **updates) -> Optional[Dict[str, Any]]:
        with self.lock:
            goal = self.get_goal(goal_id)
            if not goal:
                return None
            goal.update(updates)
            goal["updated"] = time.time()
            self.save()
            logger.info("Updated goal: %s", goal_id)
            return goal

    def set_steps(self, goal_id: int, steps: List[str]) -> Optional[Dict[str, Any]]:
        return self.update_goal(goal_id, steps=steps, status="active")

    def mark_done(self, goal_id: int, result: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.update_goal(goal_id, status="done", result=result or "")

    def next_unfinished_step(self, goal_id: int) -> Optional[tuple]:
        goal = self.get_goal(goal_id)
        if not goal:
            return None
        steps = goal.get("steps", [])
        completed = set(goal.get("completed_steps", []))
        for i, step in enumerate(steps):
            if i not in completed:
                return i, step
        return None

    def mark_step_complete(self, goal_id: int, step_index: int, result: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            goal = self.get_goal(goal_id)
            if not goal:
                return None
            goal.setdefault("completed_steps", []).append(step_index)
            goal.setdefault("step_results", []).append({
                "step_index": step_index,
                "step": goal.get("steps", [])[step_index] if step_index < len(goal.get("steps", [])) else "",
                "result": result,
                "timestamp": time.time(),
            })
            goal["updated"] = time.time()
            self.save()
            logger.info("Marked step complete for goal: %s step %s", goal_id, step_index)
            return goal