"""File store for the corpus and the results, as readable JSON.

The corpus and the results are published in the repository, so everything is
plain JSON that git can diff. Seeds and run traces live in separate folders, so
a run trace can never be mistaken for a seed.

    <root>/corpus/seeds/<trace_id>.json
    <root>/corpus/scenarios/<scenario_id>.json
    <root>/results/runs/<run_id>/manifest.json
    <root>/results/runs/<run_id>/traces/<trace_id>.json
    <root>/results/runs/<run_id>/verdicts/<trace_id>.json
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from agentproof.schema import RunManifest, Scenario, Trace, Verdict


def _write(path: Path, model: BaseModel) -> None:
    """Write atomically, so an interrupted run never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read[M: BaseModel](path: Path, cls: type[M]) -> M:
    return cls.model_validate_json(path.read_text(encoding="utf-8"))


def _read_all[M: BaseModel](folder: Path, cls: type[M]) -> list[M]:
    if not folder.is_dir():
        return []
    return [_read(path, cls) for path in sorted(folder.glob("*.json"))]


class Store:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.seeds_dir = self.root / "corpus" / "seeds"
        self.scenarios_dir = self.root / "corpus" / "scenarios"
        self.runs_dir = self.root / "results" / "runs"

    def save_seed(self, trace: Trace) -> Path:
        if trace.kind != "seed":
            raise ValueError(f"not a seed trace: {trace.trace_id}")
        path = self.seeds_dir / f"{trace.trace_id}.json"
        _write(path, trace)
        return path

    def seeds(self) -> list[Trace]:
        return sorted(_read_all(self.seeds_dir, Trace), key=lambda t: t.started_at)

    def has_scenario(self, scenario_id: str) -> bool:
        return (self.scenarios_dir / f"{scenario_id}.json").exists()

    def save_scenario(self, scenario: Scenario, *, overwrite: bool = False) -> bool:
        """Save the scenario; returns ``False`` if it already existed and was kept."""
        if self.has_scenario(scenario.scenario_id) and not overwrite:
            return False
        _write(self.scenarios_dir / f"{scenario.scenario_id}.json", scenario)
        return True

    def scenario(self, scenario_id: str) -> Scenario:
        if not self.has_scenario(scenario_id):
            raise KeyError(scenario_id)
        return _read(self.scenarios_dir / f"{scenario_id}.json", Scenario)

    def scenarios(self) -> list[Scenario]:
        return _read_all(self.scenarios_dir, Scenario)

    def _manifest_path(self, run_id: str) -> Path:
        return self.runs_dir / run_id / "manifest.json"

    def _require_run(self, run_id: str) -> Path:
        if not self._manifest_path(run_id).exists():
            raise KeyError(run_id)
        return self.runs_dir / run_id

    def create_run(self, manifest: RunManifest) -> Path:
        path = self._manifest_path(manifest.run_id)
        if path.exists():
            raise FileExistsError(f"run already exists: {manifest.run_id}")
        _write(path, manifest)
        return path.parent

    def manifest(self, run_id: str) -> RunManifest:
        return _read(self._require_run(run_id) / "manifest.json", RunManifest)

    def runs(self) -> list[str]:
        if not self.runs_dir.is_dir():
            return []
        return sorted(p.parent.name for p in self.runs_dir.glob("*/manifest.json"))

    def save_run_trace(self, trace: Trace) -> Path:
        if trace.kind != "run" or trace.run_id is None:
            raise ValueError(f"not a run trace: {trace.trace_id}")
        path = self._require_run(trace.run_id) / "traces" / f"{trace.trace_id}.json"
        _write(path, trace)
        return path

    def run_traces(self, run_id: str) -> list[Trace]:
        traces = _read_all(self._require_run(run_id) / "traces", Trace)
        return sorted(traces, key=lambda t: (t.scenario_id or "", t.repetition or 0))

    def has_verdict(self, run_id: str, trace_id: str) -> bool:
        return (self.runs_dir / run_id / "verdicts" / f"{trace_id}.json").exists()

    def save_verdict(self, verdict: Verdict) -> Path:
        """One verdict per trace: judging a trace again replaces its verdict."""
        path = self._require_run(verdict.run_id) / "verdicts" / f"{verdict.trace_id}.json"
        _write(path, verdict)
        return path

    def verdicts(self, run_id: str) -> list[Verdict]:
        return _read_all(self._require_run(run_id) / "verdicts", Verdict)
