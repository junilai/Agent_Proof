from fractions import Fraction

from experiments.analysis.detection import Detection
from experiments.figures.metrics import Classification, classification


def detection(vp=0, fn=0, fp=0, vn=0, fp_exposed=0):
    d = Detection("d4", Fraction(2, 5))
    d.true_positives = [f"vp{i}" for i in range(vp)]
    d.false_negatives = [f"fn{i}" for i in range(fn)]
    d.false_positives = [f"fp{i}" for i in range(fp)]
    d.true_negatives = [f"vn{i}" for i in range(vn)]
    d.exposed = d.true_positives + d.false_negatives + d.false_positives[:fp_exposed]
    return d


def test_the_metrics_come_from_the_confusion_matrix():
    c = classification(detection(vp=6, fp=1, vn=13, fp_exposed=1), "SDK")
    assert (c.vp, c.fn, c.fp, c.vn) == (6, 0, 1, 13)
    assert c.precision == Fraction(6, 7)
    assert c.recall == 1
    assert c.f1 == Fraction(12, 13)
    assert c.fpr == Fraction(1, 14)
    assert (c.fp_unexposed, c.fp_exposed) == (0, 1)


def test_without_flags_precision_is_undefined_and_f1_is_zero():
    c = classification(detection(fn=11, vn=9), "SDK")
    assert c.precision is None
    assert c.recall == 0
    assert c.f1 == 0


def test_without_positives_recall_and_f1_are_undefined():
    c = classification(detection(fp=5, vn=15, fp_exposed=5), "LangGraph")
    assert c.recall is None and c.f1 is None
    assert c.precision == 0
    assert c.fpr == Fraction(1, 4)
    assert (c.fp_unexposed, c.fp_exposed) == (0, 5)


def test_a_classification_keeps_its_labels():
    c = classification(detection(vp=1, vn=1), "SDK")
    assert isinstance(c, Classification)
    assert (c.operator, c.framework) == ("d4", "SDK")
