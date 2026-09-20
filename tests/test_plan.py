import unittest

from tui.plan import (
    CUSTOM_ANSWER_OPTION_ID,
    PLAN_END,
    PLAN_START,
    PlanOption,
    PlanQuestion,
    build_implementation_prompt,
    build_plan_clarification_prompt,
    build_plan_followup_prompt,
    custom_answer_text,
    encode_custom_answer,
    parse_plan_response,
    plan_answer_options,
)


class PlanTests(unittest.TestCase):
    def test_parser_extracts_only_plan_and_multiple_choice_questions(self):
        response = (
            "BEGIN_DAEDALUS_PLAN\n"
            '{"plan":"1. Add the API.\\n2. Test it.","questions":[{"id":"q1",'
            '"question":"Which store?","required":true,"options":['
            '{"id":"a","label":"SQLite"},{"id":"b","label":"JSON"}]}],'
            '"no_more_questions":false}\n'
            "END_DAEDALUS_PLAN"
        )

        result = parse_plan_response(response)

        self.assertTrue(result.valid)
        self.assertEqual(result.plan, "1. Add the API.\n2. Test it.")
        self.assertEqual(result.questions[0].text, "Which store?")
        self.assertEqual(result.questions[0].options[1], PlanOption("b", "JSON"))
        self.assertNotIn(CUSTOM_ANSWER_OPTION_ID, {option.option_id for option in result.questions[0].options})
        self.assertFalse(result.no_more_questions)

    def test_parser_requires_explicit_confirmation(self):
        result = parse_plan_response('{"plan":"Do it.","questions":[],"no_more_questions":false}')
        self.assertFalse(result.no_more_questions)
        self.assertFalse(parse_plan_response("plain markdown plan").valid)

    def test_parser_prefers_latest_valid_plan_block(self):
        first = (
            '{"plan":"Draft one.","questions":[{"id":"q1","question":"Which store?",'
            '"options":[{"id":"a","label":"SQLite"},{"id":"b","label":"JSON"}]}],'
            '"no_more_questions":false}'
        )
        second = (
            '{"plan":"Draft two.","questions":[{"id":"q1","question":"Which host?",'
            '"options":[{"id":"cloud","label":"Cloud (Recommended)"},'
            '{"id":"local","label":"Local"}]}],"no_more_questions":false}'
        )
        response = (
            "I'll inspect the repo.\n"
            f"{PLAN_START}\n{first}\n{PLAN_END}\n"
            "Revised after checking coverage.\n"
            f"{PLAN_START}\n{second}\n{PLAN_END}\n"
            "Continuing with recommended answers."
        )

        result = parse_plan_response(response)

        self.assertTrue(result.valid)
        self.assertEqual(result.plan, "Draft two.")
        self.assertEqual(result.questions[0].text, "Which host?")
        self.assertEqual(result.questions[0].options[0].label, "Cloud (Recommended)")

    def test_parser_skips_broken_earlier_block_for_later_valid_one(self):
        broken = '{"plan":"Truncated draft without closing quotes or questions'
        valid = (
            '{"plan":"Recovered plan.","questions":[{"id":"q1","question":"Which?",'
            '"options":[{"id":"a","label":"KXHIGHLAX only (Recommended)"},'
            '{"id":"b","label":"All series"}]}],"no_more_questions":false}'
        )
        response = f"{PLAN_START}\n{broken}\n{PLAN_END}\n{PLAN_START}\n{valid}\n{PLAN_END}"

        result = parse_plan_response(response)

        self.assertTrue(result.valid)
        self.assertEqual(result.plan, "Recovered plan.")
        self.assertEqual(len(result.questions), 1)

    def test_parser_accepts_raw_newlines_inside_json_strings(self):
        response = (
            f"{PLAN_START}\n"
            '{"plan":"Use regime ACF.\\n\\n## Goal\\nPull Kalshi Los Angeles daily high-temperature\n'
            '**trade-by-trade** data.",'
            '"questions":[{"id":"q1","question":"Which universe?",'
            '"options":[{"id":"a","label":"KXHIGHLAX only (Recommended)"},'
            '{"id":"b","label":"All\nClimate and Weather series already discoverable"}],'
            '"required":true}],"no_more_questions":false}\n'
            f"{PLAN_END}"
        )

        result = parse_plan_response(response)

        self.assertTrue(result.valid)
        self.assertIn("trade-by-trade", result.plan)
        self.assertEqual(
            result.questions[0].options[1].label,
            "All\nClimate and Weather series already discoverable",
        )

    def test_parser_accepts_cursor_preamble_and_four_unconfirmed_questions(self):
        """Cursor may include prose and omit redundant false confirmation."""
        response = (
            "I'll inspect the repo and storage conventions first.\n"
            "I have enough context to draft the plan and open decisions.\n"
            f"{PLAN_START}\n"
            '{"plan":"Collect the requested weather trades and compare the two regimes.",'
            '"questions":[{"id":"q1","question":"Which weather markets?",'
            '"required":true,"options":[{"id":"a","label":"Los Angeles daily high only (Recommended)"},'
            '{"id":"b","label":"Multiple weather cities"}]},{"id":"q2",'
            '"question":"Which autocorrelation matrix?","required":true,"options":['
            '{"id":"a","label":"Lag ACF summary (Recommended)"},{"id":"b","label":"Cross-market correlation"}]},'
            '{"id":"q3","question":"Include variance?","required":true,"options":['
            '{"id":"a","label":"ACF only (Recommended)"},{"id":"b","label":"Include raw variance"}]},'
            '{"id":"q4","question":"How should existing coverage refresh?","required":true,"options":['
            '{"id":"a","label":"Re-collect full range (Recommended)"},{"id":"b","label":"Merge missing dates"}]}]}'
            f"\n{PLAN_END}"
        )

        result = parse_plan_response(response)

        self.assertTrue(result.valid)
        self.assertFalse(result.no_more_questions)
        self.assertEqual([question.question_id for question in result.questions], ["q1", "q2", "q3", "q4"])

    def test_parser_rejects_ambiguous_question_and_option_ids(self):
        duplicate_questions = (
            '{"plan":"Do it.","questions":[{"id":"q1","question":"First?","options":['
            '{"id":"a","label":"A"},{"id":"b","label":"B"}]},{"id":"q1",'
            '"question":"Second?","options":[{"id":"a","label":"A"},{"id":"b","label":"B"}]}],'
            '"no_more_questions":false}'
        )
        duplicate_options = (
            '{"plan":"Do it.","questions":[{"id":"q1","question":"Choose?","options":['
            '{"id":"a","label":"First"},{"id":"a","label":"Second"}]}],'
            '"no_more_questions":false}'
        )
        contradictory_confirmation = (
            '{"plan":"Do it.","questions":[{"id":"q1","question":"Choose?","options":['
            '{"id":"a","label":"First"},{"id":"b","label":"Second"}]}],'
            '"no_more_questions":true}'
        )

        self.assertFalse(parse_plan_response(duplicate_questions).valid)
        self.assertFalse(parse_plan_response(duplicate_options).valid)
        self.assertFalse(parse_plan_response(contradictory_confirmation).valid)

    def test_followup_and_implementation_prompts_include_review_context(self):
        question = PlanQuestion("q1", "Which store?", (PlanOption("a", "SQLite"), PlanOption("b", "JSON")))
        followup = build_plan_followup_prompt("Build it", "Use a store.", (question,), {"q1": "b"})
        implementation = build_implementation_prompt("Build it", "Use a store.", {"q1": "b"})

        self.assertIn("JSON", followup)
        self.assertIn('(Recommended)', followup)
        self.assertIn("Approved implementation plan", implementation)
        self.assertIn("q1: b", implementation)

    def test_custom_answer_is_added_by_the_ui_and_formatted_for_followups(self):
        question = PlanQuestion("q1", "Which store?", (PlanOption("a", "SQLite"), PlanOption("b", "JSON")))
        options = plan_answer_options(question)
        encoded = encode_custom_answer("A store selected by the user")
        followup = build_plan_followup_prompt("Build it", "Use a store.", (question,), {"q1": encoded})
        implementation = build_implementation_prompt(
            "Build it",
            "Use a store.",
            {"q1": encoded},
            {"q1": "Which store?: Custom answer: A store selected by the user"},
        )

        self.assertEqual(options[-1], PlanOption(CUSTOM_ANSWER_OPTION_ID, "Custom answer"))
        self.assertEqual(custom_answer_text(encoded), "A store selected by the user")
        self.assertIn("Custom answer: A store selected by the user", followup)
        self.assertIn("q1: A store selected by the user", implementation)

    def test_clarification_prompt_includes_plan_prompt_and_one_question(self):
        question = PlanQuestion(
            "q1",
            "Which store?",
            (PlanOption("a", "SQLite (Recommended)"), PlanOption("b", "JSON")),
        )
        other = PlanQuestion(
            "q2",
            "Which format?",
            (PlanOption("a", "Compact"), PlanOption("b", "Readable")),
        )
        clarification = build_plan_clarification_prompt(
            "Build a cache",
            "Add a local store.",
            question,
            "What does store mean here?",
        )

        self.assertIn("Original request:\nBuild a cache", clarification)
        self.assertIn("Current plan:\nAdd a local store.", clarification)
        self.assertIn("Which store?", clarification)
        self.assertIn("SQLite (Recommended)", clarification)
        self.assertIn("What does store mean here?", clarification)
        self.assertNotIn(other.text, clarification)
        self.assertNotIn("Which format?", clarification)


if __name__ == "__main__":
    unittest.main()
