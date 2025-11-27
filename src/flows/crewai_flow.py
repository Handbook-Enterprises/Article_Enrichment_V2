import os
import json
import logging
from typing import Dict, Any

import redis
from crewai import Agent, Task, Crew


class CrewFlow:
    def __init__(self):
        self.redis_url = os.getenv("FLOW_REDIS_URL", "redis://localhost:6379/2")
        
        # Redis connection for state persistence
        self.redis_client = None
        self.enabled = False
        if self.redis_url:
            try:
                self.redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
                self.redis_client.ping()
                self.enabled = True
            except Exception as e:
                logging.warning(f"CrewAI flow | Redis connection failed: {e}, persistence disabled")
                self.redis_client = None
                self.enabled = False
        
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.agent = None
        self.llm_enabled = False
        if api_key:
            try:
                self.agent = Agent(
                    role="Flow Orchestrator",
                    goal="Persist pipeline step summaries for observability",
                    backstory="A lightweight orchestration agent that records each pipeline step into a shared store.",
                    verbose=False,
                )
                self.llm_enabled = True
            except Exception as e:
                logging.warning(f"CrewAI flow | Failed to initialize Flow Orchestrator Agent: {e}")
                self.agent = None
                self.llm_enabled = False
        
        logging.info(
            f"CrewAI flow init | redis_url={self.redis_url} | redis_enabled={'yes' if self.enabled else 'no'} | llm_enabled={'yes' if self.llm_enabled else 'no'}"
        )

    def save(self, run_id: str, step: str, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        key = f"flow:{run_id}:{step}"
        self.redis_client.set(key, json.dumps(payload))
        logging.info(
            f"CrewAI flow save | run_id={run_id} | step={step} | size={len(json.dumps(payload))} | llm_enabled={'yes' if self.llm_enabled else 'no'} | redis_enabled={'yes' if self.enabled else 'no'}"
        )

    def steps(self, run_id: str) -> Dict[str, Any]:
        keys = [k.decode() for k in self.client.keys(f"flow:{run_id}:*")]
        return {k: json.loads(self.client.get(k) or b"{}") for k in keys}


_crew_flow = CrewFlow()


def record_step(step_id: str, payload: Dict[str, Any]) -> None:
    run_id = os.getenv("FLOW_RUN_ID", "default")
    _crew_flow.save(run_id, step_id, payload)
