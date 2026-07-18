from ai_engine.schemas import CourseGenerationResult, GradingResult

from .base import CourseGenerationInput, ProviderCourseGeneration, ProviderGrade


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


class FakeCourseGenerationProvider:
    def generate(self, request: CourseGenerationInput) -> ProviderCourseGeneration:
        module_count = max(1, min(4, round(request.duration_weeks / 4)))
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
                            "artifacts": [
                                {
                                    "artifact_type": "code_example",
                                    "content": "value = 3\nprint(value)",
                                    "metadata": {"language": "python"},
                                },
                                {
                                    "artifact_type": "image_prompt",
                                    "content": "A clear classroom illustration of a Python value stored in a labelled box.",
                                    "metadata": {"purpose": "future image generation"},
                                },
                                {
                                    "artifact_type": "youtube_search",
                                    "content": f"Python {lesson_title.lower()} for beginners",
                                    "metadata": {"search_terms": ["Python", lesson_title]},
                                },
                            ],
                            "questions": [
                                {
                                    "question_type": "scenario",
                                    "prompt": "A school club needs to store the number of learners present. Explain how you would model this in Python.",
                                    "rubric": [{"criterion": "Chooses an appropriate Python value", "weight": 50}, {"criterion": "Explains the choice clearly", "weight": 50}],
                                },
                                {
                                    "question_type": "critical_thinking",
                                    "prompt": "Compare two ways of solving this lesson problem and explain which is easier to maintain.",
                                    "rubric": [{"criterion": "Compares two approaches accurately", "weight": 50}, {"criterion": "Justifies a recommendation", "weight": 50}],
                                },
                                {
                                    "question_type": "task_prompt",
                                    "prompt": "Write a prompt that would ask a coding assistant to create a small program using this lesson concept.",
                                    "rubric": [{"criterion": "Includes a clear task", "weight": 50}, {"criterion": "Includes useful constraints", "weight": 50}],
                                },
                                {
                                    "question_type": "misconception",
                                    "prompt": "A learner says that every value in Python must be stored in a variable. Explain the misconception.",
                                    "rubric": [{"criterion": "Identifies the misconception", "weight": 50}, {"criterion": "Corrects it with an example", "weight": 50}],
                                },
                                {
                                    "question_type": "error_identification",
                                    "prompt": "Find and explain the mistake in this code: print(total) before total has been assigned.",
                                    "rubric": [{"criterion": "Identifies the error", "weight": 50}, {"criterion": "Suggests a correction", "weight": 50}],
                                },
                            ],
                            "translations": [
                                {
                                    "language_code": language_code,
                                    "content": {
                                        "title": lesson_title,
                                        "content": "Translation draft pending teacher review.",
                                    },
                                }
                                for language_code in request.translation_languages
                            ],
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
