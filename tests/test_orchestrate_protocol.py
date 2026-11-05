import json
import unittest

from tui.orchestrate_protocol import (
    ORCHESTRATION_END,
    ORCHESTRATION_START,
    WORKER_REPORT_END,
    WORKER_REPORT_START,
    PlannerTask,
    load_card_template,
    load_role_rules,
    parse_card_ticks,
    parse_planner_payload,
    parse_worker_report,
    ready_tasks,
    render_task_card,
)


def planner_response(tasks, done=False, summary="Split the work.") -> str:
    payload = {"summary": summary, "tasks": tasks, "done": done}
    return (
        "Here is the plan.\n"
        f"{ORCHESTRATION_START}\n{json.dumps(payload)}\n{ORCHESTRATION_END}\n"
    )


def task(task_id, **overrides) -> dict:
    values = {
        "id": task_id,
        "title": f"Task {task_id}",
        "goal": "Make the thing work.",
        "checklist": ["item one"],
        "file_scope": [f"tui/{task_id}.py"],
        "read_first": ["tui/app.py:1-40"],
        "interfaces": "def go() -> None",
        "verify": f"pytest tests/test_{task_id}.py",
        "depends_on": [],
    }
    values.update(overrides)
    return values


class PlannerPayloadTests(unittest.TestCase):
    def test_valid_payload_parses_every_card_field(self):
        payload = parse_planner_payload(planner_response([task("t1"), task("t2", depends_on=["t1"])]))

        self.assertTrue(payload.valid)
        self.assertIsNone(payload.error)
        self.assertEqual(payload.summary, "Split the work.")
        self.assertFalse(payload.done)
        self.assertEqual([item.task_id for item in payload.tasks], ["t1", "t2"])
        first = payload.tasks[0]
        self.assertEqual(first.title, "Task t1")
        self.assertEqual(first.checklist, ("item one",))
        self.assertEqual(first.file_scope, ("tui/t1.py",))
        self.assertEqual(first.read_first, ("tui/app.py:1-40",))
        self.assertEqual(first.verify, "pytest tests/test_t1.py")
        self.assertEqual(payload.tasks[1].depends_on, ("t1",))

    def test_reissue_id_is_preserved(self):
        payload = parse_planner_payload(planner_response([task("t4", reissues="t2")]))

        self.assertTrue(payload.valid)
        self.assertEqual(payload.tasks[0].reissues, "t2")

    def test_response_without_markers_is_rejected(self):
        payload = parse_planner_payload("I could not produce a plan.")

        self.assertFalse(payload.valid)
        self.assertIn("required format", payload.error)

    def test_task_without_checklist_is_rejected(self):
        payload = parse_planner_payload(planner_response([task("t1", checklist=[])]))

        self.assertFalse(payload.valid)
        self.assertIn("checklist", payload.error)

    def test_task_without_file_scope_is_rejected(self):
        payload = parse_planner_payload(planner_response([task("t1", file_scope=[])]))

        self.assertFalse(payload.valid)
        self.assertIn("file_scope", payload.error)

    def test_duplicate_ids_are_rejected(self):
        payload = parse_planner_payload(planner_response([task("t1"), task("t1", file_scope=["tui/b.py"])]))

        self.assertFalse(payload.valid)
        self.assertIn("unique ids", payload.error)

    def test_unknown_dependency_is_rejected(self):
        payload = parse_planner_payload(planner_response([task("t1", depends_on=["t9"])]))

        self.assertFalse(payload.valid)
        self.assertIn("unknown task", payload.error)

    def test_dependency_cycle_is_rejected(self):
        payload = parse_planner_payload(
            planner_response([task("t1", depends_on=["t2"]), task("t2", depends_on=["t1"])])
        )

        self.assertFalse(payload.valid)
        self.assertIn("cycle", payload.error)

    def test_independent_tasks_may_not_share_file_scope(self):
        payload = parse_planner_payload(
            planner_response([task("t1", file_scope=["tui/app.py"]), task("t2", file_scope=["tui/app.py"])])
        )

        self.assertFalse(payload.valid)
        self.assertIn("share file scope", payload.error)

    def test_dependent_tasks_may_share_file_scope(self):
        """A dependent task runs after its parent is promoted, so it cannot race it."""
        payload = parse_planner_payload(
            planner_response(
                [
                    task("t1", file_scope=["tui/app.py"]),
                    task("t2", depends_on=["t1"], file_scope=["tui/app.py"]),
                    task("t3", depends_on=["t2"], file_scope=["tui/app.py"]),
                ]
            )
        )

        self.assertTrue(payload.valid, payload.error)

    def test_done_with_tasks_is_rejected(self):
        payload = parse_planner_payload(planner_response([task("t1")], done=True))

        self.assertFalse(payload.valid)
        self.assertIn("finished plan", payload.error)

    def test_done_with_no_tasks_finishes_the_session(self):
        payload = parse_planner_payload(planner_response([], done=True, summary="All promoted."))

        self.assertTrue(payload.valid)
        self.assertTrue(payload.done)
        self.assertEqual(payload.tasks, ())
        self.assertEqual(payload.summary, "All promoted.")


class WorkerReportTests(unittest.TestCase):
    def report(self, **overrides) -> str:
        payload = {
            "task": "t2",
            "status": "done",
            "checklist": [True, True],
            "files_changed": ["tui/bar.py"],
            "errors": "",
            "notes": "Added parse_bar().",
        }
        payload.update(overrides)
        return f"Work finished.\n{WORKER_REPORT_START}\n{json.dumps(payload)}\n{WORKER_REPORT_END}"

    def test_valid_report_parses(self):
        report = parse_worker_report(self.report())

        self.assertTrue(report.valid)
        self.assertEqual(report.task_id, "t2")
        self.assertEqual(report.status, "done")
        self.assertEqual(report.checklist, (True, True))
        self.assertEqual(report.files_changed, ("tui/bar.py",))
        self.assertEqual(report.notes, "Added parse_bar().")

    def test_blocked_status_is_accepted(self):
        report = parse_worker_report(self.report(status="blocked", checklist=[False], errors="No API."))

        self.assertTrue(report.valid)
        self.assertEqual(report.status, "blocked")
        self.assertEqual(report.errors, "No API.")

    def test_missing_report_defaults_to_partial(self):
        report = parse_worker_report("I finished the work, trust me.")

        self.assertFalse(report.valid)
        self.assertEqual(report.status, "partial")
        self.assertIn("required format", report.error)
        self.assertEqual(report.errors, report.error)

    def test_unknown_status_defaults_to_partial(self):
        report = parse_worker_report(self.report(status="finished-ish"))

        self.assertFalse(report.valid)
        self.assertEqual(report.status, "partial")
        self.assertEqual(report.task_id, "t2")
        self.assertIn("status must be one of", report.error)

    def test_malformed_json_defaults_to_partial(self):
        response = f"{WORKER_REPORT_START}\n{{\"task\": \"t2\",\n{WORKER_REPORT_END}"

        report = parse_worker_report(response)

        self.assertFalse(report.valid)
        self.assertEqual(report.status, "partial")
        self.assertIn("not valid JSON", report.error)


class ReadyTaskTests(unittest.TestCase):
    def tasks(self) -> tuple[PlannerTask, ...]:
        payload = parse_planner_payload(
            planner_response([task("t1"), task("t2"), task("t3", depends_on=["t2"])])
        )
        self.assertTrue(payload.valid, payload.error)
        return payload.tasks

    def test_only_independent_tasks_start_first(self):
        ready = ready_tasks(self.tasks(), promoted_ids=(), active_ids=(), failed_ids=())

        self.assertEqual([item.task_id for item in ready], ["t1", "t2"])

    def test_dependent_task_waits_for_promotion(self):
        ready = ready_tasks(self.tasks(), promoted_ids=("t1",), active_ids=("t2",), failed_ids=())

        self.assertEqual([item.task_id for item in ready], [])

    def test_dependent_task_starts_after_its_parent_is_promoted(self):
        ready = ready_tasks(self.tasks(), promoted_ids=("t1", "t2"), active_ids=(), failed_ids=())

        self.assertEqual([item.task_id for item in ready], ["t3"])

    def test_failed_tasks_are_not_redispatched(self):
        ready = ready_tasks(self.tasks(), promoted_ids=(), active_ids=(), failed_ids=("t1", "t2"))

        self.assertEqual([item.task_id for item in ready], [])


class CardTests(unittest.TestCase):
    def card(self) -> str:
        payload = parse_planner_payload(
            planner_response([task("t2", checklist=["item one", "item two"])])
        )
        return render_task_card(payload.tasks[0], load_card_template())

    def test_rendered_card_carries_every_section(self):
        card = self.card()

        self.assertIn("# t2 — Task t2", card)
        self.assertIn("## Checklist\n- [ ] item one\n- [ ] item two", card)
        self.assertIn("- tui/t2.py", card)
        self.assertIn("- tui/app.py:1-40", card)
        self.assertIn("pytest tests/test_t2.py", card)
        self.assertNotIn("{{", card)

    def test_ticks_round_trip_through_the_card_file(self):
        card = self.card().replace("- [ ] item one", "- [x] item one")

        self.assertEqual(parse_card_ticks(card), (True, False))

    def test_empty_optional_sections_render_placeholders(self):
        payload = parse_planner_payload(
            planner_response([task("t1", read_first=[], interfaces="", verify="")])
        )

        card = render_task_card(payload.tasks[0], load_card_template())

        self.assertIn("- (nothing beyond your file scope)", card)
        self.assertIn("(none declared)", card)
        self.assertNotIn("{{", card)

    def test_ticks_outside_the_checklist_section_are_ignored(self):
        card = self.card() + "\n## Notes\n- [x] something I did on my own\n"

        self.assertEqual(parse_card_ticks(card), (False, False))

    def test_role_rules_expose_the_three_blocks(self):
        rules = load_role_rules()

        self.assertIn("## Shared", rules)
        self.assertIn("## Planner", rules)
        self.assertIn("## Worker", rules)


if __name__ == "__main__":
    unittest.main()
