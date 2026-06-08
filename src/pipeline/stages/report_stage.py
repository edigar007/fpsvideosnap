from typing import Type

from src.pipeline.context import PipelineContext
from src.pipeline.results import CLIPS, REPORT_PATH, VIDEO_INFO
from src.pipeline.stages.base import StageResult
from src.report.report_generator import ReportGenerator


def run_report_stage(
    context: PipelineContext,
    report_generator_cls: Type[ReportGenerator] = ReportGenerator,
) -> StageResult:
    output_dir = context.config.get("global", {}).get("output_dir", "output")
    report_gen = report_generator_cls(output_dir)
    report_path = report_gen.generate(
        context.results.get(VIDEO_INFO, {}),
        context.results.get(CLIPS, []),
        context.config,
    )
    return StageResult({REPORT_PATH: report_path})
