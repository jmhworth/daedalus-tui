import unittest

from tui.prompts import (
    build_migration_repair_prompt,
    build_repair_prompt,
    build_resolver_prompt,
    build_task_prompt,
    build_topic_population_prompt,
)


class PromptTests(unittest.TestCase):
    def test_topic_population_prompt_includes_template_and_end_state(self):
        prompt = build_topic_population_prompt(
            "Kalman BTC Strategy",
            "kalman-btc-strategy",
            "Build an MVP that reaches a documented backtest result.",
            "# Kalman BTC Strategy\n\n## Topic Goal\nBuild an MVP.",
        )
        self.assertIn("topic_files/kalman-btc-strategy.md", prompt)
        self.assertIn("## Topic Goal", prompt)
        self.assertIn("documented backtest result", prompt)
        self.assertIn("Replace the initialization placeholder", prompt)

    def test_task_prompt_assigns_git_ownership_to_orchestrator(self):
        prompt = build_task_prompt("Build the feature")
        self.assertIn("leave them in the worktree", prompt)
        self.assertIn("orchestration layer owns all file staging, commits, merges, graph refreshes", prompt)
        self.assertIn("Do not run git add, git commit, git merge, git push, or switch branches", prompt)
        self.assertIn("Do not run graphify", prompt)
        self.assertIn("Do not run `supabase db push`", prompt)

    def test_migration_repair_prompt_forbids_agent_db_push(self):
        prompt = build_migration_repair_prompt("Original", "SQL error", 1, 3)
        self.assertIn("TASK_MODE: coding", prompt)
        self.assertIn("Migration push failure", prompt)
        self.assertIn("SQL error", prompt)
        self.assertIn("Do not run `supabase db push`", prompt)
        self.assertIn("Do not run git add", prompt)
        self.assertIn("Do not run graphify", prompt)

    def test_task_prompt_embeds_profile_after_user_prompt_and_before_constraints(self):
        profile = "CODING_PROFILE_SENTINEL\nUse the repository's feature files."

        prompt = build_task_prompt("Build the feature", profile_text=profile)

        self.assertIn(profile, prompt)
        self.assertIn("BEGIN_DAEDALUS_PROFILE", prompt)
        self.assertIn("Apply it directly; do not open the profile file merely to read it again", prompt)
        self.assertLess(prompt.index(profile), prompt.index("Make the requested file changes"))
        self.assertLess(prompt.index("Make the requested file changes"), prompt.index("Do not run graphify"))

    def test_plan_repair_and_resolver_prompts_embed_distinct_profiles(self):
        prompts = (
            build_task_prompt("Plan the feature", "plan", profile_text="PLANNING_PROFILE_SENTINEL"),
            build_repair_prompt("Original", "Failure", 1, 3, profile_text="REPAIR_PROFILE_SENTINEL"),
            build_resolver_prompt("Original", "Failure", 1, 3, profile_text="RESOLVER_PROFILE_SENTINEL"),
        )

        for prompt, profile in zip(
            prompts,
            ("PLANNING_PROFILE_SENTINEL", "REPAIR_PROFILE_SENTINEL", "RESOLVER_PROFILE_SENTINEL"),
        ):
            self.assertIn(profile, prompt)
            self.assertLess(prompt.index(profile), prompt.index("Do not run git add"))

    def test_missing_profile_preserves_prompt_without_a_file_pointer(self):
        prompt = build_task_prompt("Build the feature", profile_text=None)

        self.assertNotIn("BEGIN_DAEDALUS_PROFILE", prompt)
        self.assertNotIn(".agents/profiles", prompt)

    def test_repair_and_resolver_prompts_forbid_agent_git_operations(self):
        for prompt in (
            build_repair_prompt("Original", "Failure", 1, 3),
            build_resolver_prompt("Original", "Failure", 1, 3),
            build_migration_repair_prompt("Original", "Failure", 1, 3),
        ):
            self.assertIn("Do not run git add, git commit, git merge, git push, or switch branches", prompt)
            self.assertIn("orchestration layer", prompt)
            self.assertIn("Do not run graphify", prompt)
            self.assertIn("Do not run `supabase db push`", prompt)

    def test_ask_and_plan_modes_are_read_only(self):
        ask = build_task_prompt("Explain this", "ask")
        plan = build_task_prompt("Design this", "plan")
        self.assertIn("TASK_MODE: ask", ask)
        self.assertIn("read-only context", ask)
        self.assertIn("TASK_MODE: plan", plan)
        self.assertIn("implementation plan", plan)
        self.assertIn("BEGIN_DAEDALUS_PLAN", plan)
        self.assertIn("no_more_questions", plan)
        self.assertIn('(Recommended)', plan)
        self.assertIn("exactly one option as the recommended default", plan)
        self.assertIn("Do not modify files", ask)
        self.assertIn("Do not modify files", plan)

    def test_resumed_prompt_explains_existing_work_and_omits_empty_notes_section(self):
        without_notes = build_task_prompt("Continue", resumed=True)
        with_notes = build_task_prompt(
            "Continue",
            resume_notes=("The API already exists in app/api/client.py.",),
            resumed=True,
        )

        self.assertIn("resumption of work already started", without_notes)
        self.assertIn("git status and git diff", without_notes)
        self.assertNotIn("Additional notes from the user", without_notes)
        self.assertIn("Additional notes from the user", with_notes)
        self.assertIn("The API already exists in app/api/client.py.", with_notes)

    def test_topic_embeds_for_coding_plan_ask_repair_and_resolver(self):
        topic = (
            "# Sample Topic\n\n## Topic Goal\nWhy\n\n## Topic Status\nopen\n\n"
            "## State Log\n- 2026-08-24: Started.\n"
        )
        coding = build_task_prompt("Build", "coding", topic_text=topic)
        plan = build_task_prompt("Design", "plan", topic_text=topic)
        ask = build_task_prompt("Explain", "ask", topic_text=topic)
        repair = build_repair_prompt("Original", "Failure", 1, 3, topic_text=topic)
        resolver = build_resolver_prompt("Original", "Failure", 1, 3, topic_text=topic)

        for prompt in (coding, plan, ask, repair, resolver):
            self.assertIn("BEGIN_DAEDALUS_TOPIC", prompt)
            self.assertIn("Sample Topic", prompt)
            self.assertIn("TOPIC INSTRUCTIONS", prompt)

        self.assertIn("append one State Log entry", coding)
        self.assertIn("read-only for topic files", plan)
        self.assertIn("read-only for topic files", ask)
        self.assertIn("repair or resolution materially changes", repair)
        self.assertIn("repair or resolution materially changes", resolver)

    def test_untagged_prompts_omit_topic_blocks(self):
        for prompt in (
            build_task_prompt("Build"),
            build_task_prompt("Design", "plan"),
            build_task_prompt("Explain", "ask"),
            build_repair_prompt("Original", "Failure", 1, 3),
            build_resolver_prompt("Original", "Failure", 1, 3),
        ):
            self.assertNotIn("BEGIN_DAEDALUS_TOPIC", prompt)
            self.assertNotIn("topic_files", prompt)


if __name__ == "__main__":
    unittest.main()


class ConversationPromptTests(unittest.TestCase):
    def test_orders_history_and_marks_the_latest_instruction(self):
        from tui.prompts import ConversationEntry, build_conversation_prompt

        prompt = build_conversation_prompt(
            [
                ConversationEntry("user", "Build the login page"),
                ConversationEntry("assistant", "Built it."),
                ConversationEntry("context", "Re-evaluate the plan using the user's answers below."),
                ConversationEntry("assistant", "Plan revised."),
            ],
            "Now add validation",
        )
        self.assertTrue(prompt.startswith("Original request for this task:\nBuild the login page"))
        self.assertLess(prompt.index("Built it."), prompt.index("Plan revised."))
        self.assertIn("not typed by the user", prompt)
        self.assertTrue(prompt.endswith("Latest instruction (respond to this one):\nNow add validation"))

    def test_bounded_history_identifies_omitted_turns_and_keeps_the_original_goal(self):
        from tui.prompts import ConversationEntry, build_conversation_prompt

        entries = [ConversationEntry("user", "Goal text")]
        for index in range(30):
            entries.append(ConversationEntry("user", f"user turn {index} " + "x" * 400))
            entries.append(ConversationEntry("assistant", f"assistant reply {index} " + "y" * 400))
        prompt = build_conversation_prompt(entries, "final instruction", budget_chars=3000)
        self.assertLessEqual(len(prompt), 3400)
        self.assertIn("Goal text", prompt)
        self.assertIn("earlier turns omitted to fit the context budget", prompt)
        self.assertIn("assistant reply 29", prompt)
        self.assertNotIn("assistant reply 0 ", prompt)
        self.assertTrue(prompt.endswith("final instruction"))

    def test_single_turn_has_no_history_section(self):
        from tui.prompts import ConversationEntry, build_conversation_prompt

        prompt = build_conversation_prompt([ConversationEntry("user", "only goal")], "only goal")
        self.assertNotIn("Conversation so far", prompt)
        self.assertIn("only goal", prompt)


OPERATOR_PROMPT = "OPERATOR_PROMPT_SENTINEL: rewrite the whole settings bar."


class OrchestratePromptTests(unittest.TestCase):
    """Orchestrate Mode prompts: one role block each, and one card per worker."""

    def card(self) -> str:
        from tui.orchestrate_protocol import PlannerTask, load_card_template, render_task_card

        task = PlannerTask(
            "t2",
            "Add bar parsing",
            "Parse the bar payload and return a typed record.",
            ("parse_bar returns a BarRecord", "tests cover a malformed payload"),
            ("tui/bar.py", "tests/test_bar.py"),
            ("tui/foo.py:120-180",),
            "def parse_bar(text: str) -> BarRecord",
            "pytest tests/test_bar.py",
        )
        return render_task_card(task, load_card_template())

    def test_planner_prompt_carries_the_payload_contract_and_worker_count(self):
        from tui.orchestrate_protocol import load_role_rules
        from tui.prompts import build_planner_prompt

        prompt = build_planner_prompt(
            OPERATOR_PROMPT,
            role_rules=load_role_rules(),
            profile_text="PLANNING_PROFILE_SENTINEL",
            max_workers=4,
            verification_hint="pytest",
        )

        self.assertTrue(prompt.startswith("TASK_MODE: orchestrate-plan"))
        self.assertIn(OPERATOR_PROMPT, prompt)
        self.assertIn("PLANNING_PROFILE_SENTINEL", prompt)
        self.assertIn("BEGIN_DAEDALUS_ORCHESTRATION", prompt)
        self.assertIn("END_DAEDALUS_ORCHESTRATION", prompt)
        self.assertIn("At most 4 workers run at a time", prompt)
        self.assertIn("pytest", prompt)
        self.assertIn("Do not modify files", prompt)
        # The planner, not a cap, decides how many rounds the session takes.
        self.assertIn("You decide how many planning rounds", prompt)
        self.assertNotIn("BEGIN_DAEDALUS_REPOSITORY_MAP", prompt)
        # The planner gets its own block plus the shared rules, never the worker's.
        self.assertIn("You own decomposition, ordering, and conflict resolution", prompt)
        self.assertIn("Edit only inside your own Git worktree", prompt)
        self.assertNotIn("Do exactly what the card says", prompt)

    def test_planner_prompt_embeds_the_repository_map(self):
        from tui.prompts import build_planner_prompt

        prompt = build_planner_prompt(OPERATOR_PROMPT, repository_map="tui/app.py\ntui/config.py")

        self.assertIn("BEGIN_DAEDALUS_REPOSITORY_MAP", prompt)
        self.assertIn("tui/app.py\ntui/config.py", prompt)
        self.assertIn("END_DAEDALUS_REPOSITORY_MAP", prompt)

    def test_planner_prompt_embeds_the_project_context_and_names_its_file(self):
        from tui.prompts import build_planner_prompt

        prompt = build_planner_prompt(
            OPERATOR_PROMPT,
            project_context="## Session orc-001-abcdef12\n\n| t1 | Add parser | promoted |",
            context_filename="DAEDALUS_CONTEXT.md",
        )

        self.assertIn("BEGIN_DAEDALUS_PROJECT_CONTEXT", prompt)
        self.assertIn("## Session orc-001-abcdef12", prompt)
        self.assertIn("| t1 | Add parser | promoted |", prompt)
        self.assertIn("`DAEDALUS_CONTEXT.md`", prompt)
        self.assertIn("Cards marked promoted are already merged", prompt)
        self.assertIn("END_DAEDALUS_PROJECT_CONTEXT", prompt)
        self.assertLess(prompt.index("END_DAEDALUS_PROJECT_CONTEXT"), prompt.index("Decompose the request above"))
        self.assertNotIn("BEGIN_DAEDALUS_PROJECT_CONTEXT", build_planner_prompt(OPERATOR_PROMPT))

    def test_planner_prompts_describe_the_worker_environment(self):
        from tui.prompts import build_planner_prompt, build_planner_round_prompt, describe_worker_environment

        environment = describe_worker_environment(("claude", "claude-opus-5", "high"))
        self.assertTrue(environment.startswith("Workers run on Claude Code CLI (claude-opus-5)"))
        self.assertIn("none of your skills, plugins, MCP servers", environment)
        first = build_planner_prompt(OPERATOR_PROMPT, worker_environment=environment)
        later = build_planner_round_prompt(OPERATOR_PROMPT, "summary", "digest", worker_environment=environment)
        self.assertIn(environment, first)
        self.assertIn(environment, later)
        self.assertNotIn("Workers run on", build_planner_prompt(OPERATOR_PROMPT))
        self.assertEqual(describe_worker_environment(None), "")
        self.assertIn("Codex CLI (gpt-6-astra)", describe_worker_environment(("codex", "gpt-6-astra", "medium")))

    def test_planner_round_prompt_carries_the_digest_and_its_options(self):
        from tui.orchestrate_protocol import load_role_rules
        from tui.prompts import build_planner_round_prompt

        digest = "t1  promoted   4/4 checklist\nt2  failed     1/3 checklist"
        prompt = build_planner_round_prompt(
            OPERATOR_PROMPT,
            "Split the work in three.",
            digest,
            role_rules=load_role_rules(),
            round_number=2,
        )

        self.assertIn("Planner round 2.", prompt)
        self.assertNotIn("of 6", prompt)
        self.assertNotIn("capped", prompt)
        self.assertIn("You decide how many more rounds", prompt)
        self.assertIn(digest, prompt)
        self.assertIn("Split the work in three.", prompt)
        self.assertIn("reissues", prompt)
        self.assertIn("done=true", prompt)

    def test_planner_round_prompt_names_an_optional_round_cap(self):
        from tui.prompts import build_planner_round_prompt, planner_round_label

        prompt = build_planner_round_prompt(OPERATOR_PROMPT, "", "t1  promoted", round_number=2, round_limit=6)

        self.assertIn("Planner round 2 of 6.", prompt)
        self.assertIn("capped at 6 rounds", prompt)
        self.assertEqual(planner_round_label(3), "Planner round 3")
        self.assertEqual(planner_round_label(3, 5), "Planner round 3 of 5")

    def test_worker_prompt_contains_only_the_card(self):
        from tui.orchestrate_protocol import load_role_rules
        from tui.prompts import build_worker_prompt

        prompt = build_worker_prompt(
            self.card(),
            role_rules=load_role_rules(),
            profile_text="CODING_PROFILE_SENTINEL",
            verify_command="pytest tests/test_bar.py",
        )

        self.assertTrue(prompt.startswith("TASK_MODE: coding"))
        self.assertIn("Add bar parsing", prompt)
        self.assertIn("- [ ] parse_bar returns a BarRecord", prompt)
        self.assertIn("CODING_PROFILE_SENTINEL", prompt)
        self.assertIn("BEGIN_DAEDALUS_WORKER_REPORT", prompt)
        self.assertIn(".daedalus-orchestration/task.md", prompt)
        self.assertIn("Do not run git add", prompt)
        # The worker sees its own role rules, not the planner's.
        self.assertIn("Do exactly what the card says", prompt)
        self.assertNotIn("You own decomposition", prompt)
        # Context minimization: the operator's prompt never reaches a worker.
        self.assertNotIn(OPERATOR_PROMPT, prompt)

    def test_worker_prompt_cannot_be_given_the_operator_prompt(self):
        """Minimization is structural: there is no parameter to pass it through."""
        import inspect

        from tui.prompts import build_worker_prompt

        parameters = set(inspect.signature(build_worker_prompt).parameters)
        self.assertEqual(parameters, {"card_markdown", "role_rules", "profile_text", "verify_command"})

    def test_worker_prompt_fits_the_card_budget(self):
        from tui.config import load_orchestrate_settings
        from tui.orchestrate_protocol import load_role_rules
        from tui.prompts import build_worker_prompt

        settings = load_orchestrate_settings()
        prompt = build_worker_prompt(self.card(), role_rules=load_role_rules())

        self.assertLessEqual(len(prompt), settings.worker_card_budget_chars)

    def test_role_block_extracts_exactly_one_section(self):
        from tui.prompts import role_block

        rules = "# Title\n\n## Shared\nshared line\n\n## Planner\nplanner line\n\n## Worker\nworker line\n"

        self.assertEqual(role_block(rules, "Shared"), "## Shared\nshared line")
        self.assertEqual(role_block(rules, "Worker"), "## Worker\nworker line")
        self.assertEqual(role_block(rules, "Missing"), "")
        self.assertEqual(role_block(None, "Shared"), "")

    def test_bounded_digest_marks_the_omission(self):
        from tui.prompts import bounded_digest

        digest = bounded_digest("x" * 5000, 500)

        self.assertLessEqual(len(digest), 500)
        self.assertIn("truncated to fit the context budget", digest)


class WorkerTaskPromptTests(unittest.TestCase):
    """``build_task_prompt`` with a card delegates to the worker builder."""

    def card(self) -> str:
        from tui.orchestrate_protocol import PlannerTask, load_card_template, render_task_card

        task = PlannerTask(
            "t3",
            "Add baz",
            "Add the baz helper.",
            ("baz exists",),
            ("tui/baz.py",),
            verify="pytest tests/test_baz.py",
        )
        return render_task_card(task, load_card_template())

    def test_card_replaces_the_operator_prompt_and_history(self):
        from tui.prompts import RESUMPTION_TEXT, build_task_prompt

        prompt = build_task_prompt(
            OPERATOR_PROMPT,
            "coding",
            resume_notes=("HISTORY_SENTINEL",),
            resumed=True,
            profile_text="CODING_PROFILE_SENTINEL",
            topic_text="TOPIC_SENTINEL",
            orchestrate_card=self.card(),
        )

        self.assertTrue(prompt.startswith("TASK_MODE: coding"))
        self.assertIn("# t3 — Add baz", prompt)
        self.assertIn("CODING_PROFILE_SENTINEL", prompt)
        self.assertIn("Run this verification before reporting: pytest tests/test_baz.py", prompt)
        self.assertIn("BEGIN_DAEDALUS_WORKER_REPORT", prompt)
        self.assertIn(RESUMPTION_TEXT, prompt)
        self.assertNotIn(OPERATOR_PROMPT, prompt)
        self.assertNotIn("HISTORY_SENTINEL", prompt)
        self.assertNotIn("TOPIC_SENTINEL", prompt)

    def test_card_verify_command_reads_the_verify_section(self):
        from tui.orchestrate_protocol import card_verify_command

        self.assertEqual(card_verify_command(self.card()), "pytest tests/test_baz.py")
        self.assertEqual(card_verify_command("# t\n\n## Verify\n(no verification command was given)\n"), "")
        self.assertEqual(card_verify_command("# t\n\n## Goal\npytest\n"), "")
