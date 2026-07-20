from ai_engine.schemas import AnalyticsAnalysisResult, AnalyticsInsight, CourseGenerationResult, GradingResult

from .base import CourseGenerationInput, ProviderAnalyticsAnalysis, ProviderCourseGeneration, ProviderGrade


class FakeGradingProvider:
    def grade(self, *, question: str, answer: str, rubric: list[dict], execution_context=None) -> ProviderGrade:
        score = 80 if len(answer.split()) >= 8 else 60
        result = GradingResult(
            score=score,
            confidence=0.9,
            strengths=["The answer attempts the requested concept."],
            errors=[] if score >= 70 else ["Add more explanation and a concrete Python example."],
            feedback="Your response has been reviewed against the lesson rubric.",
            remediation="Review the lesson example and explain the idea with a small program." if score < 70 else "",
            recommended_action="advance" if score >= 70 else "remediate",
            requires_review=True,
        )
        return ProviderGrade(result=result, provider="fake", model="local", response_id="fake-response")


class FakeAnalyticsAnalyzer:
    def analyze(self, metrics: dict) -> ProviderAnalyticsAnalysis:
        courses = metrics.get("courses", [])
        insights = []
        for course in courses:
            title = course["title"]
            if course["completion_rate"] < 60:
                insights.append(
                    AnalyticsInsight(
                        priority="high",
                        title=f"Improve completion in {title}",
                        evidence=f"Only {course['completion_rate']}% of {course['enrollment_count']} enrolled learners have completed the course.",
                        action="Review the first unfinished lesson for each learner, then send a short check-in with one specific next step.",
                    )
                )
            if course["students_needing_help"]:
                insights.append(
                    AnalyticsInsight(
                        priority="high",
                        title=f"Follow up with learners needing support in {title}",
                        evidence=f"{course['students_needing_help']} learner(s) are flagged for support.",
                        action="Open the support queue, group learners by the lesson or misconception involved, and schedule a targeted intervention.",
                    )
                )
            if course["ai_human_gap"] >= 10:
                insights.append(
                    AnalyticsInsight(
                        priority="medium",
                        title=f"Review rubric alignment in {title}",
                        evidence=f"The average AI-to-teacher score difference is {course['ai_human_gap']} points.",
                        action="Compare the largest AI and teacher differences and clarify rubric language before the next assessment cycle.",
                    )
                )
        if not insights:
            insights.append(
                AnalyticsInsight(
                    priority="low",
                    title="Keep monitoring learner momentum",
                    evidence="No urgent threshold was detected in the current aggregate metrics.",
                    action="Review this page weekly and act when completion, pass rate, or lesson drop-off begins to trend down.",
                )
            )
        summary = (
            f"Reviewed {len(courses)} course(s). The clearest opportunities are learner follow-up, assessment support, and monitoring progress trends."
            if courses
            else "There are no course metrics to analyze yet. Create or teach a course to unlock actionable insights."
        )
        return ProviderAnalyticsAnalysis(
            result=AnalyticsAnalysisResult(
                summary=summary,
                insights=insights[:8],
                next_steps=[
                    "Start with the highest-priority insight and assign a clear owner.",
                    "Recheck the affected metric after the next learner support or assessment cycle.",
                ],
            ),
            provider="fake",
            model="local",
            response_id="fake-analytics-analysis",
        )


class FakeCourseGenerationProvider:
    def generate(self, request: CourseGenerationInput) -> ProviderCourseGeneration:
        module_count = max(1, min(4, round(request.duration_weeks / 4)))
        question_templates = {
            "scenario": {
                "question_type": "scenario",
                "prompt": "A school club needs to store the number of learners present. Explain how you would model this in Python.",
                "rubric": [{"criterion": "Chooses an appropriate Python value", "weight": 50}, {"criterion": "Explains the choice clearly", "weight": 50}],
            },
            "critical_thinking": {
                "question_type": "critical_thinking",
                "prompt": "Compare two ways of solving this lesson problem and explain which is easier to maintain.",
                "rubric": [{"criterion": "Compares two approaches accurately", "weight": 50}, {"criterion": "Justifies a recommendation", "weight": 50}],
            },
            "task_prompt": {
                "question_type": "task_prompt",
                "prompt": "Write a prompt that would ask a coding assistant to create a small program using this lesson concept.",
                "rubric": [{"criterion": "Includes a clear task", "weight": 50}, {"criterion": "Includes useful constraints", "weight": 50}],
            },
            "misconception": {
                "question_type": "misconception",
                "prompt": "A learner says that every value in Python must be stored in a variable. Explain the misconception.",
                "rubric": [{"criterion": "Identifies the misconception", "weight": 50}, {"criterion": "Corrects it with an example", "weight": 50}],
            },
            "reflection": {
                "question_type": "reflection",
                "prompt": "Reflect on how you would apply this lesson concept in a small program of your own.",
                "rubric": [{"criterion": "Connects the concept to a realistic use", "weight": 50}, {"criterion": "Explains the reflection clearly", "weight": 50}],
            },
        }
        selected_question_types = [
            question_type for question_type in request.assessment_types if question_type in question_templates
        ] or list(question_templates)
        modules = []
        for module_number in range(1, module_count + 1):
            lesson_title = f"{request.title}: foundation {module_number}"
            modules.append(
                {
                    "title": f"Module {module_number}: Core ideas",
                    "lessons": [
                        {
                            "title": lesson_title,
                            "objectives": [
                                f"Explain the key idea in {lesson_title.lower()}",
                                "Apply the idea in a short Python program",
                            ],
                            "content": (
                                f"This lesson introduces {lesson_title.lower()} for {request.audience or 'secondary-school learners'}. "
                                "Learners should connect the concept to a small Python example and explain why the example works."
                            ),
                            "questions": [question_templates[question_type] for question_type in selected_question_types],
                        }
                    ],
                }
            )

        description = request.objective.strip()
        if len(description) < 20:
            description = f"{description}. This course builds practical understanding through guided lessons and assessments."

        result = CourseGenerationResult(
            title=request.title,
            description=description
            or f"A {request.duration_weeks}-week course for {request.audience or 'secondary-school learners'} with guided lessons and assessments.",
            modules=modules,
            final_project={
                "title": f"{request.title}: community problem-solving project",
                "brief": (
                    "Design and build a small Python solution to a practical problem in your school or community. "
                    "Explain your choices, demonstrate the program, and reflect on how you tested it."
                ),
                "objectives": [
                    "Plan a small Python solution from a real-world problem",
                    "Apply Python fundamentals in a working program",
                    "Explain and test the implementation clearly",
                ],
                "requirements": [
                    "Use variables, input or output, and at least one control structure",
                    "Include comments that explain important decisions",
                    "Test the program with at least three examples",
                ],
                "deliverables": [
                    "Python source code",
                    "Short project explanation",
                    "Demonstration or test evidence",
                ],
                "rubric": [
                    {"criterion": "The program solves a clearly defined problem", "weight": 30},
                    {"criterion": "The Python implementation is accurate and readable", "weight": 30},
                    {"criterion": "Testing evidence is relevant and complete", "weight": 20},
                    {"criterion": "The learner explains decisions and limitations", "weight": 20},
                ],
                "estimated_hours": max(4, min(20, request.duration_weeks // 2)),
            },
        )
        return ProviderCourseGeneration(
            result=result,
            provider="fake",
            model="local",
            input_tokens=0,
            output_tokens=0,
            response_id="fake-course-generation",
        )
