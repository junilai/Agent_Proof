"""Classification metrics of a detection, all read from its confusion matrix (§5.4).

Precision and F1 add no choice to the analysis: they are fixed functions of the
same four cells that give the pre-registered TPR and FPR. A metric whose
denominator is zero is undefined (None), as the TPR of an operator that
manifested nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from experiments.analysis.detection import Detection


def _rate(part: int, whole: int) -> Fraction | None:
    return Fraction(part, whole) if whole else None


@dataclass(frozen=True)
class Classification:
    operator: str
    framework: str
    vp: int
    fn: int
    fp: int
    vn: int
    fp_unexposed: int
    fp_exposed: int

    @property
    def precision(self) -> Fraction | None:
        return _rate(self.vp, self.vp + self.fp)

    @property
    def recall(self) -> Fraction | None:
        """The TPR."""
        return _rate(self.vp, self.vp + self.fn)

    @property
    def fpr(self) -> Fraction | None:
        return _rate(self.fp, self.fp + self.vn)

    @property
    def f1(self) -> Fraction | None:
        """2·VP / (2·VP + FP + FN); undefined, like the recall, without positives."""
        if self.vp + self.fn == 0:
            return None
        return Fraction(2 * self.vp, 2 * self.vp + self.fp + self.fn)


def classification(detection: Detection, framework: str) -> Classification:
    return Classification(
        operator=detection.operator,
        framework=framework,
        vp=len(detection.true_positives),
        fn=len(detection.false_negatives),
        fp=len(detection.false_positives),
        vn=len(detection.true_negatives),
        fp_unexposed=len(detection.false_positives_unexposed),
        fp_exposed=len(detection.false_positives_exposed),
    )
