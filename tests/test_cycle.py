import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cycle.py"


def run_cycle(tmp_path, *args):
    env = os.environ.copy()
    env["CYCLE_FAIRY_DB"] = str(tmp_path / "cycle.sqlite")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class CycleFairyTests(unittest.TestCase):
    def test_records_period_start_and_end_with_seven_day_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            start = run_cycle(tmp_path, "record", "今天来了，有点疼", "--date", "2026-07-01")
            self.assertEqual(start["action"], "period_start")
            self.assertEqual(start["record"]["date"], "2026-07-01")
            self.assertIsNotNone(start["record"]["pain_score"])
            self.assertIn("第 1 天", start["message"])

            end = run_cycle(tmp_path, "record", "结束了", "--date", "2026-07-07")
            self.assertEqual(end["action"], "period_end")
            self.assertEqual(end["cycle"]["period_length_days"], 7)
            self.assertIn("7 天", end["message"])

            summary = run_cycle(tmp_path, "summary", "--today", "2026-07-08")
            self.assertEqual(summary["cycles_count"], 1)
            self.assertEqual(summary["usual_period_length_days"], 7)

    def test_daily_check_proactively_reminds_when_period_is_expected_soon(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for start, end in [
                ("2026-04-01", "2026-04-07"),
                ("2026-05-01", "2026-05-07"),
                ("2026-05-31", "2026-06-06"),
            ]:
                run_cycle(tmp_path, "record", "今天来了", "--date", start)
                run_cycle(tmp_path, "record", "结束了", "--date", end)

            check = run_cycle(tmp_path, "daily-check", "--today", "2026-06-28")
            self.assertTrue(any(alert["type"] == "period_expected_soon" for alert in check["alerts"]))
            self.assertIn("不用你问", check["message"])

    def test_explain_dark_period_blood_uses_normal_mechanism_without_shame_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            answer = run_cycle(Path(tmp), "explain", "经期前后黑色是怎么回事")
            text = answer["message"]
            self.assertIn("氧化", text)
            self.assertTrue("刚开始" in text or "快结束" in text)
            self.assertNotIn("脏", text)
            self.assertNotIn("绝症", text)

    def test_records_discharge_as_body_literacy_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cycle(Path(tmp), "record", "今天白带像蛋清一样", "--date", "2026-07-13")
            self.assertEqual(result["action"], "discharge_note")
            self.assertEqual(result["record"]["kind"], "discharge")
            self.assertIn("排卵期", result["message"])

    def test_records_low_mood_as_pms_aware_note_even_without_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cycle(Path(tmp), "record", "今天心情很差", "--date", "2026-07-13")
            self.assertEqual(result["action"], "mood_note")
            self.assertEqual(result["record"]["kind"], "mood_note")
            self.assertEqual(result["record"]["mood"], "low")
            self.assertIn("经前", result["message"])

    def test_records_low_mood_near_forecast_period_as_pms_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for start, end in [
                ("2026-04-01", "2026-04-07"),
                ("2026-05-01", "2026-05-07"),
                ("2026-05-31", "2026-06-06"),
            ]:
                run_cycle(tmp_path, "record", "今天来了", "--date", start)
                run_cycle(tmp_path, "record", "结束了", "--date", end)

            result = run_cycle(tmp_path, "record", "今天心情很差", "--date", "2026-06-27")
            self.assertEqual(result["action"], "pms_note")
            self.assertEqual(result["record"]["kind"], "pms_note")
            self.assertEqual(result["record"]["mood"], "low")
            self.assertIn("PMS", result["message"])
            self.assertIn("3 天", result["message"])

    def test_daily_check_marks_pms_window_before_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for start, end in [
                ("2026-04-01", "2026-04-07"),
                ("2026-05-01", "2026-05-07"),
                ("2026-05-31", "2026-06-06"),
            ]:
                run_cycle(tmp_path, "record", "今天来了", "--date", start)
                run_cycle(tmp_path, "record", "结束了", "--date", end)

            check = run_cycle(tmp_path, "daily-check", "--today", "2026-06-25")
            self.assertTrue(any(alert["type"] == "pms_window" for alert in check["alerts"]))

    def test_records_pain_heavy_flow_and_abnormal_bleeding_as_specific_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pain = run_cycle(tmp_path, "record", "今天痛经8分，还有肛门坠胀", "--date", "2026-07-01")
            self.assertEqual(pain["action"], "pain_note")
            self.assertEqual(pain["record"]["kind"], "pain_note")
            self.assertEqual(pain["record"]["pain_score"], 8)
            self.assertIn("疼痛地图", pain["message"])

            heavy = run_cycle(tmp_path, "record", "今天量特别大，一小时换一次", "--date", "2026-07-02")
            self.assertEqual(heavy["action"], "heavy_flow_note")
            self.assertEqual(heavy["record"]["kind"], "heavy_flow_note")
            self.assertEqual(heavy["record"]["flow"], "heavy")
            self.assertIn("量大", heavy["message"])

            bleeding = run_cycle(tmp_path, "record", "今天非经期出血了", "--date", "2026-07-20")
            self.assertEqual(bleeding["action"], "abnormal_bleeding_note")
            self.assertEqual(bleeding["record"]["kind"], "abnormal_bleeding_note")
            self.assertIn("非经期", bleeding["message"])

    def test_records_discharge_alert_and_cycle_adjacent_life_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            discharge = run_cycle(tmp_path, "record", "今天白带黄绿色，还有点痒", "--date", "2026-07-10")
            self.assertEqual(discharge["action"], "discharge_alert")
            self.assertEqual(discharge["record"]["kind"], "discharge_alert")
            self.assertIn("白带", discharge["message"])

            ovulation = run_cycle(tmp_path, "record", "今天排卵期白带拉丝", "--date", "2026-07-13")
            self.assertEqual(ovulation["action"], "ovulation_note")
            self.assertIn("排卵", ovulation["message"])

            late = run_cycle(tmp_path, "record", "这个月还没来", "--date", "2026-07-30")
            self.assertEqual(late["action"], "late_period_note")
            self.assertIn("没来", late["message"])

            contraception = run_cycle(tmp_path, "record", "吃了紧急避孕药后点滴出血", "--date", "2026-08-02")
            self.assertEqual(contraception["action"], "contraception_note")
            self.assertIn("避孕", contraception["message"])

            supplies = run_cycle(tmp_path, "record", "卫生巾快没了", "--date", "2026-08-03")
            self.assertEqual(supplies["action"], "supplies_note")
            self.assertIn("补货", supplies["message"])

            perimenopause = run_cycle(tmp_path, "record", "最近潮热，月经也乱", "--date", "2026-08-04")
            self.assertEqual(perimenopause["action"], "perimenopause_note")
            self.assertIn("围绝经", perimenopause["message"])

    def test_explain_covers_gynecology_expert_topics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            topics = [
                ("痛经到影响上班会不会是内异症", ["内膜异位", "影响生活"]),
                ("PCOS 是什么，为什么月经不规律", ["PMOS", "不规律"]),
                ("紧急避孕药会不会影响月经", ["紧急避孕", "出血"]),
                ("围绝经会发生什么", ["围绝经", "45"]),
                ("月经杯和卫生棉条怎么选", ["经期用品", "月经杯"]),
            ]
            for question, expected_words in topics:
                answer = run_cycle(tmp_path, "explain", question)
                for word in expected_words:
                    self.assertIn(word, answer["message"])

    def test_doctor_summary_collects_cycle_and_concern_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_cycle(tmp_path, "record", "今天来了", "--date", "2026-07-01")
            run_cycle(tmp_path, "record", "今天痛经8分，还有肛门坠胀", "--date", "2026-07-01")
            run_cycle(tmp_path, "record", "今天量特别大，一小时换一次", "--date", "2026-07-02")
            run_cycle(tmp_path, "record", "结束了", "--date", "2026-07-07")

            summary = run_cycle(tmp_path, "doctor-summary", "--today", "2026-07-08")
            self.assertIn("给医生看的", summary["message"])
            self.assertEqual(summary["cycle_summary"]["usual_period_length_days"], 7)
            self.assertTrue(any(note["kind"] == "pain_note" for note in summary["concern_notes"]))
            self.assertTrue(any(note["kind"] == "heavy_flow_note" for note in summary["concern_notes"]))

    def test_records_english_cycle_and_gynecology_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            start = run_cycle(tmp_path, "record", "my period started today with mild cramps", "--date", "2026-07-01")
            self.assertEqual(start["action"], "period_start")
            self.assertEqual(start["record"]["pain_score"], 3)
            self.assertIn("Recorded", start["message"])

            mood = run_cycle(tmp_path, "record", "my mood is terrible today", "--date", "2026-07-13")
            self.assertEqual(mood["action"], "mood_note")
            self.assertEqual(mood["record"]["mood"], "low")
            self.assertIn("mood", mood["message"])

            heavy = run_cycle(tmp_path, "record", "heavy flow, changing my pad every hour", "--date", "2026-07-02")
            self.assertEqual(heavy["action"], "heavy_flow_note")
            self.assertEqual(heavy["record"]["flow"], "heavy")
            self.assertIn("heavy flow", heavy["message"])

            discharge = run_cycle(tmp_path, "record", "yellow discharge and itching", "--date", "2026-07-10")
            self.assertEqual(discharge["action"], "discharge_alert")
            self.assertIn("discharge", discharge["message"])

            late = run_cycle(tmp_path, "record", "my period is late", "--date", "2026-07-30")
            self.assertEqual(late["action"], "late_period_note")
            self.assertIn("late", late["message"])

    def test_explain_answers_english_questions_in_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            answer = run_cycle(Path(tmp), "explain", "Why is my period blood brown at the end?")
            self.assertIn("oxidation", answer["message"])
            self.assertIn("period", answer["message"])

            pms = run_cycle(Path(tmp), "explain", "What is PMS?")
            self.assertIn("PMS", pms["message"])
            self.assertIn("hormone", pms["message"])

    def test_locale_can_be_forced_independently_of_input_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            english = run_cycle(tmp_path, "record", "今天来了", "--date", "2026-07-01", "--locale", "en")
            self.assertEqual(english["action"], "period_start")
            self.assertEqual(english["locale"], "en")
            self.assertIn("Recorded", english["message"])

            chinese = run_cycle(tmp_path, "explain", "What is PMS?", "--locale", "zh")
            self.assertEqual(chinese["locale"], "zh")
            self.assertIn("身体后台", chinese["message"])


if __name__ == "__main__":
    unittest.main()
