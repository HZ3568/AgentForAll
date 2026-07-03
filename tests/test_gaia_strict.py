from pathlib import Path

from codeagent.evaluation.gaia.evaluator import GAIAEvaluator
from codeagent.evaluation.gaia.run_eval import write_json
from codeagent.tools.results import FailureType


class DummyDataset:
    def load(self):
        return [
            {
                "task_id": "task-1",
                "question": "What is 6 times 7?",
                "level": 1,
                "final_answer": "42",
            }
        ]


class GuessingAgent:
    name = "guessing-agent"

    def begin_sample(self, sample, scratch_dir):
        self.scratch_dir = scratch_dir
        scratch_dir.mkdir(parents=True, exist_ok=True)

    def run(self, prompt):
        del prompt
        return "FINAL ANSWER: 42"

    def get_sample_metadata(self):
        return {
            "evidence": [],
            "evidence_count": 0,
            "tool_errors": [],
            "tools_used": [],
            "scratch_dir": str(self.scratch_dir),
            "trace": [{"role": "assistant", "content": "FINAL ANSWER: 42"}],
        }


def test_gaia_strict_requires_evidence_and_creates_scratch(tmp_path: Path):
    evaluator = GAIAEvaluator(
        dataset=DummyDataset(),
        level=1,
        output_root=tmp_path / "gaia_runs",
        gaia_eval_mode="strict",
    )

    results = evaluator.evaluate(GuessingAgent())
    detail = results["detailed_results"][0]

    assert detail["status"] == "unresolved"
    assert detail["failure_type"] == FailureType.INSUFFICIENT_EVIDENCE.value
    assert detail["prediction"] == "UNRESOLVED"
    assert detail["evidence_count"] == 0
    assert Path(detail["scratch_dir"]).exists()
    assert (tmp_path / "gaia_runs" / "task-1" / "result.json").exists()
    assert (tmp_path / "gaia_runs" / "task-1" / "trace.json").exists()


def test_failure_summary_file_can_be_generated(tmp_path: Path):
    summary = {
        "total_samples": 1,
        "failure_breakdown": {FailureType.INSUFFICIENT_EVIDENCE.value: 1},
    }
    output = tmp_path / "gaia_failure_summary.json"

    write_json(output, summary)

    assert output.exists()
    assert FailureType.INSUFFICIENT_EVIDENCE.value in output.read_text(encoding="utf-8")
