from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from codeagent.evaluation.gaia.dataset import GAIADataset
from codeagent.evaluation.gaia.evaluator import GAIAEvaluator


GAIA_INSTRUCTION = """\
You are being evaluated on GAIA.
Use available tools when they are useful. If a referenced file is provided, inspect it before answering.
End your response with exactly one final answer line:
FINAL ANSWER: <answer>
"""

GAIA_STRICT_INSTRUCTION = """\
You are in GAIA evaluation mode.
Do not answer from vague memory.
Every final answer must be grounded in observed tool output.
If required evidence is unavailable after trying relevant tools, return exactly:
FINAL ANSWER: UNRESOLVED
Keep the final answer concise and match the requested answer format exactly.
Todo state is not evidence.
"""


class CodeAgentGAIAAdapter:
    """Expose the project agent loop through the run(prompt) interface GAIAEvaluator expects."""

    name = "CodeAgent-Harness"

    def __init__(
        self,
        config_path: str | None = None,
        enable_memory: bool = False,
        enable_cron: bool = False,
        gaia_eval_mode: str = "off",
    ) -> None:
        from codeagent.core.runtime import create_runtime

        self.runtime = create_runtime(config_path)
        self.gaia_eval_mode = gaia_eval_mode
        if gaia_eval_mode != "off":
            self.runtime.mode = "gaia_eval"
            self.runtime.gaia_eval_mode = gaia_eval_mode
            self.runtime.allow_project_writes = False
        self._isolate_runtime(enable_memory=enable_memory, enable_cron=enable_cron)
        self._trace: list[dict[str, Any]] = []

    def _isolate_runtime(self, enable_memory: bool, enable_cron: bool) -> None:
        if not enable_memory:
            self.runtime.memory.build_context = lambda *args, **kwargs: ""
            self.runtime.memory.extract_new_memories = lambda *args, **kwargs: 0
            self.runtime.memory.consolidate_memories = lambda *args, **kwargs: None

        if not enable_cron:
            with self.runtime.cron.lock:
                self.runtime.cron.jobs.clear()
                self.runtime.cron.queue.clear()

    def begin_sample(self, sample: dict[str, Any], scratch_dir: Path) -> None:
        self.runtime.current_task_id = sample.get("task_id")
        self.runtime.current_scratch_dir = str(scratch_dir.resolve())
        self.runtime.reset_tool_tracking()
        self._trace = []

    def run(self, prompt: str) -> str:
        from codeagent.core.context import extract_text
        from codeagent.core.loop import agent_loop

        self.runtime.current_todos = []
        self.runtime.rounds_since_todo = 0
        self.runtime.background.collect_results()
        self.runtime.cron.consume()

        instruction = (
            GAIA_STRICT_INSTRUCTION
            if self.gaia_eval_mode == "strict"
            else GAIA_INSTRUCTION
        )
        scratch_note = (
            f"\n\nScratch directory for temporary files: {self.runtime.current_scratch_dir}"
            if self.runtime.current_scratch_dir
            else ""
        )
        history = [
            {"role": "user", "content": f"{prompt}\n\n{instruction}{scratch_note}"}
        ]
        context = self.runtime.update_context({}, history)

        with self.runtime.agent_lock:
            agent_loop(self.runtime, history, context)
        self._trace = history

        assistant_texts = [
            extract_text(message.get("content", ""))
            for message in history
            if message.get("role") == "assistant"
        ]
        return "\n\n".join(text for text in assistant_texts if text)

    def get_sample_metadata(self) -> dict[str, Any]:
        return {
            "evidence": [item.to_dict() for item in self.runtime.evidence],
            "evidence_count": len(self.runtime.evidence),
            "tool_errors": list(self.runtime.tool_errors),
            "tools_used": list(self.runtime.tools_used),
            "scratch_dir": self.runtime.current_scratch_dir,
            "trace": self._trace,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run GAIA evaluation for CodeAgent-Harness."
    )
    parser.add_argument(
        "--config", default=None, help="Path to config.yaml. Defaults to ./config.yaml."
    )
    parser.add_argument(
        "--dataset-name",
        default="gaia-benchmark/GAIA",
        help="HuggingFace dataset name.",
    )
    parser.add_argument(
        "--split",
        default="validation",
        choices=("validation", "test"),
        help="GAIA split.",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="Optional GAIA level filter.",
    )
    parser.add_argument(
        "--local-data-dir",
        default=None,
        help="Use a local GAIA data directory instead of HuggingFace.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit sample count for smoke tests.",
    )
    parser.add_argument("--loose", action="store_true", help="Use loose matching mode.")
    parser.add_argument(
        "--enable-memory",
        action="store_true",
        help="Enable memory context and memory writes during eval.",
    )
    parser.add_argument(
        "--enable-cron",
        action="store_true",
        help="Allow scheduled cron jobs during eval.",
    )
    parser.add_argument(
        "--output",
        default="outputs/gaia_results.json",
        help="Detailed JSON result path.",
    )
    parser.add_argument(
        "--gaia-output",
        default="outputs/gaia_submission.jsonl",
        help="GAIA JSONL export path.",
    )
    parser.add_argument(
        "--no-gaia-output", action="store_true", help="Skip GAIA JSONL export."
    )
    parser.add_argument(
        "--no-reasoning-trace",
        action="store_true",
        help="Do not include response traces in JSONL export.",
    )
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        help="Only download/load GAIA data and print statistics.",
    )
    parser.add_argument(
        "--gaia-eval-mode",
        choices=("off", "strict"),
        default="strict" if os.getenv("CODEAGENT_MODE") == "gaia_eval" else "off",
        help="Enable GAIA-specific strict evidence mode.",
    )
    parser.add_argument(
        "--run-output-root",
        default="outputs/gaia_runs",
        help="Per-sample GAIA run artifact root.",
    )
    parser.add_argument(
        "--failure-summary-output",
        default="outputs/gaia_failure_summary.json",
        help="Failure summary JSON path.",
    )
    return parser


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[OK] 详细结果已保存: {output_path}")


def main() -> None:
    args = build_parser().parse_args()

    dataset = GAIADataset(
        dataset_name=args.dataset_name,
        split=args.split,
        level=args.level,
        local_data_dir=args.local_data_dir,
    )

    if args.dataset_only:
        dataset.load()
        stats = dataset.get_statistics()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    evaluator = GAIAEvaluator(
        dataset=dataset,
        level=args.level,
        strict_mode=not args.loose,
        output_root=args.run_output_root,
        gaia_eval_mode=args.gaia_eval_mode,
    )
    agent = CodeAgentGAIAAdapter(
        config_path=args.config,
        enable_memory=args.enable_memory,
        enable_cron=args.enable_cron,
        gaia_eval_mode=args.gaia_eval_mode,
    )

    results = evaluator.evaluate(agent, max_samples=args.max_samples)
    write_json(args.output, results)
    write_json(
        args.failure_summary_output,
        {
            "total_samples": results.get("total_samples", 0),
            "exact_match_rate": results.get("exact_match_rate", 0.0),
            "partial_match_rate": results.get("partial_match_rate", 0.0),
            "failure_breakdown": results.get("failure_breakdown", {}),
        },
    )

    if not args.no_gaia_output:
        evaluator.export_to_gaia_format(
            results,
            args.gaia_output,
            include_reasoning=not args.no_reasoning_trace,
        )


# python -m codeagent.evaluation.gaia.run_eval --level 1
if __name__ == "__main__":
    main()
