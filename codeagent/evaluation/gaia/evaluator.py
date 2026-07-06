"""
GAIA 评估器模块

负责评估智能体在 GAIA 基准测试上的表现
"""

from collections import Counter
from typing import Dict, Any, List, Optional, Union
import time
import re
import json
from pathlib import Path
from codeagent.evaluation.gaia.dataset import GAIADataset
from codeagent.evaluation.gaia.metrics import GAIAMetrics
from codeagent.tools.results import FailureType


class GAIAEvaluator:
    """GAIA 评估器

    评估智能体的通用AI助手能力,包括:
    - 问题理解和推理
    - 多步骤问题解决
    - 工具使用能力
    - 答案准确性

    GAIA评估采用严格的答案匹配标准:
    - 精确匹配: 答案完全一致
    - 部分匹配: 答案包含正确信息但格式不同

    Attributes:
        dataset: GAIA 数据集
        metrics: 评估指标计算器
        level: 难度级别
        strict_mode: 是否使用严格匹配模式
    """

    def __init__(
        self,
        dataset: Optional[GAIADataset] = None,
        level: Optional[int] = None,
        local_data_dir: Optional[str] = None,
        strict_mode: bool = True,
        output_root: Union[str, Path] = "outputs/gaia_runs",
        gaia_eval_mode: str = "off",
    ):
        """初始化 GAIA 评估器

        Args:
            dataset: GAIA 数据集,如果为 None 则自动创建
            level: 难度级别 (1-3)
            local_data_dir: 本地数据目录
            strict_mode: 是否使用严格匹配模式
        """
        self.dataset = dataset or GAIADataset(
            level=level, local_data_dir=local_data_dir
        )
        self.metrics = GAIAMetrics()
        self.level = level
        self.strict_mode = strict_mode
        self.output_root = Path(output_root)
        self.gaia_eval_mode = gaia_eval_mode

    def evaluate(self, agent: Any, max_samples: Optional[int] = None) -> Dict[str, Any]:
        """评估智能体

        Args:
            agent: 要评估的智能体
            max_samples: 最大评估样本数,None表示评估全部

        Returns:
            评估结果字典,包含各项指标
        """
        print(f"\n[GAIA] 开始评估...")
        print(f"   智能体: {getattr(agent, 'name', 'Unknown')}")
        print(f"   难度级别: {self.level or '全部'}")
        print(f"   匹配模式: {'严格' if self.strict_mode else '宽松'}")

        # 加载数据集
        dataset = self.dataset.load()
        if not dataset:
            print("   [WARN] 数据集为空,跳过评估")
            return self._create_empty_results(agent)

        # 限制样本数量
        if max_samples:
            dataset = dataset[:max_samples]

        print(f"   样本数量: {len(dataset)}")

        # 执行评估
        results = []
        level_stats = {
            1: {"total": 0, "correct": 0, "partial": 0},
            2: {"total": 0, "correct": 0, "partial": 0},
            3: {"total": 0, "correct": 0, "partial": 0},
        }

        for i, sample in enumerate(dataset):
            if i % 10 == 0:
                print(f"   进度: {i+1}/{len(dataset)}")

            try:
                sample_result = self.evaluate_sample(agent, sample)
                results.append(sample_result)

                # 按级别统计
                level = sample.get("level", 1)
                if level in level_stats:
                    level_stats[level]["total"] += 1
                    if sample_result["exact_match"]:
                        level_stats[level]["correct"] += 1
                    if sample_result["partial_match"]:
                        level_stats[level]["partial"] += 1

            except Exception as e:
                print(f"   [WARN] 样本 {i} 评估失败: {e}")
                results.append(
                    {
                        "exact_match": False,
                        "partial_match": False,
                        "predicted": None,
                        "expected": sample.get("final_answer"),
                        "error": str(e),
                        "score": 0.0,
                    }
                )

        # 计算总体指标
        total_samples = len(results)
        exact_matches = sum(1 for r in results if r["exact_match"])
        partial_matches = sum(1 for r in results if r["partial_match"])

        exact_match_rate = exact_matches / total_samples if total_samples > 0 else 0.0
        partial_match_rate = (
            partial_matches / total_samples if total_samples > 0 else 0.0
        )

        # 计算分级指标
        level_metrics = {}
        for level, stats in level_stats.items():
            if stats["total"] > 0:
                level_metrics[f"Level_{level}"] = {
                    "total": stats["total"],
                    "exact_matches": stats["correct"],
                    "partial_matches": stats["partial"],
                    "exact_match_rate": stats["correct"] / stats["total"],
                    "partial_match_rate": stats["partial"] / stats["total"],
                }

        final_results = {
            "benchmark": "GAIA",
            "agent_name": getattr(agent, "name", "Unknown"),
            "strict_mode": self.strict_mode,
            "level_filter": self.level,
            "total_samples": total_samples,
            "exact_matches": exact_matches,
            "partial_matches": partial_matches,
            "exact_match_rate": exact_match_rate,
            "partial_match_rate": partial_match_rate,
            "level_metrics": level_metrics,
            "failure_breakdown": self._failure_breakdown(results),
            "detailed_results": results,
        }

        print(f"[OK] GAIA 评估完成")
        print(f"   精确匹配率: {exact_match_rate:.2%}")
        print(f"   部分匹配率: {partial_match_rate:.2%}")
        for level_name, metrics in level_metrics.items():
            print(
                f"   {level_name}: {metrics['exact_match_rate']:.2%} 精确 / {metrics['partial_match_rate']:.2%} 部分"
            )
        self._print_failure_summary(results)

        return final_results

    def evaluate_sample(self, agent: Any, sample: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个样本

        Args:
            agent: 要评估的智能体
            sample: 样本数据

        Returns:
            单个样本的评估结果
        """
        try:
            # 准备输入
            question = sample.get("question", "")
            expected_answer = sample.get("final_answer", "")
            level = sample.get("level", 1)
            task_id = sample.get("task_id", "")
            scratch_dir = self.output_root / task_id / "scratch"
            scratch_dir.mkdir(parents=True, exist_ok=True)

            # 构建提示
            prompt = self._build_prompt(question, sample)

            # 调用智能体
            if hasattr(agent, "begin_sample"):
                agent.begin_sample(sample, scratch_dir)
            start_time = time.time()
            response = agent.run(prompt)
            execution_time = time.time() - start_time
            agent_metadata = (
                agent.get_sample_metadata() if hasattr(agent, "get_sample_metadata") else {}
            )

            # 提取答案
            predicted_answer = self._extract_answer(response)
            strict_unresolved = (
                self.gaia_eval_mode == "strict"
                and int(agent_metadata.get("evidence_count", 0) or 0) == 0
            )
            if strict_unresolved:
                predicted_answer = "UNRESOLVED"

            # 评估答案
            exact_match = self._check_exact_match(predicted_answer, expected_answer)
            partial_match = self._check_partial_match(predicted_answer, expected_answer)

            # 计算分数
            if exact_match:
                score = 1.0
            elif partial_match:
                score = 0.5
            else:
                score = 0.0

            status = "success" if exact_match else "unresolved" if strict_unresolved else "failed"
            result = {
                "task_id": task_id,
                "level": level,
                "question": question,
                "exact_match": exact_match,
                "partial_match": partial_match,
                "score": score,
                "predicted": predicted_answer,
                "prediction": predicted_answer,
                "expected": expected_answer,
                "gold": expected_answer,
                "response": response,
                "execution_time": execution_time,
                "status": status,
                "failure_type": self._classify_failure(
                    predicted_answer,
                    expected_answer,
                    exact_match,
                    partial_match,
                    strict_unresolved,
                    agent_metadata.get("tool_errors", []),
                ),
                "tools_used": agent_metadata.get("tools_used", []),
                "tool_errors": agent_metadata.get("tool_errors", []),
                "evidence": agent_metadata.get("evidence", []),
                "evidence_count": agent_metadata.get("evidence_count", 0),
                "scratch_dir": str(scratch_dir),
            }
            self._save_sample_artifacts(task_id, result, agent_metadata.get("trace", []))
            return result

        except Exception as e:
            task_id = sample.get("task_id", "")
            scratch_dir = self.output_root / (task_id or "unknown") / "scratch"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            result = {
                "task_id": sample.get("task_id", ""),
                "level": sample.get("level", 1),
                "question": sample.get("question", ""),
                "exact_match": False,
                "partial_match": False,
                "score": 0.0,
                "predicted": None,
                "prediction": None,
                "expected": sample.get("final_answer", ""),
                "gold": sample.get("final_answer", ""),
                "error": str(e),
                "status": "failed",
                "failure_type": FailureType.UNKNOWN.value,
                "tools_used": [],
                "tool_errors": [],
                "evidence": [],
                "evidence_count": 0,
                "scratch_dir": str(scratch_dir),
            }
            self._save_sample_artifacts(task_id or "unknown", result, [])
            return result

    def _create_empty_results(self, agent: Any) -> Dict[str, Any]:
        """创建空的评估结果"""
        return {
            "benchmark": "GAIA",
            "agent_name": getattr(agent, "name", "Unknown"),
            "strict_mode": self.strict_mode,
            "level_filter": self.level,
            "total_samples": 0,
            "exact_matches": 0,
            "partial_matches": 0,
            "exact_match_rate": 0.0,
            "partial_match_rate": 0.0,
            "level_metrics": {},
            "failure_breakdown": {},
            "detailed_results": [],
        }

    def _build_prompt(self, question: str, sample: Dict[str, Any]) -> str:
        """构建评估提示"""
        # 构建问题提示
        prompt = f"{question}"

        # 如果有文件附件，添加提示
        if sample.get("file_name"):
            prompt += f"\n\nNote: This question may require reference to the file: {sample['file_name']}"

        return prompt

    def _extract_answer(self, response: str) -> str:
        """从响应中提取答案（GAIA格式）

        GAIA要求答案格式为：FINAL ANSWER: [答案]
        """
        # 首先尝试提取GAIA官方格式的答案
        final_answer_pattern = r"FINAL ANSWER:\s*(.+?)(?:\n|$)"
        match = re.search(final_answer_pattern, response, re.IGNORECASE | re.MULTILINE)
        if match:
            answer = match.group(1).strip()
            # 移除可能的方括号
            answer = answer.strip("[]")
            return answer

        # 备用方案：查找其他答案标记
        answer_patterns = [
            r"答案[：:]\s*(.+)",
            r"最终答案[：:]\s*(.+)",
            r"Final answer[：:]\s*(.+)",
            r"Answer[：:]\s*(.+)",
        ]

        for pattern in answer_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # 如果没有找到标记，返回最后一个非空行
        lines = response.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith("#"):
                return line

        return response.strip()

    def _check_exact_match(self, predicted: str, expected: str) -> bool:
        """检查精确匹配"""
        if not predicted or not expected:
            return False

        # 标准化字符串
        pred_normalized = self._normalize_answer(predicted)
        exp_normalized = self._normalize_answer(expected)

        return pred_normalized == exp_normalized

    def _check_partial_match(self, predicted: str, expected: str) -> bool:
        """检查部分匹配"""
        if not predicted or not expected:
            return False

        # 标准化字符串
        pred_normalized = self._normalize_answer(predicted)
        exp_normalized = self._normalize_answer(expected)

        if self._is_numeric_like(pred_normalized) or self._is_numeric_like(exp_normalized):
            return False

        # 检查包含关系
        if exp_normalized in pred_normalized or pred_normalized in exp_normalized:
            return True

        # 检查关键词匹配
        pred_words = set(pred_normalized.split())
        exp_words = set(exp_normalized.split())

        if not exp_words:
            return False

        # 如果超过70%的期望词汇出现在预测中，认为部分匹配
        overlap = len(pred_words & exp_words)
        return overlap / len(exp_words) >= 0.7

    @staticmethod
    def _is_numeric_like(answer: str) -> bool:
        return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", answer.strip()))

    def _normalize_answer(self, answer: str) -> str:
        """标准化答案字符串（GAIA官方标准化规则）

        根据GAIA论文的标准化规则：
        1. 数字：移除逗号分隔符和单位符号
        2. 字符串：移除冠词、转小写、移除多余空格
        3. 列表：按逗号分隔，每个元素独立标准化
        """
        if not answer:
            return ""

        answer = answer.strip()

        # 检查是否是逗号分隔的列表
        if "," in answer:
            # 分隔并标准化每个元素
            parts = [
                self._normalize_single_answer(p.strip()) for p in answer.split(",")
            ]
            # 按字母顺序排序（GAIA要求）
            parts.sort()
            return ",".join(parts)
        else:
            return self._normalize_single_answer(answer)

    def _normalize_single_answer(self, answer: str) -> str:
        """标准化单个答案（不包含逗号的答案）"""
        answer = answer.strip().lower()

        # 移除常见的冠词
        articles = ["the", "a", "an"]
        words = answer.split()
        if words and words[0] in articles:
            words = words[1:]
            answer = " ".join(words)

        # 移除货币符号和百分号
        answer = (
            answer.replace("$", "").replace("%", "").replace("€", "").replace("£", "")
        )

        # 移除数字中的逗号分隔符（如 1,000 -> 1000）
        # 但保留小数点
        answer = re.sub(r"(\d),(\d)", r"\1\2", answer)

        # 移除多余空格
        answer = " ".join(answer.split())

        # 移除末尾的标点符号
        answer = answer.rstrip(".,;:!?")

        return answer

    def _classify_failure(
        self,
        predicted: str | None,
        expected: str,
        exact_match: bool,
        partial_match: bool,
        strict_unresolved: bool,
        tool_errors: list[dict],
    ) -> str | None:
        if exact_match:
            return None
        if strict_unresolved:
            return FailureType.INSUFFICIENT_EVIDENCE.value

        error_types = [str(item.get("error_type", "")) for item in tool_errors]
        tools = [str(item.get("tool", "")) for item in tool_errors]
        if any(err in {"captcha_blocked", "http_403", "access_denied"} for err in error_types):
            return FailureType.WEB_SEARCH_BLOCKED.value
        if "empty_search_results" in error_types and any(tool == "web_search" for tool in tools):
            return FailureType.WEB_SEARCH_EMPTY.value
        if any(tool in {"fetch_url", "web_fetch"} for tool in tools):
            return FailureType.FETCH_FAILED.value
        file_tools = {
            "read_file",
            "file_read",
            "read_spreadsheet",
            "spreadsheet_read",
            "pdf_extract",
            "pdf_extract_text",
            "extract_pdf_text",
            "extract_pdf_tables",
            "pdf_extract_tables",
            "audio_transcribe",
            "image_ocr",
        }
        if any(
            err
            in {
                "file_parse_failed",
                "missing_pdf_dependency",
                "missing_pdf_table_dependency",
                "empty_pdf_text",
                "empty_pdf_tables",
                "tool_error",
            }
            for err in error_types
        ) and any(tool in file_tools for tool in tools):
            return FailureType.FILE_PARSE_FAILED.value
        if any(err in {"missing_audio_dependency", "audio_transcription_failed"} for err in error_types):
            return FailureType.AUDIO_TRANSCRIPTION_FAILED.value
        if any(err in {"missing_ocr_dependency", "ocr_failed"} for err in error_types):
            return FailureType.OCR_FAILED.value
        if "shell_command_failed" in error_types:
            return FailureType.SHELL_COMMAND_FAILED.value

        if self._looks_like_answer_format_error(predicted, expected):
            return FailureType.ANSWER_FORMAT_ERROR.value
        return FailureType.REASONING_ERROR.value if partial_match else FailureType.UNKNOWN.value

    def _looks_like_answer_format_error(self, predicted: str | None, expected: str) -> bool:
        if not predicted:
            return False
        pred = self._normalize_answer(predicted)
        exp = self._normalize_answer(expected)
        if self._is_numeric_like(pred) and self._is_numeric_like(exp):
            try:
                pred_num = float(pred)
                exp_num = float(exp)
            except ValueError:
                return False
            return exp_num != 0 and abs(pred_num / exp_num) in {1000, 1000.0}
        return exp in pred or pred in exp

    def _failure_breakdown(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = Counter(
            result.get("failure_type")
            for result in results
            if result.get("failure_type")
        )
        return dict(counter)

    def _print_failure_summary(self, results: List[Dict[str, Any]]) -> None:
        breakdown = self._failure_breakdown(results)
        if not breakdown:
            return
        print("\nGAIA Evaluation Summary")
        print("Failure breakdown:")
        for failure_type, count in sorted(breakdown.items()):
            print(f"- {failure_type}: {count}")

    def _save_sample_artifacts(self, task_id: str, result: Dict[str, Any], trace: list) -> None:
        sample_dir = self.output_root / task_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        (sample_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (sample_dir / "trace.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def export_to_gaia_format(
        self,
        results: Dict[str, Any],
        output_path: Union[str, Path],
        include_reasoning: bool = True,
    ) -> None:
        """导出为GAIA官方格式

        GAIA格式要求：
        - JSONL格式（每行一个JSON对象）
        - 每个对象包含：task_id, model_answer, reasoning_trace（可选）

        Args:
            results: 评估结果
            output_path: 输出文件路径
            include_reasoning: 是否包含推理轨迹
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        detailed_results = results.get("detailed_results", [])

        with open(output_path, "w", encoding="utf-8") as f:
            for result in detailed_results:
                gaia_result = {
                    "task_id": result.get("task_id", ""),
                    "model_answer": result.get("predicted", ""),
                }

                if include_reasoning:
                    gaia_result["reasoning_trace"] = result.get("response", "")

                f.write(json.dumps(gaia_result, ensure_ascii=False) + "\n")

        print(f"[OK] GAIA格式结果已导出")
        print(f"   输出文件: {output_path}")
        print(f"   样本数: {len(detailed_results)}")
        print(f"   包含推理轨迹: {include_reasoning}")
